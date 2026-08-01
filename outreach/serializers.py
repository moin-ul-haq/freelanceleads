from rest_framework import serializers
from outreach.models import EmailAccount, Campaign, CampaignStep, CampaignLead, OutreachMessage, EmailReply
from leads.models import Lead

class EmailAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAccount
        fields = ['id', 'email_address', 'provider', 'daily_send_limit', 'smtp_host', 'smtp_port', 'smtp_username', 'imap_host', 'imap_port', 'imap_username', 'created_at']
        read_only_fields = ['user', 'created_at']

class CampaignStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignStep
        fields = ['id', 'step_order', 'delay_days', 'subject_template', 'body_template']

class CampaignLeadLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ["id", "name", "email", "phone", "website", "city", "niche"]


class CampaignLeadSerializer(serializers.ModelSerializer):
    lead = CampaignLeadLeadSerializer(read_only=True)

    class Meta:
        model = CampaignLead
        fields = [
            "id",
            "lead",
            "current_step",
            "next_step_date",
            "status",
            "added_at",
        ]


class CampaignSerializer(serializers.ModelSerializer):
    steps = CampaignStepSerializer(many=True, read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "email_account",
            "name",
            "status",
            "created_at",
            "updated_at",
            "steps",
            "enrolled_count",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_enrolled_count(self, obj):
        # Use annotation from queryset if available, fallback to DB count
        return getattr(obj, '_enrolled_count', obj.campaign_leads.count())

class EmailReplySerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    campaign_name = serializers.SerializerMethodField()

    def get_lead_name(self, obj):
        m = obj.outreach_message
        if m.campaign_lead:
            return m.campaign_lead.lead.name
        return m.lead.name if m.lead else None

    def get_campaign_name(self, obj):
        m = obj.outreach_message
        return m.campaign_lead.campaign.name if m.campaign_lead else "One-off email"
    
    class Meta:
        model = EmailReply
        fields = ['id', 'from_email', 'subject', 'body', 'received_at', 'lead_name', 'campaign_name']
