# demosites/ai.py
#
# Generates the copy for a full one-page demo site. Same grounding doctrine
# as pitches: only use facts we actually have (plus details the freelancer
# explicitly typed in). No invented years-in-business, certifications,
# review quotes, or guarantees — this page is shown to the business owner
# themselves, so fabrications kill the pitch instantly.

import json

from services.ai import complete_json, clean_typography

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
- Plain, confident, local-business language. 6th-grade words. No hype words ("world-class", "premier", "unmatched", "unparalleled", "elevate", "unlock"), no em dashes.
- Match the requested copy tone. "auto" means: pick what fits the niche (e.g. warm for a salon, reassuring for a plumber, energetic for a gym).
""".strip()

REQUIRED_TEXT_KEYS = (
    "headline", "tagline", "about_p1", "about_p2",
    "service_area", "cta_headline", "cta_text",
)

# (key, exact count rendered, minimum acceptable, item shape)
LIST_SPECS = (
    ("hero_points", 3, 2, str),
    ("services", 6, 4, {"name", "description"}),
    ("why_us", 4, 3, {"title", "text"}),
    ("process", 3, 3, {"title", "text"}),
    ("faq", 4, 3, {"q", "a"}),
)

TONES = ("auto", "friendly", "professional", "bold", "luxury", "playful")

BANNED_WORDS = ("world-class", "premier", "unmatched", "unparalleled", "elevate", "unlock")


def _validate(content: dict) -> list[str]:
    """Returns a list of concrete problems — empty list means ship it."""
    problems = []

    for key in REQUIRED_TEXT_KEYS:
        val = content.get(key)
        if not isinstance(val, str) or len(val.strip()) < 8:
            problems.append(f"'{key}' is missing or too short")

    headline = content.get("headline") or ""
    if isinstance(headline, str) and len(headline.split()) > 12:
        problems.append("'headline' is longer than 12 words")

    for key, _want, minimum, shape in LIST_SPECS:
        items = content.get(key)
        if not isinstance(items, list) or len(items) < minimum:
            problems.append(f"'{key}' needs at least {minimum} items")
            continue
        for item in items:
            if shape is str:
                if not isinstance(item, str) or not item.strip():
                    problems.append(f"'{key}' contains an empty entry")
                    break
            else:
                if not isinstance(item, dict) or not shape.issubset(item) or any(
                    not str(item.get(f, "")).strip() for f in shape
                ):
                    problems.append(f"'{key}' items must all have non-empty {sorted(shape)}")
                    break

    lowered = json.dumps(content).lower()
    hits = [w for w in BANNED_WORDS if w in lowered]
    if hits:
        problems.append(f"remove hype words: {hits}")

    return problems


def _normalize(content: dict) -> dict:
    """Trims lists to the exact rendered counts and cleans typography everywhere."""

    def clean(value):
        if isinstance(value, str):
            return clean_typography(value)
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        return value

    content = clean(content)
    for key, want, _minimum, _shape in LIST_SPECS:
        content[key] = content[key][:want]
    return content


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

    user_prompt = json.dumps(payload, indent=2)
    problems = ["not generated yet"]
    content = None

    # Two attempts: the retry feeds the validator's complaints back to the
    # model so the second pass fixes exactly what was wrong.
    for attempt in range(2):
        try:
            raw = complete_json(
                system_prompt=SITE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.7 if attempt == 0 else 0.4,
                max_tokens=2800,
            )
            content = json.loads(raw)
        except Exception:
            content = None
            problems = ["previous response was not valid JSON"]
            continue

        problems = _validate(content)
        if not problems:
            break
        user_prompt = (
            json.dumps(payload, indent=2)
            + "\n\nYour previous attempt had these problems, fix ALL of them:\n- "
            + "\n- ".join(problems)
        )

    if problems:
        raise RuntimeError(
            "AI couldn't produce complete site content, please try again. "
            f"(issues: {problems[:3]})"
        )

    return _normalize(content)
