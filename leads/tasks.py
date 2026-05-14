# leads/tasks.py

import requests
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from celery import shared_task

from .models import Lead
from services.scoring import calculate_score


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _check_ssl(url: str) -> bool:
    """Returns True if website has valid SSL certificate."""
    if not url:
        return False
    try:
        hostname = url.replace('https://', '').replace('http://', '').split('/')[0]
        ctx      = ssl.create_default_context()
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
        'has_meta_title': False,
        'has_meta_desc' : False,
        'has_schema'    : False,
        'has_social'    : False,
    }

    if not url:
        return result

    try:
        response = requests.get(
            url,
            timeout = 4,  # reduced from 8
            headers = {'User-Agent': 'Mozilla/5.0'},
            stream  = True,  # don't download full page — stop at size limit
        )

        # Read only first 50KB — enough for head/meta tags, saves bandwidth
        content = b''
        for chunk in response.iter_content(chunk_size=1024):
            content += chunk
            if len(content) > 50_000:
                break

        soup = BeautifulSoup(content, 'html.parser')

        result['has_meta_title'] = bool(soup.find('title'))

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        result['has_meta_desc'] = bool(meta_desc and meta_desc.get('content'))

        result['has_schema'] = bool(
            soup.find('script', attrs={'type': 'application/ld+json'})
        )

        social_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'linkedin.com', 'tiktok.com']
        links          = [a.get('href', '') for a in soup.find_all('a', href=True)]
        result['has_social'] = any(
            any(domain in link for domain in social_domains)
            for link in links
        )

    except Exception:
        pass

    return result


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

    # Skip if already audited — DB is source of truth
    if lead.audit_done:
        return

    website = lead.website

    # No website — skip all checks, just mark done
    if not website:
        lead.audit_done        = True
        lead.opportunity_score = calculate_score(
            has_website     = False,
            has_ssl         = False,
            pagespeed_score = None,
            rating          = lead.rating,
            review_count    = lead.review_count,
            has_meta_title  = False,
            has_meta_desc   = False,
            has_schema      = False,
            has_social      = False,
        )
        lead.save(update_fields=['audit_done', 'opportunity_score'])
        return

    # Run SSL check and scrape concurrently
    has_ssl = False
    scraped = {
        'has_meta_title': False,
        'has_meta_desc' : False,
        'has_schema'    : False,
        'has_social'    : False,
    }

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_check_ssl, website)     : 'ssl',
            ex.submit(_scrape_website, website) : 'scrape',
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == 'ssl':
                    has_ssl = future.result()
                else:
                    scraped = future.result()
            except Exception:
                pass  # keep defaults on failure

    # Recalculate full score with all audit data
    score = calculate_score(
        has_website     = lead.has_website,
        has_ssl         = has_ssl,
        pagespeed_score = None,  # added later with PageSpeed API
        rating          = lead.rating,
        review_count    = lead.review_count,
        has_meta_title  = scraped['has_meta_title'],
        has_meta_desc   = scraped['has_meta_desc'],
        has_schema      = scraped['has_schema'],
        has_social      = scraped['has_social'],
    )

    # Save permanently to DB — next time lead comes from cache/DB, no audit needed
    lead.has_ssl           = has_ssl
    lead.has_meta_title    = scraped['has_meta_title']
    lead.has_meta_desc     = scraped['has_meta_desc']
    lead.has_schema        = scraped['has_schema']
    lead.has_social        = scraped['has_social']
    lead.opportunity_score = score
    lead.audit_done        = True
    lead.save(update_fields=[
        'has_ssl', 'has_meta_title', 'has_meta_desc',
        'has_schema', 'has_social', 'opportunity_score', 'audit_done',
        'updated_at',
    ])


@shared_task
def audit_leads_batch(lead_ids: list[int]):
    """
    Fires individual audit_lead tasks for a batch of leads.
    Only queues leads that have not been audited yet — saves Celery queue space.
    """
    # Filter out already audited leads before queuing
    pending_ids = Lead.objects.filter(
        id__in    = lead_ids,
        audit_done = False
    ).values_list('id', flat=True)

    for lead_id in pending_ids:
        audit_lead.delay(lead_id)