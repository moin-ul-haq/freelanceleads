from django.contrib import admin
from .models import EmailAccount, Campaign, CampaignStep, CampaignLead, OutreachMessage, EmailReply


class CampaignStepInline(admin.TabularInline):
    model = CampaignStep
    extra = 0
    ordering = ("step_order",)


class CampaignLeadInline(admin.TabularInline):
    model = CampaignLead
    extra = 0
    readonly_fields = ("added_at",)


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ("email_address", "user", "provider", "created_at")
    list_select_related = ("user",)
    list_filter = ("provider",)
    search_fields = ("email_address", "user__email")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "email_account", "status", "created_at")
    list_select_related = ("user", "email_account")
    list_filter = ("status",)
    search_fields = ("name", "user__email")
    inlines = [CampaignStepInline, CampaignLeadInline]


@admin.register(CampaignStep)
class CampaignStepAdmin(admin.ModelAdmin):
    list_display = ("campaign", "step_order", "delay_days", "subject_template")
    list_select_related = ("campaign",)
    list_filter = ("campaign",)
    ordering = ("campaign", "step_order")


@admin.register(CampaignLead)
class CampaignLeadAdmin(admin.ModelAdmin):
    list_display = ("lead", "campaign", "current_step", "status", "next_step_date", "added_at")
    list_select_related = ("lead", "campaign")
    list_filter = ("status", "campaign")
    search_fields = ("lead__name", "campaign__name")


@admin.register(OutreachMessage)
class OutreachMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "campaign_lead", "sent_at", "opened_at")
    list_select_related = ("campaign_lead__lead", "campaign_lead__campaign")
    list_filter = ("sent_at",)
    search_fields = ("subject", "message_id")
    readonly_fields = ("sent_at",)


@admin.register(EmailReply)
class EmailReplyAdmin(admin.ModelAdmin):
    list_display = ("from_email", "subject", "received_at", "created_at")
    list_select_related = ("outreach_message",)
    search_fields = ("from_email", "subject")
    readonly_fields = ("created_at",)
