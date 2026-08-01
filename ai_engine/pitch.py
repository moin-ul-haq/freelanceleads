# ═══════════════════════════════════════════════════════════════
#  ai_engine/pitch.py
#  Pitch email generation logic.
# ═══════════════════════════════════════════════════════════════

import json
import re
from services.ai import complete, complete_json
from ai_engine.prompts import PITCH_SYSTEM_PROMPT, BULK_PITCH_SYSTEM_PROMPT, PROPOSAL_SYSTEM_PROMPT

# Normalize typography the model sneaks in despite instructions —
# cold emails must read as typed by a human, not typeset.
_PUNCT_MAP = str.maketrans({
    "‘": "'", "’": "'",   # curly single quotes
    "“": '"', "”": '"',   # curly double quotes
    "‑": "-", "‐": "-",   # unicode hyphens
    "–": "-",                   # en dash
    "—": ", ",                  # em dash → comma
    " ": " ",                   # non-breaking space
})


def _clean_copy(text: str) -> str:
    if not text:
        return text
    text = text.translate(_PUNCT_MAP)
    # collapse spacing artifacts left by the substitutions above
    text = re.sub(r"[ \t]+,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


TONE_LABELS = {
    "professional": "professional and polished",
    "friendly": "warm and conversational",
    "direct": "straight to the point, no fluff",
    "urgent": "creates mild urgency without being pushy",
}

SERVICE_LABELS = {
    "web_design": "Custom Website Design & Development",
    "seo": "Search Engine Optimization (SEO)",
    "gbp_optimization": "Google Business Profile Optimization",
    "social_media": "Social Media Marketing",
    "full_package": "Full Digital Marketing Package (Web + SEO + GBP + Social)",
}

def _build_audit_summary(lead) -> dict:
    """
    Compact audit dict for the prompt. Issues are ordered by pitch priority
    (most painful first) and each carries a plain-language, customer-facing
    consequence so the model anchors on lost customers, not tech jargon.
    """
    data = {
        "name": lead.name,
        "niche": lead.niche,
        "location": f"{lead.city}, {lead.country}".rstrip(", "),
        "website": lead.website or None,
    }

    # Positive facts — opener material ("people clearly find you on Google")
    facts = []
    if lead.rating is not None and lead.review_count:
        facts.append(
            f"Google listing has {lead.review_count} reviews at {lead.rating} stars"
        )
    data["facts"] = facts

    # (issue, consequence) in strict pitch-priority order
    issues = []
    if not lead.has_website:
        issues.append({
            "issue": "No website",
            "consequence": (
                "people find them on Google Maps, then have nowhere to go, "
                "so they call a competitor that has a site"
            ),
        })
    else:
        if lead.pagespeed_score is not None and lead.pagespeed_score < 50:
            issues.append({
                "issue": f"Very slow website (speed score {lead.pagespeed_score}/100)",
                "consequence": (
                    "the site is painfully slow to open on a phone, "
                    "most visitors give up before it loads"
                ),
            })
        if not lead.has_ssl:
            issues.append({
                "issue": "Site served over plain HTTP",
                "consequence": (
                    "Chrome shows a 'Not Secure' warning next to their name "
                    "to every visitor"
                ),
            })
        if not lead.has_meta_title or not lead.has_meta_desc:
            issues.append({
                "issue": "Page title/description missing",
                "consequence": (
                    f"the site barely shows up when locals search "
                    f"'{lead.niche} near me', so searchers pick a competitor "
                    "they can actually find"
                ),
            })
        if not lead.has_schema:
            issues.append({
                "issue": "No structured data",
                "consequence": (
                    "Google can't show their hours, reviews or services in "
                    "search results the way it does for competitors"
                ),
            })

    if lead.rating is not None and lead.rating < 3.5:
        issues.append({
            "issue": f"Low rating ({lead.rating} stars)",
            "consequence": (
                "locals comparing options on the map pick the higher-rated "
                "competitor next to them"
            ),
        })
    if lead.review_count is not None and lead.review_count < 10:
        issues.append({
            "issue": f"Only {lead.review_count} Google reviews",
            "consequence": (
                "businesses with more reviews rank above them in the map "
                "results and look more trustworthy"
            ),
        })
    if not lead.has_social:
        issues.append({
            "issue": "No social media presence",
            "consequence": "customers who check for an active page find nothing",
        })

    if not issues:
        issues.append({
            "issue": "Solid basics, room to grow",
            "consequence": (
                "they're doing fine, the pitch angle is helping them pull "
                "ahead of local competitors, not fixing something broken"
            ),
        })

    data["primary_issue"] = issues[0]
    data["other_issues"] = issues[1:]
    return data

def generate_pitch(
    lead,
    tone: str = "professional",
    sender_name: str = "Alex",
    feedback: str = "",
    previous_pitch: str = "",
) -> str:
    tone_label = TONE_LABELS.get(tone, TONE_LABELS["professional"])
    audit_data = _build_audit_summary(lead)

    payload = {
        "lead": audit_data,
        "tone": tone_label,
        "sender_name": sender_name,
    }
    user_prompt = json.dumps(payload, indent=2)

    # Re-prompt mode: revise the previous draft per the user's instruction,
    # keeping every rule of the system prompt intact
    if feedback.strip() and previous_pitch.strip():
        user_prompt += (
            "\n\nPREVIOUS DRAFT:\n" + previous_pitch.strip()
            + "\n\nREVISION REQUEST from the sender: " + feedback.strip()
            + "\nRewrite the email applying this request. Keep all rules "
            "(structure, length, banned phrases, single primary issue)."
        )

    return _clean_copy(complete(
        system_prompt=PITCH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=2000,  # reasoning models think before the (short) answer
    ))

def generate_bulk_pitches(
    leads: list, tone: str = "professional", sender_name: str = "Alex"
) -> list[dict]:
    results = []
    tone_label = TONE_LABELS.get(tone, TONE_LABELS["professional"])
    
    # Chunk leads into batches of 5 to save tokens and improve latency
    chunk_size = 5
    for i in range(0, len(leads), chunk_size):
        chunk = leads[i:i + chunk_size]
        leads_data = []
        for lead in chunk:
            data = _build_audit_summary(lead)
            data["lead_id"] = lead.id  # Required for matching response
            leads_data.append(data)
            
        user_prompt = json.dumps({
            "leads": leads_data,
            "tone": tone_label,
            "sender_name": sender_name
        }, indent=2)
        
        try:
            # Requires JSON mode
            response_json = complete_json(
                system_prompt=BULK_PITCH_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.8,
            )
            parsed = json.loads(response_json)
            
            # Match pitches to leads safely (guaranteeing an entry for every lead)
            pitches_by_id = {
                p.get("lead_id"): p.get("pitch") 
                for p in parsed.get("pitches", []) 
                if p.get("lead_id") is not None
            }
            
            for lead in chunk:
                if lead.id in pitches_by_id:
                    results.append({
                        "lead_id": lead.id,
                        "pitch": _clean_copy(pitches_by_id[lead.id]),
                        "error": None
                    })
                else:
                    results.append({
                        "lead_id": lead.id,
                        "pitch": None,
                        "error": "AI failed to generate a pitch for this lead."
                    })
        except Exception as e:
            # If batch fails, mark all in chunk as failed
            for lead in chunk:
                results.append({"lead_id": lead.id, "pitch": None, "error": str(e)})
                
    return results


def generate_proposal(
    lead, sender_name: str = "Alex", service_type: str = "web_design", price_range: str = "$500–$2,000"
) -> str:
    """
    Generate a professional proposal for a lead based on audit data.
    Uses PROPOSAL_SYSTEM_PROMPT.
    """
    service_label = SERVICE_LABELS.get(service_type, SERVICE_LABELS["web_design"])
    audit_data = _build_audit_summary(lead)

    user_prompt = json.dumps({
        "lead": audit_data,
        "sender_name": sender_name,
        "service": service_label,
        "price_range": price_range,
    }, indent=2)

    return _clean_copy(complete(
        system_prompt=PROPOSAL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
    ))
