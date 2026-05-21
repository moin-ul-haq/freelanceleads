from rest_framework import serializers
from pipeline.models import PipelineStage, PipelineLead, ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'action', 'timestamp']

class PipelineLeadSerializer(serializers.ModelSerializer):
    logs = ActivityLogSerializer(many=True, read_only=True)
    lead_details = serializers.SerializerMethodField()

    class Meta:
        model = PipelineLead
        fields = ['id', 'lead', 'lead_details', 'stage', 'deal_value', 'follow_up_date', 'notes', 'order', 'created_at', 'updated_at', 'logs']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_lead_details(self, obj):
        return {
            'id': obj.lead.id,
            'name': obj.lead.name,
            'niche': obj.lead.niche,
            'city': obj.lead.city,
            'country': obj.lead.country,
            'website': obj.lead.website,
            'rating': obj.lead.rating,
        }

class PipelineStageSerializer(serializers.ModelSerializer):
    leads = PipelineLeadSerializer(many=True, read_only=True)

    class Meta:
        model = PipelineStage
        fields = ['id', 'name', 'system_key', 'order', 'color', 'leads']
        read_only_fields = ['user', 'system_key']
