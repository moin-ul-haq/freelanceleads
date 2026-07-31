# leads/tasks.py

import requests
import ssl
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from celery import shared_task
from django.conf import settings
from django.db.models import Q

from .models import Lead
from services.email_finder import find_business_email, _fetch_page, _extract_email_from_html
from services.pagespeed import get_pagespeed_score
from services.scoring import calculate_score

AUDIT_META_BYTES = 120_000


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────


def _check_ssl(url: str) -> bool:
    """Returns True if website has valid SSL certificate."""
    if not url:
        return False
    try:
        hostname = url.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(6)  # slow-but-valid TLS handshakes must not read as "no SSL"
            s.connect((hostname, 443))
        return True
    except Exception:
        return False


def _audit_website(url: str) -> dict:
    """
    Fetches the site once and derives all website checks from it.

    Key rule: if the site can't be fetched at all (bot wall, geo block,
    datacenter-IP block, dead host), the audit is INCONCLUSIVE — we must not
    record unverified problems as facts. False "no SSL" / "no meta" flags
    inflate the opportunity score and, worse, produce pitches that accuse the
    business of problems it doesn't have. Unverifiable checks default to
    "no problem found".
    """
    result = {
        "reachable": False,
        "has_ssl": url.startswith("https://"),
        "has_meta_title": True,
        "has_meta_desc": True,
        "has_schema": True,
        "has_social": True,
        "email": "",
    }

    if not url:
        return result

    try:
        content, final_url = _fetch_page(url)
        if not content:
            # Unreachable from our network — only SSL can still be probed
            if not result["has_ssl"]:
                result["has_ssl"] = _check_ssl(url)
            return result

        result["reachable"] = True
        # Real-world truth: if the browser-style fetch landed on https, SSL works
        result["has_ssl"] = final_url.startswith("https://") or _check_ssl(final_url)

        meta_html = content[:AUDIT_META_BYTES]
        soup = BeautifulSoup(meta_html, "html.parser")

        result["has_meta_title"] = bool(soup.find("title"))

        meta_desc = soup.find("meta", attrs={"name": "description"})
        result["has_meta_desc"] = bool(meta_desc and meta_desc.get("content"))

        result["has_schema"] = bool(
            soup.find("script", attrs={"type": "application/ld+json"})
        )

        social_domains = [
            "facebook.com",
            "instagram.com",
            "twitter.com",
            "x.com",
            "linkedin.com",
            "tiktok.com",
        ]
        links = [a.get("href", "") for a in soup.find_all("a", href=True)]
        result["has_social"] = any(
            any(domain in link for domain in social_domains) for link in links
        )

        # Full email pass (large-page safe + contact link discovery)
        result["email"] = _extract_email_from_html(content, final_url)
        if not result["email"]:
            result["email"] = find_business_email(
                final_url,
                homepage_content=content,
                homepage_final_url=final_url,
            )

    except Exception:
        pass

    return result


def _enrich_lead_email(lead: Lead) -> bool:
    """Try to find and save email for a lead that already has audit_done=True."""
    if lead.email or not lead.website:
        return False

    email = find_business_email(lead.website)
    if not email:
        return False

    lead.email = email
    lead.save(update_fields=["email", "updated_at"])
    return True


# ─────────────────────────────────────────────────────────────
#  Tasks
# ─────────────────────────────────────────────────────────────


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def audit_lead(self, lead_id: int):
    """
    Runs full audit for a single lead.
    - Skips if already audited (audit_done=True)
    - Skips scraping if no website
    - Runs SSL + scrape concurrently via ThreadPoolExecutor
    - Saves results to DB permanently
    """
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return

    website = lead.website

    # Already audited but missing email — backfill without re-running full audit
    if lead.audit_done:
        _enrich_lead_email(lead)
        return

    # No website — skip all checks, just mark done
    if not website:
        lead.audit_done = True
        lead.opportunity_score = calculate_score(
            has_website=False,
            has_ssl=False,
            pagespeed_score=None,
            rating=lead.rating,
            review_count=lead.review_count,
            has_meta_title=False,
            has_meta_desc=False,
            has_schema=False,
            has_social=False,
        )
        lead.save(update_fields=["audit_done", "opportunity_score"])
        return

    # Run the site audit and PageSpeed concurrently
    scraped = {
        "reachable": False,
        "has_ssl": website.startswith("https://"),
        "has_meta_title": True,
        "has_meta_desc": True,
        "has_schema": True,
        "has_social": True,
        "email": "",
    }
    pagespeed_score = None

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_audit_website, website): "site",
            ex.submit(get_pagespeed_score, website): "pagespeed",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == "pagespeed":
                    pagespeed_score = future.result()
                else:
                    scraped = future.result()
            except Exception:
                pass  # keep defaults on failure

    # Recalculate full score with all audit data
    score = calculate_score(
        has_website=lead.has_website,
        has_ssl=scraped["has_ssl"],
        pagespeed_score=pagespeed_score,
        rating=lead.rating,
        review_count=lead.review_count,
        has_meta_title=scraped["has_meta_title"],
        has_meta_desc=scraped["has_meta_desc"],
        has_schema=scraped["has_schema"],
        has_social=scraped["has_social"],
    )

    # Save permanently to DB — next time lead comes from cache/DB, no audit needed
    lead.pagespeed_score = pagespeed_score
    lead.has_ssl = scraped["has_ssl"]
    lead.has_meta_title = scraped["has_meta_title"]
    lead.has_meta_desc = scraped["has_meta_desc"]
    lead.has_schema = scraped["has_schema"]
    lead.has_social = scraped["has_social"]
    lead.opportunity_score = score
    lead.audit_done = True

    update_fields = [
        "has_ssl",
        "has_meta_title",
        "has_meta_desc",
        "has_schema",
        "has_social",
        "opportunity_score",
        "audit_done",
        "updated_at",
    ]
    if scraped.get("email") and not lead.email:
        lead.email = scraped["email"]
        update_fields.append("email")

    lead.save(update_fields=update_fields)


@shared_task
def audit_leads_batch(lead_ids: list[int]):
    """
    Fires individual audit_lead tasks for a batch of leads.
    Only queues leads that have not been audited yet — saves Celery queue space.

    With a real broker each lead becomes its own Celery task (workers parallelize).
    In eager mode (no Redis) we parallelize locally with a thread pool instead of
    running 20 sequential audits.
    """
    # Queue new audits and backfill email for audited leads that still have no email
    pending_ids = list(
        Lead.objects.filter(id__in=lead_ids)
        .filter(
            Q(audit_done=False)
            | Q(audit_done=True, email="", has_website=True)
        )
        .values_list("id", flat=True)
    )

    if not pending_ids:
        return

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        with ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(_audit_lead_safe, pending_ids))
    else:
        for lead_id in pending_ids:
            audit_lead.delay(lead_id)


def _audit_lead_safe(lead_id: int):
    """Run one audit, never letting an exception kill the batch pool."""
    try:
        audit_lead(lead_id)
    except Exception:
        pass


def dispatch_audits(lead_ids: list[int]):
    """
    Entry point for views: never blocks the request.
    - Broker mode: hand off to Celery.
    - Eager mode: run the batch in a daemon thread so the API responds instantly
      while audits fill in scores/emails in the background.
    """
    if not lead_ids:
        return
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        threading.Thread(
            target=audit_leads_batch, args=(lead_ids,), daemon=True
        ).start()
    else:
        audit_leads_batch.delay(lead_ids)
