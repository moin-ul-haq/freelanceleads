from django.db import models
from django.conf import settings


PLAN_CHOICES = [("free", "Free"), ("pro", "Pro"), ("max", "Max"), ("unlimited", "Unlimited")]


class Plan(models.Model):
    """Subscription tier defining pricing and usage limits."""

    name = models.CharField(max_length=10, choices=PLAN_CHOICES, unique=True)
    price_usd = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    stripe_price_id = models.CharField(max_length=100, blank=True)

    # Numeric limits (-1 = unlimited)
    search_limit = models.IntegerField(default=0)
    backlink_search_limit = models.IntegerField(default=0)
    ai_pitch_limit = models.IntegerField(default=0)
    email_send_limit = models.IntegerField(default=0)
    saved_leads_limit = models.IntegerField(default=0)
    ai_chat_limit = models.IntegerField(default=0)
    bulk_search_limit = models.IntegerField(default=0)
    team_seat_limit = models.IntegerField(default=1)  # Free=1, Pro=1, Max=3

    # Hidden plans (e.g. "unlimited") are assignable only via the admin
    is_public = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} — ${self.price_usd}"


class PlanFeature(models.Model):
    """Boolean feature flag tied to a plan (e.g. PDF reports, CRM access)."""

    FEATURE_CHOICES = [
        ("website_generation", "Website Generation"),
        ("pdf_audit_reports", "PDF Audit Reports"),
        ("ai_lead_scoring", "AI Lead Scoring"),
        ("pipeline_crm", "Pipeline CRM"),
        ("follow_up_sequences", "Follow-up Sequences"),
        ("proposals_case_studies", "Proposals & Case Studies"),
        ("competitor_comparison", "Competitor Comparison"),
        ("niche_scanner", "Niche Scanner"),
        ("csv_export_import", "CSV Export & Import"),
        ("bulk_pitch_generation", "Bulk Pitch Generation"),
        ("daily_email_automations", "Daily Email Automations"),
        ("review_response_templates", "Review Response Templates"),
        ("priority_support", "Priority Support"),
    ]

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("plan", "feature")

    def __str__(self):
        return f"{'✅' if self.is_enabled else '❌'} {self.plan.name} — {self.feature}"


class UserSubscription(models.Model):
    """Tracks a user's active Stripe subscription and billing status."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("cancelled", "Cancelled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.plan.name} — {self.status}"

    def is_active(self):
        """Check if the subscription is currently usable."""
        return self.status in ("active", "trialing")


class UsageCounter(models.Model):
    ACTION_CHOICES = [
        ("search", "Search"),
        ("backlink_search", "Backlink Search"),
        ("ai_pitch", "AI Pitch"),
        ("email_send", "Email Send"),
        ("ai_chat", "AI Chat"),
        ("bulk_search", "Bulk Search"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    count = models.IntegerField(default=0)
    bonus = models.IntegerField(
        default=0
    )  # carried over credits from previous plan or credit packs
    reset_date = models.DateField()
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "action", "reset_date")
        indexes = [
            models.Index(fields=["user", "action", "reset_date"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.action}: {self.count} ({self.reset_date})"


class PaymentHistory(models.Model):
    """Immutable log of all Stripe invoice payments for audit and display."""

    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    stripe_invoice_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.amount} {self.currency} — {self.status}"


class StripeWebhookEvent(models.Model):
    """Stores processed Stripe event IDs to guarantee webhook idempotency."""

    stripe_event_id = models.CharField(max_length=100, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} — {self.stripe_event_id}"
