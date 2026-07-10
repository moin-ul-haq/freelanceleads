# ai_engine/serializers.py

from rest_framework import serializers


# ─────────────────────────────────────────────────────────────
#  Pitch Serializers
# ─────────────────────────────────────────────────────────────


class GeneratePitchSerializer(serializers.Serializer):
    """POST /api/ai/generate-pitch/"""

    lead_id = serializers.IntegerField()
    tone = serializers.ChoiceField(
        choices=["professional", "friendly", "direct", "urgent"],
        default="professional",
        required=False,
    )
    sender_name = serializers.CharField(max_length=50, default="Alex", required=False)


class BulkGeneratePitchSerializer(serializers.Serializer):
    """POST /api/ai/bulk-pitch/ — Max plan only"""

    lead_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=40,
    )
    tone = serializers.ChoiceField(
        choices=["professional", "friendly", "direct", "urgent"],
        default="professional",
        required=False,
    )
    sender_name = serializers.CharField(max_length=50, default="Alex", required=False)


# ─────────────────────────────────────────────────────────────
#  Chat Serializers
# ─────────────────────────────────────────────────────────────


class ChatMessageSerializer(serializers.Serializer):
    """Single message in chat history."""

    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()


class ChatSerializer(serializers.Serializer):
    """POST /api/ai/chat/"""

    message = serializers.CharField()  # latest user message
    history = ChatMessageSerializer(  # previous conversation
        many=True,
        required=False,
        default=[],
    )


# ─────────────────────────────────────────────────────────────
#  Proposal Serializers
# ─────────────────────────────────────────────────────────────


class GenerateProposalSerializer(serializers.Serializer):
    """POST /api/ai/generate-proposal/"""

    lead_id = serializers.IntegerField()
    sender_name = serializers.CharField(max_length=100, default="Alex", required=False)
    service_type = serializers.ChoiceField(
        choices=["web_design", "seo", "gbp_optimization", "social_media", "full_package"],
        default="web_design",
        required=False,
    )
    price_range = serializers.CharField(
        max_length=50, default="$500–$2,000", required=False
    )

