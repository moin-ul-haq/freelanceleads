# leads/serializers.py

from rest_framework import serializers
from .models import Lead, SavedLead
from services.scoring import get_score_label, get_score_reasons


# ─────────────────────────────────────────────────────────────
#  Lead Serializers
# ─────────────────────────────────────────────────────────────

class LeadSerializer(serializers.ModelSerializer):
    """
    Full lead detail — used in search results and lead detail endpoint.
    Includes computed score label and pitch reasons.
    """
    score_label  = serializers.SerializerMethodField()
    reasons      = serializers.SerializerMethodField()
    is_saved     = serializers.SerializerMethodField()



    class Meta:
        model  = Lead
        fields = (
            'id', 'place_id', 'name', 'niche',
            'city', 'state', 'country',
            'address', 'phone', 'website', 'email',
            'rating', 'review_count', 'gbp_status',
            'has_website', 'has_ssl', 'pagespeed_score',
            'has_meta_title', 'has_meta_desc', 'has_schema', 'has_social',
            'opportunity_score', 'score_label', 'reasons',
            'audit_done', 'status', 'is_saved',
            'latitude', 'longitude',
            'created_at', 'updated_at',
        )

    def get_score_label(self, obj):
        return get_score_label(obj.opportunity_score)

    def get_reasons(self, obj):
        return get_score_reasons(
            has_website     = obj.has_website,
            has_ssl         = obj.has_ssl,
            pagespeed_score = obj.pagespeed_score,
            rating          = obj.rating,
            review_count    = obj.review_count,
            has_meta_title  = obj.has_meta_title,
            has_meta_desc   = obj.has_meta_desc,
            has_schema      = obj.has_schema,
            has_social      = obj.has_social,
        )

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.saved_by.filter(user=request.user).exists()


class LeadMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight — used in saved leads list and pipeline.
    """
    score_label = serializers.SerializerMethodField()

    class Meta:
        model  = Lead
        fields = (
            'id', 'name', 'niche', 'city', 'country',
            'phone', 'website', 'rating', 'review_count',
            'opportunity_score', 'score_label', 'audit_done',
        )

    def get_score_label(self, obj):
        return get_score_label(obj.opportunity_score)


# ─────────────────────────────────────────────────────────────
#  Search Serializers
# ─────────────────────────────────────────────────────────────
class LeadSearchSerializer(serializers.Serializer):
    """POST /api/leads/search/ — input validation."""
    niche     = serializers.CharField(max_length=100)
    city      = serializers.CharField(max_length=100)
    country   = serializers.CharField(max_length=50, required=False, default='')
    refresh   = serializers.BooleanField(required=False, default=False)
    load_more = serializers.BooleanField(required=False, default=False)  # ✅ add this

    def validate_niche(self, value):
        return value.strip().lower()

    def validate_city(self, value):
        return value.strip().lower()

    def validate_country(self, value):
        return value.strip().lower()

# ─────────────────────────────────────────────────────────────
#  Saved Lead Serializers
# ─────────────────────────────────────────────────────────────

class SavedLeadSerializer(serializers.ModelSerializer):
    lead = LeadMinimalSerializer(read_only=True)

    class Meta:
        model  = SavedLead
        fields = ('id', 'lead', 'notes', 'saved_at')
        read_only_fields = ('saved_at',)


class SaveLeadSerializer(serializers.Serializer):
    """POST /api/leads/{id}/save/ — optional notes."""
    notes = serializers.CharField(required=False, allow_blank=True, default='')