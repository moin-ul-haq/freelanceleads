from django.contrib import admin
from .models import Plan, PlanFeature, UserSubscription, UsageCounter, PaymentHistory


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_usd",
        "stripe_price_id",
        "search_limit",
        "ai_pitch_limit",
        "email_send_limit",
    )
    inlines = [PlanFeatureInline]


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ("plan", "feature", "is_enabled")
    list_filter = ("plan", "is_enabled")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end", "updated_at")
    list_select_related = ("user", "plan")
    list_filter = ("status", "plan")


@admin.register(UsageCounter)
class UsageCounterAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "count", "reset_date", "last_used")
    list_select_related = ("user",)
    list_filter = ("action",)


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "currency", "status", "paid_at", "created_at")
    list_select_related = ("user",)
    list_filter = ("status", "currency")
