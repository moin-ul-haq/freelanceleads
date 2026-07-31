# demosites/ai.py
#
# Generates the copy for a one-page demo site. Same grounding doctrine as
# pitches: only use facts we actually have. No invented years-in-business,
# certifications, review quotes, or guarantees — this page is shown to the
# business owner themselves, so fabrications kill the pitch instantly.

import json

from services.ai import complete_json

SITE_SYSTEM_PROMPT = """
You write website copy for a one-page site for a local business. The copy is a DEMO the freelancer shows the business owner, so it must feel like it was written specifically for that business and be believable to the owner.

Return ONLY valid JSON exactly matching:
{
  "headline": "...",       // hero headline, max 8 words, benefit-led, mentions the service naturally
  "tagline": "...",        // one sentence under the headline, mentions the city
  "about": "...",          // 2-3 sentences about the business, warm and plain, first person plural ("we")
  "services": [            // exactly 4 items, realistic offerings for this niche
    {"name": "...", "description": "..."}   // description = one sentence
  ],
  "why_us": ["...", "...", "..."],  // exactly 3 short trust points
  "cta_headline": "...",   // e.g. "Ready to get started?"
  "cta_text": "..."        // one sentence pushing a call/visit
}

Rules:
- Ground everything in the provided data (name, niche, city, rating, reviews).
- If rating >= 4 and review_count > 0 you may reference it ("rated X stars by our customers"). Otherwise never mention ratings or reviews.
- NEVER invent: years in business, certifications, awards, team size, guarantees, customer quotes, or specific prices.
- Plain, confident, local-business language. 6th-grade words. No hype ("world-class", "premier", "unmatched"), no em dashes.
- Services must fit the niche (a plumber gets drain cleaning, not "digital strategy").
""".strip()

REQUIRED_KEYS = ("headline", "tagline", "about", "services", "why_us", "cta_headline", "cta_text")


def generate_site_content(lead) -> dict:
    payload = {
        "name": lead.name,
        "niche": lead.niche,
        "city": lead.city,
        "country": lead.country,
        "rating": lead.rating,
        "review_count": lead.review_count,
        "phone": lead.phone or None,
    }
    raw = complete_json(
        system_prompt=SITE_SYSTEM_PROMPT,
        user_prompt=json.dumps(payload, indent=2),
        temperature=0.7,
        max_tokens=1200,
    )
    content = json.loads(raw)

    missing = [k for k in REQUIRED_KEYS if k not in content]
    if missing:
        raise RuntimeError(f"AI returned incomplete site content (missing {missing})")
    return content
