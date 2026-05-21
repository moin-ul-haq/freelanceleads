# accounts/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
from billing.models import UserSubscription, Plan

User = get_user_model()


@receiver(post_save, sender=User)
def create_free_subscription(sender, instance, created, **kwargs):
    """
    Automatically creates a free subscription when a new user registers.
    Fires only on creation, not on every user save.
    """
    if not created:
        return

    free_plan = Plan.objects.filter(name="free").first()

    if not free_plan:
        # Free plan not seeded in DB yet — skip silently
        # Run: python manage.py seed_plans to fix this
        return

    UserSubscription.objects.create(
        user=instance,
        plan=free_plan,
        status="active",
        current_period_end=timezone.now() + relativedelta(months=1),
    )
