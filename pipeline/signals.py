from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from pipeline.models import PipelineStage

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_pipeline_stages(sender, instance, created, **kwargs):
    if created:
        PipelineStage.objects.bulk_create([
            PipelineStage(user=instance, name="New", order=1, color="#E2E8F0"),
            PipelineStage(user=instance, name="Contacted", order=2, color="#FEF08A"),
            PipelineStage(user=instance, name="Interested", order=3, color="#93C5FD"),
            PipelineStage(user=instance, name="Proposal Sent", order=4, color="#C4B5FD"),
            PipelineStage(user=instance, name="Closed Won", system_key="closed_won", order=5, color="#86EFAC"),
            PipelineStage(user=instance, name="Closed Lost", system_key="closed_lost", order=6, color="#FCA5A5"),
        ])
