# ═══════════════════════════════════════════════════════════════
#  ai_engine/pitch.py
#  Pitch email generation logic.
# ═══════════════════════════════════════════════════════════════

import json
from services.ai import complete, complete_json
from ai_engine.prompts import PITCH_SYSTEM_PROMPT, BULK_PITCH_SYSTEM_PROMPT, PROPOSAL_SYSTEM_PROMPT

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
    Returns a compact dictionary of audit data to minimize tokens.
    """
    data = {
        "name": lead.name,
        "niche": lead.niche,
        "location": f"{lead.city}, {lead.country}",
        "website": lead.website or None,
    }
    
    issues = []
    if not lead.has_website:
        issues.append("No website")
    else:
        if not lead.has_ssl: issues.append("No SSL")
        if lead.pagespeed_score is not None and lead.pagespeed_score < 50:
            issues.append(f"PageSpeed: {lead.pagespeed_score}")
        if not lead.has_meta_title or not lead.has_meta_desc:
            issues.append("Missing meta tags")
        if not lead.has_schema: issues.append("No schema")
        
    if lead.rating is not None and lead.rating < 3.5:
        issues.append(f"Rating: {lead.rating}")
    if lead.review_count is not None and lead.review_count < 10:
        issues.append(f"Reviews: {lead.review_count}")
    if not lead.has_social:
        issues.append("No social media")
        
    if not issues:
        issues.append("General online presence improvement needed")
        
    data["issues"] = issues
    return data

def generate_pitch(lead, tone: str = "professional", sender_name: str = "Alex") -> str:
    tone_label = TONE_LABELS.get(tone, TONE_LABELS["professional"])
    audit_data = _build_audit_summary(lead)
    
    user_prompt = json.dumps({
        "lead": audit_data,
        "tone": tone_label,
        "sender_name": sender_name
    }, indent=2)

    return complete(
        system_prompt=PITCH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8,
    )

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
                        "pitch": pitches_by_id[lead.id],
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

    return complete(
        system_prompt=PROPOSAL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,
    )