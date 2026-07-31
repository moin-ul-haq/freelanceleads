from django.contrib import admin

from .models import GeneratedSite, SiteInquiry


@admin.register(GeneratedSite)
class GeneratedSiteAdmin(admin.ModelAdmin):
    list_display = ("business_name", "slug", "niche", "city", "user", "color_scheme", "tone", "created_at")
    search_fields = ("business_name", "slug", "city")
    list_filter = ("color_scheme", "tone")


@admin.register(SiteInquiry)
class SiteInquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "phone", "email", "created_at")
    search_fields = ("name", "email", "phone", "message")
    list_filter = ("site",)
    readonly_fields = ("site", "name", "email", "phone", "message", "created_at")
