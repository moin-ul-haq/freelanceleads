# Admin dashboard stats — rendered on the admin index page.

from datetime import timedelta

from django import template
from django.db.models import Count, Sum
from django.utils import timezone

register = template.Library()


@register.inclusion_tag("admin/fl_stats.html")
def fl_stats():
    from django.contrib.auth import get_user_model
    from billing.models import UserSubscription, UsageCounter, PaymentHistory
    from leads.models import Lead, SavedLead
    from pipeline.models import PipelineLead
    from outreach.models import Campaign, EmailReply
    from demosites.models import GeneratedSite, SiteInquiry
    from freelanceleads.quota_guard import get_period_start

    User = get_user_model()
    week_ago = timezone.now() - timedelta(days=7)
    period = get_period_start()

    plans = dict(
        UserSubscription.objects.values_list("plan__name").annotate(n=Count("id"))
    )
    usage = dict(
        UsageCounter.objects.filter(reset_date=period)
        .values_list("action")
        .annotate(total=Sum("count"))
    )
    emails_found = Lead.objects.exclude(email="").count()
    deliverable = Lead.objects.filter(email_status="deliverable").count()

    return {
        "boxes": [
            ("Users", User.objects.count(), f"+{User.objects.filter(created_at__gte=week_ago).count()} this week"),
            ("Paid plans", (plans.get("pro", 0) + plans.get("max", 0)), f"pro {plans.get('pro', 0)} · max {plans.get('max', 0)}"),
            ("Leads", Lead.objects.count(), f"{Lead.objects.filter(audit_done=True).count()} audited"),
            ("Emails found", emails_found, f"{deliverable} deliverable"),
            ("Searches (month)", usage.get("search", 0), "this billing period"),
            ("AI pitches (month)", usage.get("ai_pitch", 0), "incl. demo sites"),
            ("Saved leads", SavedLead.objects.count(), ""),
            ("Pipeline deals", PipelineLead.objects.count(), f"${PipelineLead.objects.aggregate(v=Sum('deal_value'))['v'] or 0:,.0f} value"),
            ("Campaigns", Campaign.objects.count(), f"{Campaign.objects.filter(status='active').count()} active"),
            ("Replies", EmailReply.objects.count(), ""),
            ("Demo sites", GeneratedSite.objects.count(), f"{SiteInquiry.objects.count()} inquiries"),
            ("Payments", PaymentHistory.objects.count(), f"${PaymentHistory.objects.aggregate(v=Sum('amount'))['v'] or 0:,.0f} collected"),
        ]
    }
