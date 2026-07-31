# services/pagespeed.py
#
# Google PageSpeed Insights API wrapper (free API).
# Returns the mobile performance score (0-100) for a URL, or None on any
# failure — audits must never crash because PageSpeed is unavailable.

import requests
from django.conf import settings

PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TIMEOUT_SECONDS = 30


def get_pagespeed_score(url: str, strategy: str = "mobile") -> int | None:
    """
    Fetches the Lighthouse performance score for a URL.

    Returns an int 0-100, or None if the check is disabled (no key),
    the URL is missing, or the API call fails.
    """
    if not url or not settings.PAGESPEED_API_KEY:
        return None

    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
        "key": settings.PAGESPEED_API_KEY,
    }

    try:
        resp = requests.get(PAGESPEED_ENDPOINT, params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        raw = data["lighthouseResult"]["categories"]["performance"]["score"]
        return round(raw * 100)
    except Exception:
        return None
