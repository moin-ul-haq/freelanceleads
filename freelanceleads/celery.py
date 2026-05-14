# freelanceleads/celery.py

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freelanceleads.settings')

app = Celery('freelanceleads')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks([
    'accounts',
    'billing',
    'leads',  # ← explicitly add leads
])

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')