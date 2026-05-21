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

    score_label = serializers.SerializerMethodField()
    reasons = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            "id",
            "place_id",
            "name",
            "niche",
            "city",
            "state",
            "country",
            "address",
            "phone",
            "website",
            "email",
            "rating",
            "review_count",
            "gbp_status",
            "has_website",
            "has_ssl",
            "pagespeed_score",
            "has_meta_title",
            "has_meta_desc",
            "has_schema",
            "has_social",
            "opportunity_score",
            "score_label",
            "reasons",
            "audit_done",
            "status",
            "is_saved",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        )

    def get_score_label(self, obj):
        return get_score_label(obj.opportunity_score)

    def get_reasons(self, obj):
        return get_score_reasons(
            has_website=obj.has_website,
            has_ssl=obj.has_ssl,
            pagespeed_score=obj.pagespeed_score,
            rating=obj.rating,
            review_count=obj.review_count,
            has_meta_title=obj.has_meta_title,
            has_meta_desc=obj.has_meta_desc,
            has_schema=obj.has_schema,
            has_social=obj.has_social,
        )

    def get_is_saved(self, obj):
        saved_ids = self.context.get("saved_lead_ids")
        if saved_ids is not None:
            return obj.id in saved_ids
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.saved_by.filter(user=request.user).exists()


class LeadMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight — used in saved leads list and pipeline.
    """

    score_label = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            "id",
            "name",
            "niche",
            "city",
            "country",
            "phone",
            "website",
            "rating",
            "review_count",
            "opportunity_score",
            "score_label",
            "audit_done",
        )

    def get_score_label(self, obj):
        return get_score_label(obj.opportunity_score)


# ─────────────────────────────────────────────────────────────
#  Search Serializers
# ─────────────────────────────────────────────────────────────


class LeadSearchSerializer(serializers.Serializer):
    """
    POST /api/leads/search/ — input validation.

    Accepts either:
      - `city`   (single string)   → normalized to a one-element list internally
      - `cities` (list of strings, max 10)

    Exactly one of the two must be provided.
    """

    niche = serializers.CharField(max_length=100)

    # Single-city path (original)
    city = serializers.CharField(max_length=100, required=False, allow_blank=False)

    # Bulk-city path (new)
    cities = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        min_length=1,
        max_length=10,
    )

    country = serializers.CharField(max_length=50, required=False, default="")
    refresh = serializers.BooleanField(required=False, default=False)
    load_more = serializers.BooleanField(required=False, default=False)

    # ── field-level normalization ──────────────────────────────────────────

    def validate_niche(self, value):
        return value.strip().lower()

    def validate_city(self, value):
        return value.strip().lower()

    def validate_country(self, value):
        return value.strip().lower()

    def validate_cities(self, value):
        return [c.strip().lower() for c in value if c.strip()]

    # ── cross-field validation ─────────────────────────────────────────────

    def validate(self, attrs):
        city = attrs.get("city")
        cities = attrs.get("cities")

        if not city and not cities:
            raise serializers.ValidationError(
                "You must provide either 'city' (single string) or 'cities' (list of strings)."
            )

        if city and cities:
            raise serializers.ValidationError(
                "Provide either 'city' or 'cities', not both."
            )

        # Normalise both paths to a unified `cities` list so the view only
        # needs to deal with one shape.
        if city:
            attrs["cities"] = [city]

        # Remove the scalar field so downstream code never sees it.
        attrs.pop("city", None)

        return attrs


# ─────────────────────────────────────────────────────────────
#  Saved Lead Serializers
# ─────────────────────────────────────────────────────────────


class SavedLeadSerializer(serializers.ModelSerializer):
    lead = LeadMinimalSerializer(read_only=True)

    class Meta:
        model = SavedLead
        fields = ("id", "lead", "notes", "saved_at")
        read_only_fields = ("saved_at",)


class SaveLeadSerializer(serializers.Serializer):
    """POST /api/leads/{id}/save/ — optional notes."""

    notes = serializers.CharField(required=False, allow_blank=True, default="")
