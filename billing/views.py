# billing/views.py
#
# API views for the billing module:
#
#   1. PlanListView          — GET    /api/billing/plans/
#   2. PlanDetailView        — GET    /api/billing/plans/<id>/
#   3. SubscriptionDetailView— GET    /api/billing/subscription/
#   4. CheckoutSessionView   — POST   /api/billing/checkout/
#   5. StripeWebhookView     — POST   /api/billing/webhook/
#   6. UsageStatsView        — GET    /api/billing/usage/
#   7. CancelSubscriptionView— POST   /api/billing/cancel/

import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Plan,
    UserSubscription,
    StripeWebhookEvent,
    PaymentHistory,
    UsageCounter,
)
from .serializers import (
    PlanSerializer,
    UserSubscriptionSerializer,
    CheckoutSessionSerializer,
    UsageStatsSerializer,
    CancelSubscriptionSerializer,
)

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
PLAN_HIERARCHY = ["free", "pro", "max"]


# ───────────────────────────────────────────────────────────────
#  Helper — safe subscription access
# ───────────────────────────────────────────────────────────────


def _get_subscription(user):
    """
    Safely fetch the user's subscription.
    Returns None if no subscription exists (e.g. signal failed at registration).
    """
    try:
        return user.subscription
    except UserSubscription.DoesNotExist:
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  Plan Views (public)
# ═══════════════════════════════════════════════════════════════


class PlanListView(ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]


class PlanDetailView(RetrieveAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]


# ═══════════════════════════════════════════════════════════════
#  Subscription Detail
# ═══════════════════════════════════════════════════════════════


class SubscriptionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = _get_subscription(request.user)
        if not subscription:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
#  Checkout — Create Stripe Session for Upgrade
# ═══════════════════════════════════════════════════════════════


class CheckoutSessionView(APIView):
    """
    POST /api/billing/checkout/

    Creates a Stripe Checkout Session for plan upgrades.

    IMPORTANT: The old subscription is NOT cancelled here. It is cancelled
    inside the `_handle_checkout_completed` webhook, AFTER payment succeeds.
    This prevents the user from losing their plan if they abandon checkout.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSessionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan_name = serializer.validated_data["plan_name"]

        # Fetch target plan from DB
        try:
            plan = Plan.objects.get(name=plan_name)
        except Plan.DoesNotExist:
            return Response(
                {"error": "Plan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not plan.stripe_price_id:
            return Response(
                {"error": "Plan is not configured for payments."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user's current subscription
        subscription = _get_subscription(request.user)
        if not subscription:
            return Response(
                {"error": "No subscription found. Please contact support."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_plan_name = subscription.plan.name

        # Block downgrade or same plan
        current_rank = (
            PLAN_HIERARCHY.index(current_plan_name)
            if current_plan_name in PLAN_HIERARCHY
            else 0
        )
        target_rank = (
            PLAN_HIERARCHY.index(plan_name) if plan_name in PLAN_HIERARCHY else 0
        )

        if target_rank <= current_rank:
            return Response(
                {
                    "error": f"You are already on the {current_plan_name} plan. You can only upgrade to a higher plan."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create or reuse Stripe customer
        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={"user_id": request.user.id},
            )
            subscription.stripe_customer_id = customer.id
            subscription.save(update_fields=["stripe_customer_id"])

        # Build metadata — include old plan so webhook can carry over credits
        session_metadata = {
            "user_id": request.user.id,
            "plan_name": plan_name,
            "old_plan_name": current_plan_name,
        }

        # NOTE: We do NOT cancel the old Stripe subscription here.
        # It is cancelled in _handle_checkout_completed after payment succeeds.
        # This prevents the user from losing access if they abandon checkout.

        # Create Stripe Checkout Session for new plan
        session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=settings.STRIPE_SUCCESS_URL
            + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.STRIPE_CANCEL_URL,
            metadata=session_metadata,
        )

        return Response({"session_url": session.url}, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
#  Stripe Webhook — Processes incoming Stripe events
# ═══════════════════════════════════════════════════════════════


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/billing/webhook/

    Receives and processes Stripe webhook events.
    Uses atomic transactions to prevent partial state updates.
    Uses idempotency checks to prevent double-processing.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        # Verify webhook signature — reject tampered requests
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(
                {"error": "Invalid signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotency check — ignore already-processed events
        if StripeWebhookEvent.objects.filter(stripe_event_id=event["id"]).exists():
            return Response(
                {"status": "already processed"},
                status=status.HTTP_200_OK,
            )

        # Route event to correct handler
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event["type"])

        # Wrap handler + idempotency record in a transaction.
        # If the handler crashes, the event is NOT marked as processed,
        # so Stripe will retry. But partial state changes are rolled back.
        try:
            with transaction.atomic():
                if handler:
                    handler(event["data"]["object"])

                # Mark event as processed (inside the transaction)
                StripeWebhookEvent.objects.create(
                    stripe_event_id=event["id"],
                    event_type=event["type"],
                )
        except Exception:
            logger.exception(
                "Stripe webhook handler failed for event %s (%s)",
                event["id"],
                event["type"],
            )
            return Response(
                {"error": "Webhook handler failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    # ── Event Handlers ────────────────────────────────────────

    def _handle_checkout_completed(self, session):
        """
        User completed checkout — upgrade their plan.

        Steps:
            1. Retrieve full session from Stripe (metadata may be partial).
            2. Cancel the OLD Stripe subscription (safe — payment already succeeded).
            3. Carry over remaining credits from old plan.
            4. Update local subscription record with new plan.
        """
        from freelanceleads.quota_guard import carry_over_credits

        try:
            session = stripe.checkout.Session.retrieve(session["id"])
        except stripe.error.StripeError as e:
            logger.error("Could not retrieve Stripe session: %s", e)
            return

        try:
            user_id = int(session.metadata.user_id)
            plan_name = session.metadata.plan_name
            old_plan_name = getattr(session.metadata, "old_plan_name", "free")
        except (AttributeError, TypeError, ValueError) as e:
            logger.error("Missing or invalid session metadata: %s", e)
            return

        try:
            subscription = UserSubscription.objects.select_related("plan").get(
                user_id=user_id
            )
            new_plan = Plan.objects.get(name=plan_name)
            old_plan = Plan.objects.get(name=old_plan_name)
        except (UserSubscription.DoesNotExist, Plan.DoesNotExist) as e:
            logger.error("Subscription or plan not found: %s", e)
            return

        # Cancel the old Stripe subscription NOW (after payment succeeded).
        # This is safe — the user already paid for the new plan.
        if old_plan_name != "free" and subscription.stripe_subscription_id:
            try:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
            except stripe.error.StripeError as e:
                logger.warning(
                    "Could not cancel old subscription %s: %s",
                    subscription.stripe_subscription_id,
                    e,
                )
                # Continue anyway — old subscription may have already expired

        # Carry over remaining credits from old plan to new plan
        if old_plan_name != "free":
            carry_over_credits(subscription.user, old_plan, new_plan)

        # Update local subscription record
        subscription.plan = new_plan
        subscription.status = "active"
        subscription.stripe_subscription_id = session.subscription
        subscription.save(update_fields=["plan", "status", "stripe_subscription_id"])

        logger.info(
            "Plan updated: user=%s, %s → %s (carry-over applied)",
            user_id,
            old_plan_name,
            plan_name,
        )

    def _handle_subscription_deleted(self, stripe_subscription):
        """
        Stripe subscription ended (cancelled or expired).
        Downgrade the user back to the free plan with active status.
        """
        try:
            subscription = UserSubscription.objects.get(
                stripe_subscription_id=stripe_subscription["id"],
            )
            free_plan = Plan.objects.get(name="free")

            # Set status to 'active' (not 'cancelled') because the user
            # is now an active free-tier user. Setting 'cancelled' would
            # make is_active() return False, locking them out entirely.
            subscription.plan = free_plan
            subscription.status = "active"
            subscription.stripe_subscription_id = ""  # clear stale Stripe ID
            subscription.save(
                update_fields=["plan", "status", "stripe_subscription_id"]
            )

            logger.info(
                "Subscription ended — user %s downgraded to free",
                subscription.user_id,
            )
        except UserSubscription.DoesNotExist:
            logger.warning(
                "Subscription deleted event for unknown stripe_subscription_id: %s",
                stripe_subscription.get("id"),
            )

    def _handle_payment_succeeded(self, invoice):
        """Record successful payment in PaymentHistory."""
        try:
            subscription = UserSubscription.objects.get(
                stripe_customer_id=invoice["customer"],
            )
        except UserSubscription.DoesNotExist:
            logger.warning(
                "Payment succeeded for unknown customer: %s",
                invoice.get("customer"),
            )
            return

        PaymentHistory.objects.get_or_create(
            stripe_invoice_id=invoice["id"],
            defaults={
                "user": subscription.user,
                "amount": invoice["amount_paid"] / 100,  # Stripe sends cents
                "currency": invoice["currency"],
                "status": "paid",
                "paid_at": datetime.fromtimestamp(
                    invoice["status_transitions"]["paid_at"],
                    tz=dt_timezone.utc,
                ),
            },
        )

        # Update period end
        subscription.current_period_end = datetime.fromtimestamp(
            invoice["lines"]["data"][0]["period"]["end"],
            tz=dt_timezone.utc,
        )
        subscription.status = "active"
        subscription.save(update_fields=["current_period_end", "status"])

    def _handle_payment_failed(self, invoice):
        """Mark subscription as past_due on failed payment."""
        try:
            subscription = UserSubscription.objects.get(
                stripe_customer_id=invoice["customer"],
            )
        except UserSubscription.DoesNotExist:
            logger.warning(
                "Payment failed for unknown customer: %s",
                invoice.get("customer"),
            )
            return

        subscription.status = "past_due"
        subscription.save(update_fields=["status"])

        PaymentHistory.objects.get_or_create(
            stripe_invoice_id=invoice["id"],
            defaults={
                "user": subscription.user,
                "amount": invoice["amount_due"] / 100,
                "currency": invoice["currency"],
                "status": "failed",
            },
        )


# ═══════════════════════════════════════════════════════════════
#  Usage Stats
# ═══════════════════════════════════════════════════════════════


class UsageStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from freelanceleads.quota_guard import get_period_start

        subscription = _get_subscription(request.user)
        if not subscription:
            return Response(
                {"error": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start = get_period_start()

        counters = UsageCounter.objects.filter(
            user=request.user,
            reset_date=period_start,
        ).select_related("user__subscription__plan")

        serializer = UsageStatsSerializer(
            {
                "usage": counters,
                "reset_date": period_start,
                "plan": subscription.plan.name,
            }
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
#  Cancel Subscription
# ═══════════════════════════════════════════════════════════════


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        subscription = _get_subscription(request.user)
        if not subscription:
            return Response(
                {"error": "No subscription found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block if already on free plan
        if subscription.plan.name == "free":
            return Response(
                {"error": "You are on the free plan. Nothing to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block if already cancelled
        if subscription.status == "cancelled":
            return Response(
                {"error": "Subscription is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel on Stripe — at_period_end=True means user keeps access until period ends
        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.error.StripeError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Stripe will fire customer.subscription.deleted webhook when period ends.
        # That webhook will downgrade plan to free — we just mark as cancelled here.
        subscription.status = "cancelled"
        subscription.save(update_fields=["status"])

        return Response(
            {
                "message": "Subscription cancelled. You will have access until the end of your billing period.",
                "current_period_end": subscription.current_period_end,
            },
            status=status.HTTP_200_OK,
        )
