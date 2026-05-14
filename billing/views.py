from .serializers import PlanSerializer,UserSubscriptionSerializer,CheckoutSessionSerializer,UsageStatsSerializer,CancelSubscriptionSerializer
from .models import Plan,UserSubscription,StripeWebhookEvent,PaymentHistory,UsageCounter
from rest_framework.generics import ListAPIView,RetrieveAPIView
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.conf import settings
import stripe
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from billing.models import UsageCounter
from datetime import datetime, timezone as dt_timezone


stripe.api_key = settings.STRIPE_SECRET_KEY
PLAN_HIERARCHY = ['free', 'pro', 'max']


class PlanListView(ListAPIView):
    model=Plan
    serializer_class=PlanSerializer
    permission_classes=[AllowAny]
    queryset=Plan.objects.all()



class PlanDetailView(RetrieveAPIView):
    queryset=Plan.objects.all()
    permission_classes=[AllowAny]
    serializer_class=PlanSerializer
    



class SubscriptionDetailView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        try:
            subscription = request.user.subscription
        except UserSubscription.DoesNotExist:
            return Response({"detail":"No Subscription Found"},status=status.HTTP_404_NOT_FOUND)
        serializer=UserSubscriptionSerializer(subscription)
        return Response(serializer.data,status=status.HTTP_200_OK)
    





class CheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CheckoutSessionSerializer
 
    def post(self, request):
        serializer = CheckoutSessionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        plan_name = serializer.validated_data['plan_name']
 
        # Fetch target plan from DB
        try:
            plan = Plan.objects.get(name=plan_name)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)
 
        if not plan.stripe_price_id:
            return Response({'error': 'Plan is not configured for payments.'}, status=status.HTTP_400_BAD_REQUEST)
 
        subscription = request.user.subscription
        current_plan_name = subscription.plan.name
 
        # Block downgrade or same plan
        current_rank = PLAN_HIERARCHY.index(current_plan_name) if current_plan_name in PLAN_HIERARCHY else 0
        target_rank  = PLAN_HIERARCHY.index(plan_name) if plan_name in PLAN_HIERARCHY else 0
 
        if target_rank <= current_rank:
            return Response(
                {'error': f'You are already on the {current_plan_name} plan. You can only upgrade to a higher plan.'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        # Create or reuse Stripe customer
        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email    = request.user.email,
                metadata = {'user_id': request.user.id}
            )
            subscription.stripe_customer_id = customer.id
            subscription.save(update_fields=['stripe_customer_id'])
 
        # Build metadata — include old plan so webhook can carry over credits
        session_metadata = {
            'user_id'       : request.user.id,
            'plan_name'     : plan_name,
            'old_plan_name' : current_plan_name,   # ← key addition
        }
 
        # If user has an active Stripe subscription, cancel it before creating new one
        # (Stripe mid-cycle upgrade — we handle credit carry-over ourselves)
        if subscription.stripe_subscription_id and current_plan_name != 'free':
            try:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
            except stripe.error.StripeError as e:
                return Response({'error': f'Could not cancel existing subscription: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
 
        # Create Stripe Checkout Session for new plan
        session = stripe.checkout.Session.create(
            customer             = subscription.stripe_customer_id,
            payment_method_types = ['card'],
            line_items           = [{'price': plan.stripe_price_id, 'quantity': 1}],
            mode                 = 'subscription',
            success_url          = settings.STRIPE_SUCCESS_URL + '&session_id={CHECKOUT_SESSION_ID}',
            cancel_url           = settings.STRIPE_CANCEL_URL,
            metadata             = session_metadata,
        )
 
        return Response({'session_url': session.url}, status=status.HTTP_200_OK)
 







@method_decorator(csrf_exempt,name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]  # Stripe sends requests, not logged in users

    def post(self, request):
        payload    = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')


        # import logging
        # logger = logging.getLogger(__name__)
        # logger.warning(f"SECRET: {settings.STRIPE_WEBHOOK_SECRET}")
        # logger.warning(f"SIG: {sig_header}")

        # Verify webhook signature — reject tampered requests
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response({'error': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency check — ignore already processed events
        if StripeWebhookEvent.objects.filter(stripe_event_id=event['id']).exists():
            return Response({'status': 'already processed'}, status=status.HTTP_200_OK)

        # Route event to correct handler
        handlers = {
            'checkout.session.completed'       : self._handle_checkout_completed,
            'customer.subscription.deleted'    : self._handle_subscription_deleted,
            'invoice.payment_succeeded'        : self._handle_payment_succeeded,
            'invoice.payment_failed'           : self._handle_payment_failed,
        }

        handler = handlers.get(event['type'])
        if handler:
            handler(event['data']['object'])

        # Mark event as processed
        StripeWebhookEvent.objects.create(
            stripe_event_id = event['id'],
            event_type      = event['type'],
        )

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    # ── Event Handlers ────────────────────────────────────────
  
    def _handle_checkout_completed(self, session):
        from freelanceleads.quota_guard import carry_over_credits

        try:
            session = stripe.checkout.Session.retrieve(session['id'])
        except stripe.error.StripeError as e:
            # print(f"ERROR: Could not retrieve session from Stripe: {e}")
            return

        # DEBUG — remove after fixing
        # print(f"DEBUG session.metadata raw: {session.metadata}")
        # print(f"DEBUG session.metadata type: {type(session.metadata)}")

        try:
            user_id       = int(session.metadata.user_id)
            plan_name     = session.metadata.plan_name
            old_plan_name = getattr(session.metadata, 'old_plan_name', 'free')
        except (AttributeError, TypeError, ValueError) as e:
            print(f"ERROR: Missing or invalid metadata: {e}")
            return

        try:
            subscription = UserSubscription.objects.select_related('plan').get(user_id=user_id)
            new_plan     = Plan.objects.get(name=plan_name)
            old_plan     = Plan.objects.get(name=old_plan_name)
        except (UserSubscription.DoesNotExist, Plan.DoesNotExist) as e:
            print(f"ERROR: {e}")
            return

        if old_plan_name != 'free':
            carry_over_credits(subscription.user, old_plan, new_plan)

        subscription.plan                   = new_plan
        subscription.status                 = 'active'
        subscription.stripe_subscription_id = session.subscription  # attribute access
        subscription.save(update_fields=['plan', 'status', 'stripe_subscription_id'])

        print(f"SUCCESS: Plan updated from {old_plan_name} → {plan_name} with carry-over credits applied")



    def _handle_subscription_deleted(self, stripe_subscription):
        """User cancelled — downgrade back to free."""
        try:
            subscription = UserSubscription.objects.get(
                stripe_subscription_id = stripe_subscription['id']
            )
            free_plan                  = Plan.objects.get(name='free')
            subscription.plan          = free_plan
            subscription.status        = 'cancelled'
            subscription.save(update_fields=['plan', 'status'])
        except UserSubscription.DoesNotExist:
            return

    def _handle_payment_succeeded(self, invoice):
        """Record successful payment in PaymentHistory."""
        try:
            subscription = UserSubscription.objects.get(
                stripe_customer_id = invoice['customer']
            )
        except UserSubscription.DoesNotExist:
            return

        PaymentHistory.objects.get_or_create(
            stripe_invoice_id = invoice['id'],
            defaults = {
                'user'     : subscription.user,
                'amount'   : invoice['amount_paid'] / 100,  # Stripe sends cents
                'currency' : invoice['currency'],
                'status'   : 'paid',
                'paid_at': datetime.fromtimestamp(invoice['status_transitions']['paid_at'], tz=dt_timezone.utc),
            }
        )

        # Update period end
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            invoice['lines']['data'][0]['period']['end'], tz=dt_timezone.utc
        )
        subscription.status = 'active'
        subscription.save(update_fields=['current_period_end', 'status'])

    def _handle_payment_failed(self, invoice):
        """Mark subscription as past_due on failed payment."""
        try:
            subscription        = UserSubscription.objects.get(stripe_customer_id=invoice['customer'])
            subscription.status = 'past_due'
            subscription.save(update_fields=['status'])

            PaymentHistory.objects.get_or_create(
                stripe_invoice_id = invoice['id'],
                defaults = {
                    'user'     : subscription.user,
                    'amount'   : invoice['amount_due'] / 100,
                    'currency' : invoice['currency'],
                    'status'   : 'failed',
                }
            )
        except UserSubscription.DoesNotExist:
            return







class UsageStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from freelanceleads.quota_guard import get_period_start
        period_start = get_period_start()

        # Fetch all counters for current period
        counters = UsageCounter.objects.filter(
            user       = request.user,
            reset_date = period_start,
        ).select_related('user__subscription__plan')

        serializer = UsageStatsSerializer({
            'usage'      : counters,
            'reset_date' : period_start,
            'plan'       : request.user.subscription.plan.name,
        })

        return Response(serializer.data, status=status.HTTP_200_OK)






class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        subscription = request.user.subscription

        # Block if already on free plan
        if subscription.plan.name == 'free':
            return Response(
                {'error': 'You are on free plan. Nothing to cancel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Block if already cancelled
        if subscription.status == 'cancelled':
            return Response(
                {'error': 'Subscription is already cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cancel on Stripe — at_period_end=True means user keeps access until period ends
        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
        except stripe.error.StripeError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Stripe will fire customer.subscription.deleted webhook when period ends
        # That webhook will downgrade plan to free — we just mark as cancelled here
        subscription.status = 'cancelled'
        subscription.save(update_fields=['status'])

        return Response({
            'message'            : 'Subscription cancelled. You will have access until the end of your billing period.',
            'current_period_end' : subscription.current_period_end,
        }, status=status.HTTP_200_OK)