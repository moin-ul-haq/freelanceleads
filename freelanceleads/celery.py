# freelanceleads/celery.py

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freelanceleads.settings")

app = Celery("freelanceleads")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(
    [
        "accounts",
        "billing",
        "leads",
        "ai_engine",
        "pipeline",
        "outreach",
        "services",
    ]
)

from celery.schedules import crontab

app.conf.beat_schedule = {
    'send-hourly-follow-up-reminders': {
        'task': 'pipeline.tasks.send_hourly_follow_up_reminders',
        'schedule': crontab(minute=0), # Top of every hour
    },
    'process-outreach-campaigns': {
        'task': 'outreach.tasks.process_outreach_campaigns',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'poll-imap-replies': {
        'task': 'outreach.tasks.poll_imap_replies',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
