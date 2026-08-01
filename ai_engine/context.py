# ai_engine/context.py
#
# Builds a compact, factual snapshot of the user's account for the AI
# assistant, so its advice is grounded in their real data instead of
# generic tips. Keep it small — this rides along on every chat call.

from django.db.models import Count, Sum

from freelanceleads.quota_guard import get_effective_limit, get_remaining_quota


def build_user_snapshot(user) -> dict:
    from billing.models import UsageCounter
    from leads.models import SavedLead
    from pipeline.models import PipelineLead, PipelineStage
    from outreach.models import Campaign, EmailReply
    from demosites.models import GeneratedSite, SiteInquiry
    from freelanceleads.quota_guard import get_period_start

    snapshot = {
        "name": user.first_name or user.username,
        "plan": getattr(getattr(user, "subscription", None), "plan", None)
        and user.subscription.plan.name or "free",
    }

    # Quotas — used vs limit for the actions that matter
    usage = {}
    counters = {
        c.action: c.count
        for c in UsageCounter.objects.filter(user=user, reset_date=get_period_start())
    }
    for action in ("search", "ai_pitch", "email_send"):
        limit = get_effective_limit(user, action)
        usage[action] = {
            "used": counters.get(action, 0),
            "limit": "unlimited" if limit == -1 else limit,
            "remaining": get_remaining_quota(user, action),
        }
    snapshot["quota"] = usage

    # Saved leads — the working set
    saved = SavedLead.objects.filter(user=user).select_related("lead")
    snapshot["saved_leads_count"] = saved.count()
    hot = [
        {
            "name": s.lead.name,
            "niche": s.lead.niche,
            "city": s.lead.city,
            "score": s.lead.opportunity_score,
            "email_found": bool(s.lead.email),
            "email_status": s.lead.email_status,
        }
        for s in saved.order_by("-lead__opportunity_score")[:5]
    ]
    if hot:
        snapshot["top_saved_leads"] = hot

    # Pipeline — deals by stage + money
    stages = (
        PipelineLead.objects.filter(user=user)
        .values("stage__name")
        .annotate(n=Count("id"), value=Sum("deal_value"))
    )
    if stages:
        snapshot["pipeline"] = {
            s["stage__name"]: {"deals": s["n"], "value": float(s["value"] or 0)}
            for s in stages
        }
        won = PipelineLead.objects.filter(
            user=user, stage__system_key="closed_won"
        ).aggregate(v=Sum("deal_value"))["v"]
        snapshot["pipeline"]["total_won_value"] = float(won or 0)
    followups = PipelineLead.objects.filter(
        user=user, follow_up_date__isnull=False
    ).exclude(stage__system_key__in=["closed_won", "closed_lost"]).count()
    if followups:
        snapshot["pending_follow_ups"] = followups

    # Outreach + demo sites
    campaigns = Campaign.objects.filter(user=user)
    if campaigns.exists():
        snapshot["campaigns"] = [
            {"name": c.name, "status": c.status} for c in campaigns[:5]
        ]
    replies = EmailReply.objects.filter(
        outreach_message__campaign_lead__campaign__user=user
    ).count()
    if replies:
        snapshot["campaign_replies"] = replies

    sites = GeneratedSite.objects.filter(user=user)
    if sites.exists():
        snapshot["demo_sites"] = sites.count()
        inquiries = SiteInquiry.objects.filter(site__user=user).count()
        snapshot["demo_site_inquiries"] = inquiries

    return snapshot
