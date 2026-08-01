# ai_engine/tools.py
#
# Function-calling tools for the AI assistant. Every tool is scoped to the
# requesting user — the executor never exposes another user's data. Results
# are compact dicts (serialized to JSON for the model).

from django.db.models import Count, Q, Sum


def _tool(name, description, params=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params or {},
                "required": required or [],
            },
        },
    }


TOOLS = [
    _tool(
        "list_saved_leads",
        "The user's saved leads (their working shortlist) with score, city, email status.",
    ),
    _tool(
        "find_lead",
        "Find a specific business/lead/client by (partial) name across the user's saved leads and pipeline. Returns full details: audit results, contact info, email deliverability, pipeline stage, campaigns it's enrolled in, demo site.",
        {"name": {"type": "string", "description": "Business name or part of it"}},
        ["name"],
    ),
    _tool(
        "get_pipeline",
        "The user's sales pipeline: every stage with its deals (business, value, follow-up date).",
    ),
    _tool(
        "list_campaigns",
        "All outreach campaigns with status and stats: enrolled leads, emails sent, opens, replies.",
    ),
    _tool(
        "get_campaign",
        "Detailed stats for one campaign by (partial) name: steps, emails sent/opened, reply rate, per-lead progress.",
        {"name": {"type": "string"}},
        ["name"],
    ),
    _tool(
        "get_inbox",
        "Recent replies received across all campaigns (sender, subject, snippet).",
    ),
    _tool(
        "get_usage_and_plan",
        "The user's plan and quota usage: searches, AI pitches, email sends — used/remaining.",
    ),
    _tool(
        "list_demo_sites",
        "The user's AI-generated demo websites with their public URLs and inquiry counts.",
    ),
    _tool(
        "get_site_inquiries",
        "Contact-form submissions received on the user's demo sites (name, phone, message).",
    ),
]


def execute_tool(user, name: str, args: dict):
    from demosites.models import GeneratedSite, SiteInquiry
    from leads.models import Lead, SavedLead
    from outreach.models import Campaign, CampaignLead, EmailReply, OutreachMessage
    from pipeline.models import PipelineLead

    if name == "list_saved_leads":
        rows = SavedLead.objects.filter(user=user).select_related("lead").order_by("-lead__opportunity_score")[:25]
        return [
            {
                "name": s.lead.name, "niche": s.lead.niche, "city": s.lead.city,
                "score": s.lead.opportunity_score, "email": s.lead.email or None,
                "email_status": s.lead.email_status, "phone": s.lead.phone or None,
            }
            for s in rows
        ] or "No saved leads yet."

    if name == "find_lead":
        q = (args.get("name") or "").strip()
        if not q:
            return "Provide a name to search."
        lead_ids = set(
            SavedLead.objects.filter(user=user, lead__name__icontains=q).values_list("lead_id", flat=True)
        ) | set(
            PipelineLead.objects.filter(user=user, lead__name__icontains=q).values_list("lead_id", flat=True)
        )
        leads = Lead.objects.filter(Q(id__in=lead_ids) | Q(name__icontains=q))[:3]
        if not leads:
            return f"No lead matching '{q}' found in your account."
        out = []
        for lead in leads:
            info = {
                "name": lead.name, "niche": lead.niche, "city": lead.city,
                "score": lead.opportunity_score, "rating": lead.rating,
                "reviews": lead.review_count, "website": lead.website or None,
                "email": lead.email or None, "email_status": lead.email_status,
                "phone": lead.phone or None,
                "audit": {
                    "has_website": lead.has_website, "has_ssl": lead.has_ssl,
                    "meta_tags": lead.has_meta_title and lead.has_meta_desc,
                    "schema": lead.has_schema, "social": lead.has_social,
                    "pagespeed": lead.pagespeed_score,
                },
            }
            pl = PipelineLead.objects.filter(user=user, lead=lead).select_related("stage").first()
            if pl:
                info["pipeline"] = {
                    "stage": pl.stage.name, "deal_value": float(pl.deal_value or 0),
                    "follow_up_date": str(pl.follow_up_date) if pl.follow_up_date else None,
                    "notes": pl.notes or None,
                }
            cls = CampaignLead.objects.filter(lead=lead, campaign__user=user).select_related("campaign")
            if cls:
                info["campaigns"] = [
                    {"campaign": c.campaign.name, "status": c.status, "current_step": c.current_step}
                    for c in cls
                ]
            site = GeneratedSite.objects.filter(user=user, lead=lead).first()
            if site:
                info["demo_site"] = {
                    "url": f"/sites/{site.slug}/",
                    "inquiries": site.inquiries.count(),
                }
            out.append(info)
        return out

    if name == "get_pipeline":
        rows = PipelineLead.objects.filter(user=user).select_related("stage", "lead").order_by("stage__order", "order")
        if not rows:
            return "Pipeline is empty."
        stages = {}
        for pl in rows:
            stages.setdefault(pl.stage.name, []).append({
                "business": pl.lead.name, "value": float(pl.deal_value or 0),
                "follow_up": str(pl.follow_up_date) if pl.follow_up_date else None,
            })
        return stages

    if name == "list_campaigns":
        camps = Campaign.objects.filter(user=user)
        if not camps:
            return "No campaigns yet."
        out = []
        for c in camps:
            leads_qs = CampaignLead.objects.filter(campaign=c)
            msgs = OutreachMessage.objects.filter(campaign_lead__campaign=c)
            out.append({
                "name": c.name, "status": c.status,
                "enrolled": leads_qs.count(),
                "emails_sent": msgs.count(),
                "opened": msgs.filter(opened_at__isnull=False).count(),
                "replies": EmailReply.objects.filter(outreach_message__campaign_lead__campaign=c).count(),
            })
        return out

    if name == "get_campaign":
        q = (args.get("name") or "").strip()
        c = Campaign.objects.filter(user=user, name__icontains=q).first()
        if not c:
            return f"No campaign matching '{q}'."
        leads_qs = CampaignLead.objects.filter(campaign=c)
        msgs = OutreachMessage.objects.filter(campaign_lead__campaign=c)
        sent = msgs.count()
        opened = msgs.filter(opened_at__isnull=False).count()
        replies = EmailReply.objects.filter(outreach_message__campaign_lead__campaign=c).count()
        return {
            "name": c.name, "status": c.status,
            "steps": [
                {"order": s.step_order, "delay_days": s.delay_days, "subject": s.subject_template}
                for s in c.steps.all().order_by("step_order")
            ],
            "enrolled": leads_qs.count(),
            "lead_status_counts": dict(leads_qs.values_list("status").annotate(n=Count("id"))),
            "emails_sent": sent,
            "opened": opened,
            "open_rate_pct": round(opened / sent * 100, 1) if sent else 0,
            "replies": replies,
        }

    if name == "get_inbox":
        replies = EmailReply.objects.filter(
            outreach_message__campaign_lead__campaign__user=user
        ).order_by("-received_at")[:10]
        return [
            {"from": r.from_email, "subject": r.subject, "snippet": r.body[:150],
             "received": str(r.received_at)[:16]}
            for r in replies
        ] or "Inbox is empty — no replies yet."

    if name == "get_usage_and_plan":
        from .context import build_user_snapshot
        snap = build_user_snapshot(user)
        return {"plan": snap.get("plan"), "quota": snap.get("quota")}

    if name == "list_demo_sites":
        sites = GeneratedSite.objects.filter(user=user)
        return [
            {"business": s.business_name, "url": f"/sites/{s.slug}/",
             "inquiries": s.inquiries.count(), "created": str(s.created_at)[:10]}
            for s in sites
        ] or "No demo sites generated yet."

    if name == "get_site_inquiries":
        inquiries = SiteInquiry.objects.filter(site__user=user).select_related("site").order_by("-created_at")[:10]
        return [
            {"site": i.site.business_name, "name": i.name, "phone": i.phone or None,
             "email": i.email or None, "message": i.message[:200], "at": str(i.created_at)[:16]}
            for i in inquiries
        ] or "No inquiries yet."

    return f"Unknown tool: {name}"
