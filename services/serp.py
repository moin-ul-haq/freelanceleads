# services/serp.py

from django.conf import settings
from serpapi import GoogleSearch


def _normalize(text: str) -> str:
    return text.strip().lower() if text else ""


def _extract_country(address: str) -> str:
    """
    Extracts last part of address as country name.
    Example: "123 Main St, Albany, NY, USA" → "USA"
    Example: "Plot 5, DHA, Lahore, Pakistan" → "Pakistan"
    Falls back to empty string if not found.
    """
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    return parts[-1].strip() if parts else ""


def search_businesses(
    niche: str, city: str, country: str = "", start: int = 0
) -> list[dict]:
    """
    Searches Google Maps via SerpAPI for businesses matching niche + city.
    Works globally — no country-specific logic.

    Returns normalized list of business dicts ready to save in Lead model.
    """
    query = f"{niche} in {city}"
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": settings.SERP_API_KEY,
        "start": start,
    }

    try:
        results = GoogleSearch(params).get_dict()
    except Exception as e:
        raise RuntimeError(f"SerpAPI error: {e}")

    businesses = results.get("local_results", [])
    normalized = []

    for b in businesses:
        address = b.get("address", "")
        coordinates = b.get("gps_coordinates", {})

        normalized.append(
            {
                "place_id": b.get("place_id", ""),
                "name": b.get("title", ""),
                "niche": _normalize(niche),
                # Use searched city as-is — most reliable globally
                "city": _normalize(city),
                # SerpAPI does not return state separately — extract from address if needed
                "state": "",  # will be enriched later if needed
                # Extract country from last part of address
                "country": country or _extract_country(address),
                "address": address,
                "phone": b.get("phone", ""),
                "website": b.get("website", ""),
                "rating": b.get("rating"),
                "review_count": b.get("reviews", 0),
                "gbp_status": b.get("type", ""),
                "has_website": bool(b.get("website")),
                # Store coordinates — useful for future geo features
                "latitude": coordinates.get("latitude"),
                "longitude": coordinates.get("longitude"),
            }
        )

    return normalized
