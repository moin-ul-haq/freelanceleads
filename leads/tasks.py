# leads/tasks.py

import requests
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from celery import shared_task
from django.db.models import Q

from .models import Lead
from services.email_finder import find_business_email, _fetch_page, _extract_email_from_html
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
            s.settimeout(3)  # reduced from 5
            s.connect((hostname, 443))
        return True
    except Exception:
        return False


def _scrape_website(url: str) -> dict:
    """
    Scrapes website HTML and checks:
    - meta title, meta description
    - schema markup (JSON-LD)
    - social media links
    """
    result = {
        "has_meta_title": False,
        "has_meta_desc": False,
        "has_schema": False,
        "has_social": False,
        "email": "",
    }

    if not url:
        return result

    try:
        content, final_url = _fetch_page(url)
        if not content:
            return result

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

    # Run SSL check and scrape concurrently
    has_ssl = False
    scraped = {
        "has_meta_title": False,
        "has_meta_desc": False,
        "has_schema": False,
        "has_social": False,
        "email": "",
    }

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_check_ssl, website): "ssl",
            ex.submit(_scrape_website, website): "scrape",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == "ssl":
                    has_ssl = future.result()
                else:
                    scraped = future.result()
            except Exception:
                pass  # keep defaults on failure

    # Recalculate full score with all audit data
    score = calculate_score(
        has_website=lead.has_website,
        has_ssl=has_ssl,
        pagespeed_score=None,  # added later with PageSpeed API
        rating=lead.rating,
        review_count=lead.review_count,
        has_meta_title=scraped["has_meta_title"],
        has_meta_desc=scraped["has_meta_desc"],
        has_schema=scraped["has_schema"],
        has_social=scraped["has_social"],
    )

    # Save permanently to DB — next time lead comes from cache/DB, no audit needed
    lead.has_ssl = has_ssl
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
    """
    # Queue new audits and backfill email for audited leads that still have no email
    pending_ids = (
        Lead.objects.filter(id__in=lead_ids)
        .filter(
            Q(audit_done=False)
            | Q(audit_done=True, email="", has_website=True)
        )
        .values_list("id", flat=True)
    )

    for lead_id in pending_ids:
        audit_lead.delay(lead_id)
