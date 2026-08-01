from rest_framework import serializers
from .models import Plan, PlanFeature, UserSubscription, UsageCounter, PaymentHistory


# ─────────────────────────────────────────────────────────────
#  Plan Serializers
# ─────────────────────────────────────────────────────────────


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = ("feature", "is_enabled")


class PlanSerializer(serializers.ModelSerializer):
    """
    Full plan detail — used in pricing page + subscription detail.
    stripe_price_id excluded — internal field, never expose to frontend.
    """

    features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = (
            "id",
            "name",
            "price_usd",
            "search_limit",
            "backlink_search_limit",
            "ai_pitch_limit",
            "email_send_limit",
            "saved_leads_limit",
            "ai_chat_limit",
            "bulk_search_limit",
            "team_seat_limit",
            "features",
        )
        # stripe_price_id intentionally excluded


# ─────────────────────────────────────────────────────────────
#  Subscription Serializers
# ─────────────────────────────────────────────────────────────


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = (
            "id",
            "plan",
            "status",
            "is_active",
            "current_period_end",
            "updated_at",
        )
        # stripe IDs excluded — internal only

    def get_is_active(self, obj):
        return obj.is_active()


class CheckoutSessionSerializer(serializers.Serializer):
    """POST /billing/checkout/ — frontend sends plan name."""

    plan_name = serializers.ChoiceField(choices=["pro", "max"])
    # View creates Stripe session and returns session_url


class CancelSubscriptionSerializer(serializers.Serializer):
    """POST /billing/cancel/ — confirmation flag required."""

    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("confirm must be true to cancel.")
        return value


# ─────────────────────────────────────────────────────────────
#  Usage Serializers
# ─────────────────────────────────────────────────────────────


class UsageCounterSerializer(serializers.ModelSerializer):
    limit = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    is_exhausted = serializers.SerializerMethodField()

    class Meta:
        model = UsageCounter
        fields = ("action", "count", "limit", "remaining", "is_exhausted", "reset_date")

    def _get_limit(self, obj):
        """Returns the raw plan limit for this action."""
        sub = getattr(obj.user, "subscription", None)
        if not sub:
            return 0
        limit_field = f"{obj.action}_limit"
        return getattr(sub.plan, limit_field, 0)

    def _get_effective_limit(self, obj):
        """
        Returns plan limit + bonus credits.
        Bonus credits come from plan upgrades mid-cycle (carry-over).
        """
        base = self._get_limit(obj)
        if base == -1:
            return -1  # unlimited — bonus irrelevant
        return base + obj.bonus

    def get_limit(self, obj):
        return self._get_effective_limit(obj)

    def get_remaining(self, obj):
        limit = self._get_effective_limit(obj)
        if limit == -1:
            return -1  # unlimited
        return max(0, limit - obj.count)

    def get_is_exhausted(self, obj):
        limit = self._get_effective_limit(obj)
        if limit == -1:
            return False
        return obj.count >= limit


class UsageStatsSerializer(serializers.Serializer):
    """
    GET /billing/usage/ — full usage summary for current period.
    View aggregates all UsageCounter rows and passes here.
    """

    usage = UsageCounterSerializer(many=True)
    reset_date = serializers.DateField()
    plan = serializers.CharField()  # plan name only


# ─────────────────────────────────────────────────────────────
#  Payment Serializers
# ─────────────────────────────────────────────────────────────


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = ("id", "amount", "currency", "status", "paid_at", "created_at")
        # stripe_invoice_id excluded — internal only
