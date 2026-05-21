from celery import shared_task
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
    users_at_8am = []
    
    # 1. Identify which users are currently at 8am
    for user in User.objects.all():
        try:
            user_tz = pytz.timezone(user.timezone)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.UTC
            
        local_time = now_utc.astimezone(user_tz)
        if local_time.hour == 8:
            users_at_8am.append(user)

    if not users_at_8am:
        return "No users at 8am right now."

    # 2. Find pipeline leads for these users that need follow up today
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
        )
        
        for lead in leads_to_remind:
            # Here we would send the email. 
            # send_mail(...)
            
            # Log the activity
            ActivityLog.objects.create(
                user=user,
                pipeline_lead=lead,
                action="Follow-up reminder sent"
            )

    return f"Processed reminders for {len(users_at_8am)} users."
