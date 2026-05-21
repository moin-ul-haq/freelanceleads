# services/scoring.py

"""
Opportunity Score Algorithm (0-100)
Higher score = more problems = more opportunity for freelancer to pitch services.

Scoring logic:
- Start at 0
- Add points for each problem found
- More problems = higher score = better lead

Score interpretation:
    70-100 = Hot Lead
    40-69  = Warm Lead
    0-39   = Cold Lead
"""


# ── Problem Weights ───────────────────────────────────────────────

PROBLEM_WEIGHTS = {
    "no_website": 40,  # Biggest opportunity — build from scratch
    "no_ssl": 15,  # HTTP only
    # 'slow_pagespeed': 15,  # TODO: enable later — PageSpeed score < 50
    "poor_rating": 10,  # Rating < 3.5 stars
    "low_review_count": 10,  # Less than 10 reviews
    "missing_meta": 10,  # No meta title or description
    "no_schema": 5,  # No JSON-LD / structured data
    "no_social": 10,  # No social media presence
}
# Total possible = 100 (clean — no normalization needed)

# Score thresholds
HOT_LEAD_THRESHOLD = 70
WARM_LEAD_THRESHOLD = 40


def calculate_score(
    has_website: bool,
    has_ssl: bool,
    pagespeed_score: int | None,  # reserved — not used in scoring yet
    rating: float | None,
    review_count: int,
    has_meta_title: bool,
    has_meta_desc: bool,
    has_schema: bool,
    has_social: bool,
) -> int:
    """
    Calculates opportunity score for a single lead.
    Returns integer between 0 and 100.
    Higher score = more problems = better opportunity.
    """
    score = 0

    if not has_website:
        score += PROBLEM_WEIGHTS["no_website"]

    if not has_ssl:
        score += PROBLEM_WEIGHTS["no_ssl"]

    # TODO: Uncomment when pagespeed integration is ready
    # if pagespeed_score is not None and pagespeed_score < 50:
    #     score += PROBLEM_WEIGHTS['slow_pagespeed']

    if rating is not None and rating < 3.5:
        score += PROBLEM_WEIGHTS["poor_rating"]

    if review_count < 10:
        score += PROBLEM_WEIGHTS["low_review_count"]

    if not has_meta_title or not has_meta_desc:
        score += PROBLEM_WEIGHTS["missing_meta"]

    if not has_schema:
        score += PROBLEM_WEIGHTS["no_schema"]

    if not has_social:
        score += PROBLEM_WEIGHTS["no_social"]

    return max(0, min(100, score))  # clamp between 0 and 100


def get_score_label(score: int) -> str:
    """Returns human readable label for score."""
    if score >= HOT_LEAD_THRESHOLD:
        return "hot"
    elif score >= WARM_LEAD_THRESHOLD:
        return "warm"
    return "cold"


def get_score_reasons(
    has_website: bool,
    has_ssl: bool,
    pagespeed_score: int | None,  # reserved — not used in scoring yet
    rating: float | None,
    review_count: int,
    has_meta_title: bool,
    has_meta_desc: bool,
    has_schema: bool,
    has_social: bool,
) -> list[str]:
    """
    Returns list of reasons why this lead scored high.
    Used in frontend to show freelancer what to pitch.
    Example: ["No website", "No SSL certificate", "Only 3 reviews"]
    """
    reasons = []

    if not has_website:
        reasons.append("No website found")

    if not has_ssl:
        reasons.append("No SSL certificate (HTTP only)")

    # TODO: Uncomment when pagespeed integration is ready
    # if pagespeed_score is not None and pagespeed_score < 50:
    #     reasons.append(f"Slow website speed (score: {pagespeed_score}/100)")

    if rating is not None and rating < 3.5:
        reasons.append(f"Poor rating ({rating} stars)")

    if review_count < 10:
        reasons.append(f"Very few reviews ({review_count})")

    if not has_meta_title or not has_meta_desc:
        reasons.append("Missing meta title or description")

    if not has_schema:
        reasons.append("No schema markup found")

    if not has_social:
        reasons.append("No social media presence")

    return reasons


def score_from_lead(lead) -> tuple[int, str, list[str]]:
    """
    Convenience function — takes a Lead model instance.
    Returns (score, label, reasons) tuple.

    Usage:
        score, label, reasons = score_from_lead(lead)
    """
    score = calculate_score(
        has_website=lead.has_website,
        has_ssl=lead.has_ssl,
        pagespeed_score=lead.pagespeed_score,
        rating=lead.rating,
        review_count=lead.review_count,
        has_meta_title=lead.has_meta_title,
        has_meta_desc=lead.has_meta_desc,
        has_schema=lead.has_schema,
        has_social=lead.has_social,
    )
    label = get_score_label(score)
    reasons = get_score_reasons(
        has_website=lead.has_website,
        has_ssl=lead.has_ssl,
        pagespeed_score=lead.pagespeed_score,
        rating=lead.rating,
        review_count=lead.review_count,
        has_meta_title=lead.has_meta_title,
        has_meta_desc=lead.has_meta_desc,
        has_schema=lead.has_schema,
        has_social=lead.has_social,
    )
    return score, label, reasons
