# core/quota_guard.py

from datetime import date

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from billing.models import UsageCounter


LIMIT_FIELD_MAP = {
    "search": "search_limit",
    "backlink_search": "backlink_search_limit",
    "ai_pitch": "ai_pitch_limit",
    "email_send": "email_send_limit",
    "ai_chat": "ai_chat_limit",
    "bulk_search": "bulk_search_limit",
}


def get_period_start() -> date:
    today = date.today()
    return today.replace(day=1)


def _get_plan_limit(user, action: str) -> int:
    """Returns base plan limit for action. -1 = unlimited."""
    limit_field = LIMIT_FIELD_MAP.get(action)
    if not limit_field:
        raise ValueError(f"Unknown action: {action}")
    try:
        return getattr(user.subscription.plan, limit_field, 0)
    except Exception:
        return 0


def _get_counter(user, action: str) -> UsageCounter:
    """Fetches or creates UsageCounter for current period."""
    counter, _ = UsageCounter.objects.get_or_create(
        user=user,
        action=action,
        reset_date=get_period_start(),
        defaults={"count": 0, "bonus": 0},
    )
    return counter


def _get_redis_key(user_id: int, action: str, period_start: date) -> str:
    return f"quota:{user_id}:{action}:{period_start}"


def get_effective_limit(user, action: str) -> int:
    """
    Returns total effective limit including bonus credits.
    -1 means unlimited — bonus is ignored in that case.
    """
    base_limit = _get_plan_limit(user, action)
    if base_limit == -1:
        return -1  # unlimited — bonus irrelevant

    counter = _get_counter(user, action)
    return base_limit + counter.bonus


def get_remaining_quota(user, action: str) -> int:
    """
    Returns the exact number of remaining credits for an action.
    Returns 999_999 for unlimited plans.
    """
    base_limit = _get_plan_limit(user, action)
    if base_limit == -1:
        return 999_999

    counter = _get_counter(user, action)
    effective_limit = base_limit + counter.bonus
    
    period_start = get_period_start()
    redis_key = _get_redis_key(user.id, action, period_start)
    cached_count = cache.get(redis_key)
    
    if cached_count is None:
        cached_count = counter.count
        
    return max(0, effective_limit - cached_count)


def check(user, action: str) -> None:
    """
    Checks if user has remaining quota.
    Raises PermissionDenied (HTTP 403) if exhausted.
    """
    base_limit = _get_plan_limit(user, action)

    if base_limit == -1:
        return  # unlimited

    # Single DB call — reused for both count and bonus
    counter = _get_counter(user, action)
    period_start = get_period_start()
    redis_key = _get_redis_key(user.id, action, period_start)
    cached_count = cache.get(redis_key)

    if cached_count is None:
        cached_count = counter.count
        cache.set(redis_key, cached_count, timeout=_seconds_until_month_end())

    effective_limit = base_limit + counter.bonus

    if cached_count >= effective_limit:
        raise PermissionDenied(
            {
                "error": "Quota limit reached.",
                "action": action,
                "limit": effective_limit,
                "upgrade_url": "/api/billing/checkout/",
            }
        )


def increment(user, action: str) -> None:
    period_start = get_period_start()
    redis_key = _get_redis_key(user.id, action, period_start)

    counter = _get_counter(user, action)
    UsageCounter.objects.filter(pk=counter.pk).update(
        count=F("count") + 1,
        last_used=timezone.now(),
    )
    new_count = counter.count + 1

    if cache.get(redis_key) is None:
        cache.set(redis_key, new_count, timeout=_seconds_until_month_end())
    else:
        cache.incr(redis_key)


def carry_over_credits(user, old_plan, new_plan) -> None:
    """
    Calculates remaining credits on old plan and adds them as bonus
    on new plan's UsageCounter rows.
    Called before plan is switched.
    """
    period_start = get_period_start()

    for action, limit_field in LIMIT_FIELD_MAP.items():
        old_limit = getattr(old_plan, limit_field, 0)

        # Skip if old plan was unlimited — can't carry infinity
        if old_limit == -1:
            continue

        new_limit = getattr(new_plan, limit_field, 0)

        # Skip if new plan is unlimited — bonus irrelevant
        if new_limit == -1:
            continue

        counter, _ = UsageCounter.objects.get_or_create(
            user=user,
            action=action,
            reset_date=period_start,
            defaults={"count": 0, "bonus": 0},
        )

        remaining = max(0, (old_limit + counter.bonus) - counter.count)
        counter.bonus += remaining
        counter.save(update_fields=["bonus"])


def _seconds_until_month_end() -> int:
    from datetime import datetime
    import calendar

    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = datetime(today.year, today.month, last_day, 23, 59, 59)
    delta = month_end - datetime.now()
    return max(int(delta.total_seconds()), 1)
