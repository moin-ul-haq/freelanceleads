# ai_engine/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status



from freelanceleads.quota_guard import check, increment
from leads.models import Lead
from services.ai import chat as ai_chat
from ai_engine.pitch import generate_pitch, generate_bulk_pitches, generate_proposal
from ai_engine.prompts import CHAT_SYSTEM_PROMPT
from ai_engine.serializers import (
    GeneratePitchSerializer,
    BulkGeneratePitchSerializer,
    ChatSerializer,
    GenerateProposalSerializer,
)


# ─────────────────────────────────────────────────────────────
#  Pitch Generator
# ─────────────────────────────────────────────────────────────


class GeneratePitchView(APIView):
    """
    POST /api/ai/generate-pitch/

    Generates a personalized cold email pitch for a single lead.
    Uses lead audit data to reference specific problems found.

    Request:
        {
            "lead_id"     : 42,
            "tone"        : "friendly",
            "sender_name" : "Ahmad"
        }

    Response:
        {
            "pitch"   : "Subject: ...\n\nHi John, ...",
            "lead_id" : 42
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GeneratePitchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Quota check
        check(request.user, "ai_pitch")

        lead_id = serializer.validated_data["lead_id"]
        tone = serializer.validated_data["tone"]
        sender_name = (
            serializer.validated_data.get("sender_name")
            or request.user.first_name
            or request.user.username
        )

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            pitch = generate_pitch(
                lead,
                tone=tone,
                sender_name=sender_name,
                feedback=serializer.validated_data.get("feedback", ""),
                previous_pitch=serializer.validated_data.get("previous_pitch", ""),
            )
        except RuntimeError as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Increment quota only on success
        increment(request.user, "ai_pitch")

        return Response(
            {
                "pitch": pitch,
                "lead_id": lead_id,
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────
#  Bulk Pitch Generator
# ─────────────────────────────────────────────────────────────


class BulkGeneratePitchView(APIView):
    """
    POST /api/ai/bulk-pitch/

    Generates pitches for multiple leads at once.
    Max plan only. Runs synchronously — Celery task added later.

    Request:
        {
            "lead_ids"    : [1, 2, 3, ...],
            "tone"        : "professional",
            "sender_name" : "Ahmad"
        }

    Response:
        {
            "results": [
                {"lead_id": 1, "pitch": "Subject: ...", "error": null},
                {"lead_id": 2, "pitch": null, "error": "API error"},
            ],
            "success_count" : 2,
            "failed_count"  : 1
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Max plan only — safe access to subscription
        subscription = getattr(request.user, "subscription", None)
        if not subscription or subscription.plan.name not in ("max", "unlimited"):
            return Response(
                {
                    "error": "Bulk pitch generation is a Max plan feature. Please upgrade."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkGeneratePitchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lead_ids = serializer.validated_data["lead_ids"]
        tone = serializer.validated_data["tone"]
        sender_name = (
            serializer.validated_data.get("sender_name")
            or request.user.first_name
            or request.user.username
        )

        # 1. Fetch only leads that actually exist in the DB (Missing leads cost 0 tokens)
        leads_qs = Lead.objects.filter(id__in=lead_ids)
        existing_leads = list(leads_qs)
        existing_ids = {l.id for l in existing_leads}
        missing_ids = [lid for lid in lead_ids if lid not in existing_ids]

        # 2. Check if user has enough ai_pitch quota for the existing leads
        from freelanceleads.quota_guard import get_remaining_quota
        remaining = get_remaining_quota(request.user, "ai_pitch")
        
        quota_exceeded_ids = []
        if remaining != 999_999 and remaining < len(existing_leads):
            # Track which leads were dropped because quota ran out
            quota_exceeded_ids = [l.id for l in existing_leads[remaining:]]
            existing_leads = existing_leads[:remaining]

        # 3. Send ONLY valid, within-quota leads to the AI
        results = []
        if existing_leads:
            results = generate_bulk_pitches(existing_leads, tone=tone, sender_name=sender_name)

        # 4. Explicitly append missing leads to the response (proves we didn't send them to AI)
        for missing_id in missing_ids:
            results.append({
                "lead_id": missing_id,
                "pitch": None,
                "error": "Lead does not exist in the database (0 tokens used)."
            })

        # 5. Explicitly append quota-exceeded leads to the response
        for quota_id in quota_exceeded_ids:
            results.append({
                "lead_id": quota_id,
                "pitch": None,
                "error": "Insufficient AI pitch quota (0 tokens used)."
            })

        # Increment quota for each successful pitch
        success_count = sum(1 for r in results if r["error"] is None)
        for _ in range(success_count):
            increment(request.user, "ai_pitch")

        return Response(
            {
                "results": results,
                "success_count": success_count,
                "failed_count": len(results) - success_count,
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────
#  AI Chat Assistant
# ─────────────────────────────────────────────────────────────


class ChatView(APIView):
    """
    POST /api/ai/chat/

    Multi-turn AI chat assistant for pitch help, objection handling,
    pricing advice etc.

    Frontend sends full conversation history with each request.
    Claude/OpenAI is stateless — history passed every time.

    Request:
        {
            "message": "How do I respond if they say they already have a website?",
            "history": [
                {"role": "user",      "content": "Help me write a pitch for a plumber"},
                {"role": "assistant", "content": "Sure! Here's a pitch..."}
            ]
        }

    Response:
        {
            "reply"  : "Great question! Here's how to handle that objection...",
            "history": [...updated history including this exchange...]
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        import json as _json

        from .context import build_user_snapshot
        from .models import ChatMessage

        serializer = ChatSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Quota check
        check(request.user, "ai_chat")

        message = serializer.validated_data["message"]

        # Server-side history is the source of truth (survives refreshes/devices)
        stored = list(
            ChatMessage.objects.filter(user=request.user)
            .order_by("-created_at")[:12]
        )[::-1]

        # Ground the assistant in the user's real account data
        try:
            snapshot = build_user_snapshot(request.user)
        except Exception:
            snapshot = {}

        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": "ACCOUNT SNAPSHOT (live data):\n" + _json.dumps(snapshot),
            },
        ]
        for msg in stored:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": message})

        try:
            # Tool-calling: the assistant can query the user's real data
            # (leads, campaigns, pipeline, inbox, sites) before answering.
            from services.ai import chat_with_tools
            from .tools import TOOLS, execute_tool

            reply = chat_with_tools(
                messages=messages,
                tools=TOOLS,
                tool_executor=lambda name, args: execute_tool(request.user, name, args),
                max_tokens=900,  # reasoning models think before the (short) answer
            )
        except Exception as e:
            return Response({"error": f"AI API error: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

        from services.ai import clean_typography
        reply = clean_typography(reply)

        # Increment quota + persist the exchange
        increment(request.user, "ai_chat")
        ChatMessage.objects.create(user=request.user, role="user", content=message)
        ChatMessage.objects.create(user=request.user, role="assistant", content=reply)

        updated_history = [
            {"role": m.role, "content": m.content} for m in stored
        ] + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]

        return Response(
            {
                "reply": reply,
                "history": updated_history,
            },
            status=status.HTTP_200_OK,
        )


class ChatHistoryView(APIView):
    """
    GET    /api/ai/chat/history/ — persisted conversation (oldest first)
    DELETE /api/ai/chat/history/ — start a fresh conversation
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import ChatMessage

        messages = ChatMessage.objects.filter(user=request.user).order_by("created_at")
        return Response({
            "history": [{"role": m.role, "content": m.content} for m in messages[:200]]
        })

    def delete(self, request):
        from .models import ChatMessage

        ChatMessage.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────
#  Proposal Generator
# ─────────────────────────────────────────────────────────────


class GenerateProposalView(APIView):
    """
    POST /api/ai/generate-proposal/

    Generates a professional proposal for a lead based on audit data.
    Includes problem summary, proposed solution, deliverables, timeline, and pricing.

    Request:
        {
            "lead_id"      : 42,
            "sender_name"  : "Ahmad",
            "service_type" : "web_design",
            "price_range"  : "$500–$2,000"
        }

    Response:
        {
            "proposal" : "## Proposal for ...\n\n...",
            "lead_id"  : 42
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateProposalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Quota check — proposals count as AI pitch usage
        check(request.user, "ai_pitch")

        lead_id = serializer.validated_data["lead_id"]
        sender_name = (
            serializer.validated_data.get("sender_name")
            or request.user.first_name
            or request.user.username
        )
        service_type = serializer.validated_data["service_type"]
        price_range = serializer.validated_data["price_range"]

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            proposal = generate_proposal(
                lead,
                sender_name=sender_name,
                service_type=service_type,
                price_range=price_range,
            )
        except RuntimeError as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Increment quota only on success
        increment(request.user, "ai_pitch")

        return Response(
            {
                "proposal": proposal,
                "lead_id": lead_id,
            },
            status=status.HTTP_200_OK,
        )

