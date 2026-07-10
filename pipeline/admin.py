from django.contrib import admin
from pipeline.models import PipelineStage, PipelineLead, ActivityLog

@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'system_key', 'order', 'color')
    list_select_related = ('user',)
    list_filter = ('user', 'system_key')
    search_fields = ('name', 'user__email')
    ordering = ('user', 'order')

@admin.register(PipelineLead)
class PipelineLeadAdmin(admin.ModelAdmin):
    list_display = ('lead', 'user', 'stage', 'deal_value', 'follow_up_date', 'order')
    list_select_related = ('lead', 'user', 'stage')
    list_filter = ('user', 'stage', 'follow_up_date')
    search_fields = ('lead__name', 'user__email', 'notes')
    ordering = ('user', 'stage', 'order')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'pipeline_lead', 'timestamp')
    list_select_related = ('user', 'pipeline_lead')
    list_filter = ('user', 'timestamp')
    search_fields = ('action', 'user__email')
    ordering = ('-timestamp',)
