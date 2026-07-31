# demosites/ai.py
#
# Generates the copy for a full one-page demo site. Same grounding doctrine
# as pitches: only use facts we actually have (plus details the freelancer
# explicitly typed in). No invented years-in-business, certifications,
# review quotes, or guarantees — this page is shown to the business owner
# themselves, so fabrications kill the pitch instantly.

import json

from services.ai import complete_json

SITE_SYSTEM_PROMPT = """
You write website copy for a one-page site for a local business. The copy is a DEMO the freelancer shows the business owner, so it must feel like it was written specifically for that business and be believable to the owner.

Return ONLY valid JSON exactly matching:
{
  "headline": "...",         // hero headline, max 9 words, benefit-led, mentions the service naturally
  "tagline": "...",          // one sentence under the headline, mentions the city
  "hero_points": ["...", "...", "..."],   // 3 punchy trust chips, 2-4 words each (e.g. "Same-day service")
  "about_p1": "...",         // first about paragraph, 3-4 sentences, warm, first person plural ("we")
  "about_p2": "...",         // second about paragraph, 2-3 sentences, focus on how they treat customers
  "services": [              // exactly 6 items, realistic offerings for this niche
    {"name": "...", "description": "..."}   // description = 1-2 sentences
  ],
  "why_us": [                // exactly 4 items
    {"title": "...", "text": "..."}   // title 2-4 words, text one sentence
  ],
  "process": [               // exactly 3 steps: how working with them goes
    {"title": "...", "text": "..."}
  ],
  "faq": [                   // exactly 4 questions a customer in this niche actually asks
    {"q": "...", "a": "..."}   // answer 1-2 sentences, honest and non-committal on prices
  ],
  "service_area": "...",     // one sentence: which area they serve, built from the city
  "cta_headline": "...",     // e.g. "Ready to get started?"
  "cta_text": "..."          // one sentence pushing a call or the contact form
}

Rules:
- Ground everything in the provided data (name, niche, city, rating, reviews, and the freelancer's optional notes).
- If the freelancer supplied a services list, use EXACTLY those as the service names (expand each with a fitting description). Otherwise choose 6 realistic services for the niche.
- If the freelancer supplied extra_info, weave those facts naturally into about/why_us — these are real facts from the business.
- If rating >= 4 and review_count > 0 you may reference it ("rated X stars by our customers"). Otherwise never mention ratings or reviews.
- NEVER invent: years in business, certifications, awards, team size, guarantees, customer quotes, or specific prices. FAQ answers must not promise prices or timelines.
- Plain, confident, local-business language. 6th-grade words. No hype ("world-class", "premier", "unmatched"), no em dashes.
- Match the requested copy tone. "auto" means: pick what fits the niche (e.g. warm for a salon, reassuring for a plumber, energetic for a gym).
""".strip()

REQUIRED_KEYS = (
    "headline", "tagline", "hero_points", "about_p1", "about_p2", "services",
    "why_us", "process", "faq", "service_area", "cta_headline", "cta_text",
)

TONES = ("auto", "friendly", "professional", "bold", "luxury", "playful")


def generate_site_content(lead, tone: str = "auto", services_hint: str = "", extra_info: str = "") -> dict:
    payload = {
        "name": lead.name,
        "niche": lead.niche,
        "city": lead.city,
        "country": lead.country,
        "rating": lead.rating,
        "review_count": lead.review_count,
        "phone": lead.phone or None,
        "copy_tone": tone if tone in TONES else "auto",
    }
    if services_hint.strip():
        payload["services_list_from_freelancer"] = [
            s.strip() for s in services_hint.split(",") if s.strip()
        ][:6]
    if extra_info.strip():
        payload["extra_info"] = extra_info.strip()[:1000]

    raw = complete_json(
        system_prompt=SITE_SYSTEM_PROMPT,
        user_prompt=json.dumps(payload, indent=2),
        temperature=0.7,
        max_tokens=2800,
    )
    content = json.loads(raw)

    missing = [k for k in REQUIRED_KEYS if k not in content]
    if missing:
        raise RuntimeError(f"AI returned incomplete site content (missing {missing})")
    return content
