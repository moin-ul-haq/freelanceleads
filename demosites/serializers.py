from django.conf import settings
from rest_framework import serializers

from .models import GeneratedSite


class GeneratedSiteSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    inquiry_count = serializers.SerializerMethodField()
    latest_inquiries = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedSite
        fields = (
            "id", "lead", "slug", "url", "business_name", "niche", "city",
            "color_scheme", "tone", "content", "inquiry_count",
            "latest_inquiries", "created_at", "updated_at",
        )

    def get_url(self, obj):
        return f"{settings.SITE_URL}/sites/{obj.slug}/"

    def get_inquiry_count(self, obj):
        return obj.inquiries.count()

    def get_latest_inquiries(self, obj):
        return [
            {
                "name": i.name, "email": i.email, "phone": i.phone,
                "message": i.message[:200], "created_at": i.created_at,
            }
            for i in obj.inquiries.all()[:5]
        ]
