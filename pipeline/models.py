from django.db import models
from django.conf import settings
from leads.models import Lead

class PipelineStage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pipeline_stages')
    name = models.CharField(max_length=100)
    system_key = models.CharField(max_length=50, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(max_length=7, default='#E2E8F0')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.user.email})"

class PipelineLead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pipeline_leads')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='pipeline_entries')
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name='leads')
    deal_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.lead.name} -> {self.stage.name}"

class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pipeline_activity_logs')
    pipeline_lead = models.ForeignKey(PipelineLead, on_delete=models.SET_NULL, null=True, related_name='logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.email} - {self.action} at {self.timestamp}"
