# leads/admin.py

from django.contrib import admin
from .models import Lead, SavedLead, SearchCache


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "niche",
        "city",
        "state",
        "country",
        "opportunity_score",
        "audit_done",
        "created_at",
    )
    list_filter = ("niche", "country", "audit_done", "has_ssl", "has_website")
    search_fields = ("name", "city", "state", "phone", "email", "website")
    ordering = ("-opportunity_score",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SavedLead)
class SavedLeadAdmin(admin.ModelAdmin):
    list_display = ("user", "lead", "saved_at")
    search_fields = ("user__email", "lead__name")


@admin.register(SearchCache)
class SearchCacheAdmin(admin.ModelAdmin):
    list_display = (
        "cache_key",
        "niche",
        "city",
        "state",
        "total_results",
        "is_exhausted",
        "last_fetched",
    )
    search_fields = ("cache_key", "niche", "city")
    readonly_fields = ("created_at",)
