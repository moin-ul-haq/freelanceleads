from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Team, TeamSeat


class TeamSeatInline(admin.TabularInline):
    model = TeamSeat
    extra = 1


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    inlines = [TeamSeatInline]


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "first_name", "current_plan_name", "is_staff", "created_at")
    list_filter = UserAdmin.list_filter + ("subscription__plan__name",)
    search_fields = ("email", "username", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (("Meta", {"fields": ("created_at",)}),)
    readonly_fields = ("created_at",)
    actions = ("grant_unlimited", "revoke_to_free")

    @admin.display(description="Plan", ordering="subscription__plan__name")
    def current_plan_name(self, obj):
        sub = getattr(obj, "subscription", None)
        return sub.plan.name if sub else "-"

    def _set_plan(self, request, queryset, plan_name):
        from billing.models import Plan, UserSubscription

        plan = Plan.objects.filter(name=plan_name).first()
        if not plan:
            self.message_user(request, f"Plan '{plan_name}' not found — run seed_plans.", level="error")
            return
        changed = 0
        for user in queryset:
            sub, _ = UserSubscription.objects.get_or_create(user=user, defaults={"plan": plan})
            sub.plan = plan
            sub.status = "active"
            sub.save(update_fields=["plan", "status"])
            changed += 1
        # Quota checks read cached counts — clearing makes new limits apply instantly
        from django.core.cache import cache
        cache.clear()
        self.message_user(request, f"{changed} user(s) moved to the {plan_name} plan.")

    @admin.action(description="Grant UNLIMITED plan (no quotas)")
    def grant_unlimited(self, request, queryset):
        self._set_plan(request, queryset, "unlimited")

    @admin.action(description="Revoke — back to free plan")
    def revoke_to_free(self, request, queryset):
        self._set_plan(request, queryset, "free")


@admin.register(TeamSeat)
class TeamSeatAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "role", "joined_at")
    list_filter = ("role",)
