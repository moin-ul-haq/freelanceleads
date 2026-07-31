from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import pytz
from django.contrib.auth import get_user_model
from pipeline.models import PipelineLead, ActivityLog

User = get_user_model()

@shared_task
def send_hourly_follow_up_reminders():
    """
    Runs every hour. Finds users whose current local time is 8 AM.
    For those users, finds all PipelineLeads with a follow_up_date of today
    and sends a reminder.
    """
    now_utc = timezone.now()

    # 1. Compute which timezones are currently at 8am — avoid loading all users
    timezones_at_8am = []
    for tz_name in pytz.common_timezones:
        try:
            tz = pytz.timezone(tz_name)
            if now_utc.astimezone(tz).hour == 8:
                timezones_at_8am.append(tz_name)
        except Exception:
            continue

    if not timezones_at_8am:
        return "No timezones at 8am right now."

    # 2. Single query: fetch only users in matching timezones
    users_at_8am = list(User.objects.filter(timezone__in=timezones_at_8am))

    if not users_at_8am:
        return "No users at 8am right now."

    # 3. Find pipeline leads for these users that need follow up today
    for user in users_at_8am:
        try:
            user_tz = pytz.timezone(user.timezone)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.UTC
            
        local_today = now_utc.astimezone(user_tz).date()
        
        leads_to_remind = PipelineLead.objects.filter(
            user=user,
            follow_up_date=local_today
        ).exclude(
            stage__system_key__in=['closed_won', 'closed_lost']
        ).select_related('lead', 'stage')
        
        leads_to_remind = list(leads_to_remind)
        if not leads_to_remind:
            continue

        lines = []
        for pl in leads_to_remind:
            business = pl.lead.name if pl.lead else "Unknown business"
            stage = pl.stage.name if pl.stage else "—"
            deal = f" (deal: ${pl.deal_value})" if pl.deal_value else ""
            lines.append(f"- {business} — stage: {stage}{deal}")

        try:
            send_mail(
                subject=f"FreelanceLeads: {len(leads_to_remind)} follow-up(s) due today",
                message=(
                    "You have follow-ups scheduled for today:\n\n"
                    + "\n".join(lines)
                    + f"\n\nOpen your pipeline: {settings.FRONTEND_URL}/pipeline"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            # Don't log "sent" if the email failed — try again next run
            continue

        for pl in leads_to_remind:
            ActivityLog.objects.create(
                user=user,
                pipeline_lead=pl,
                action="Follow-up reminder sent"
            )

    return f"Processed reminders for {len(users_at_8am)} users."
