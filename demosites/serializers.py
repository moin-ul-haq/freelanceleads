from django.conf import settings
from rest_framework import serializers

from .models import GeneratedSite


class GeneratedSiteSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedSite
        fields = (
            "id", "lead", "slug", "url", "business_name", "niche", "city",
            "content", "created_at", "updated_at",
        )

    def get_url(self, obj):
        return f"{settings.SITE_URL}/sites/{obj.slug}/"
