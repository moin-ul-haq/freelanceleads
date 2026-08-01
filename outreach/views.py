from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Case, When, Q
from django.conf import settings
from django.core import signing
from django.http import HttpResponse
from django.utils import timezone
import base64

from outreach.models import EmailAccount, Campaign, CampaignStep, CampaignLead, OutreachMessage, EmailReply
from outreach.serializers import (
    EmailAccountSerializer,
    CampaignSerializer,
    CampaignStepSerializer,
    CampaignLeadSerializer,
    EmailReplySerializer,
)

class EmailAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = EmailAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        data = self.request.data
        account = serializer.save(user=self.request.user)
        
        if account.provider == 'google':
            if 'access_token' in data:
                account.access_token = data['access_token']
            if 'refresh_token' in data:
                account.refresh_token = data['refresh_token']
        else:
            if 'smtp_password' in data:
                account.smtp_password = data['smtp_password']
            if 'imap_password' in data:
                account.imap_password = data['imap_password']
        account.save()

class CampaignListCreateView(generics.ListCreateAPIView):
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Campaign.objects.filter(
            user=self.request.user
        ).prefetch_related("steps").annotate(
            _enrolled_count=Count('campaign_leads')
        )

    def create(self, request, *args, **kwargs):
        user_accounts = EmailAccount.objects.filter(user=request.user)
        account_count = user_accounts.count()
        email_account_id = request.data.get("email_account")

        if account_count == 0:
            return Response(
                {"error": "No email account linked. Please connect an email account first via /api/outreach/accounts/ or /api/outreach/google/auth-url/."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if account_count == 1 and not email_account_id:
            # Auto-assign the only email account
            email_account_id = user_accounts.first().id

        if account_count > 1 and not email_account_id:
            # Require explicit selection
            available = [
                {"id": a.id, "email_address": a.email_address, "provider": a.provider}
                for a in user_accounts
            ]
            return Response(
                {
                    "error": "You have multiple email accounts. Please specify which one to use.",
                    "available_accounts": available,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate the selected account belongs to the user
        if email_account_id and not user_accounts.filter(id=email_account_id).exists():
            return Response(
                {"error": f"Email account {email_account_id} not found or does not belong to you."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store for perform_create (avoids mutating request.data)
        self._resolved_email_account_id = email_account_id
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        save_kwargs = {"user": self.request.user}
        resolved_id = getattr(self, "_resolved_email_account_id", None)
        if resolved_id:
            save_kwargs["email_account_id"] = resolved_id
        serializer.save(**save_kwargs)


class CampaignDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user).prefetch_related("steps")


class CampaignLeadsListView(generics.ListAPIView):
    """GET enrolled leads for a campaign."""

    serializer_class = CampaignLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            CampaignLead.objects.filter(
                campaign_id=self.kwargs["pk"],
                campaign__user=self.request.user,
            )
            .select_related("lead")
            .order_by("-added_at")
        )

class CampaignStepCreateView(generics.CreateAPIView):
    serializer_class = CampaignStepSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        campaign_id = self.request.data.get('campaign_id')
        if not campaign_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"campaign_id": "This field is required."})
        try:
            campaign = Campaign.objects.get(id=campaign_id, user=self.request.user)
        except Campaign.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Campaign not found or does not belong to you.")
        serializer.save(campaign=campaign)

class CampaignEnrollView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            campaign = Campaign.objects.get(pk=pk, user=request.user)
        except Campaign.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Auto-assign email account if not set
        if not campaign.email_account:
            user_accounts = EmailAccount.objects.filter(user=request.user)
            account_count = user_accounts.count()

            if account_count == 0:
                return Response(
                    {"error": "No email account linked. Please connect an email account first."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif account_count == 1:
                campaign.email_account = user_accounts.first()
                campaign.save(update_fields=["email_account"])
            else:
                available = [
                    {"id": a.id, "email_address": a.email_address, "provider": a.provider}
                    for a in user_accounts
                ]
                return Response(
                    {
                        "error": "Campaign has no email account and you have multiple accounts. Please update the campaign with an email_account first.",
                        "available_accounts": available,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
        lead_ids = request.data.get("lead_ids", [])
        if not isinstance(lead_ids, list) or not lead_ids:
            return Response(
                {"error": "Provide lead_ids as a non-empty list, e.g. {\"lead_ids\": [1, 2, 3]}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Batch fetch all leads in one query instead of N individual get() calls
        from leads.models import Lead

        leads_map = {l.id: l for l in Lead.objects.filter(id__in=lead_ids)}

        created_count = 0
        skipped_ids = []
        missing_email_ids = []

        for lid in lead_ids:
            lead = leads_map.get(lid)
            if not lead:
                skipped_ids.append({"lead_id": lid, "reason": "not_found"})
                continue

            if not lead.email:
                missing_email_ids.append(lid)
                skipped_ids.append({"lead_id": lid, "reason": "no_email"})
                continue

            from outreach.models import UnsubscribedEmail
            if UnsubscribedEmail.objects.filter(user=request.user, email__iexact=lead.email).exists():
                skipped_ids.append({"lead_id": lid, "reason": "unsubscribed"})
                continue

            _obj, created = CampaignLead.objects.get_or_create(
                campaign=campaign,
                lead_id=lid,
                defaults={"next_step_date": timezone.now()},
            )
            if created:
                created_count += 1
            else:
                skipped_ids.append({"lead_id": lid, "reason": "already_enrolled"})

        total_enrolled = campaign.campaign_leads.count()

        return Response(
            {
                "status": "enrolled",
                "count": created_count,
                "total_enrolled": total_enrolled,
                "already_enrolled": len(
                    [s for s in skipped_ids if s.get("reason") == "already_enrolled"]
                ),
                "missing_email_lead_ids": missing_email_ids,
                "skipped": skipped_ids,
            }
        )

class UnifiedInboxView(generics.ListAPIView):
    serializer_class = EmailReplySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EmailReply.objects.filter(
            outreach_message__campaign_lead__campaign__user=self.request.user
        ).select_related(
            'outreach_message__campaign_lead__campaign',
            'outreach_message__campaign_lead__lead',
        ).order_by('-received_at')

class TrackingPixelView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, message_id):
        pixel_data = base64.b64decode(b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        
        try:
            msg = OutreachMessage.objects.get(message_id=message_id)
            if not msg.opened_at:
                msg.opened_at = timezone.now()
                msg.save(update_fields=["opened_at"])
        except OutreachMessage.DoesNotExist:
            pass
            
        return HttpResponse(pixel_data, content_type="image/gif")

class GoogleAuthURLView(APIView):
    """Returns the Google OAuth consent URL that the user clicks to connect Gmail."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import os
        from urllib.parse import urlencode

        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        redirect_uri = request.build_absolute_uri('/api/outreach/google/callback/')

        # Sign the user ID to prevent tampering in the OAuth state param
        signed_state = signing.dumps(request.user.id, salt='google-oauth-state')

        params = urlencode({
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://mail.google.com/ https://www.googleapis.com/auth/userinfo.email',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': signed_state,
        })

        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        return Response({"auth_url": auth_url})

class GoogleCallbackView(APIView):
    """Handles the redirect from Google after user grants permission."""
    permission_classes = [AllowAny]  # Google redirects here; no Bearer token in the URL

    def get(self, request):
        import os, requests as http_requests
        from django.contrib.auth import get_user_model

        code = request.query_params.get('code')
        state = request.query_params.get('state')

        if not code or not state:
            return Response({"error": "Missing code or state."}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the signed state token — prevents account takeover
        try:
            user_id = signing.loads(state, salt='google-oauth-state', max_age=600)
        except signing.BadSignature:
            return Response({"error": "Invalid or expired state token."}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)

        # Exchange the authorization code for tokens
        token_response = http_requests.post("https://oauth2.googleapis.com/token", data={
            'code': code,
            'client_id': os.environ.get("GOOGLE_CLIENT_ID", ""),
            'client_secret': os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            'redirect_uri': request.build_absolute_uri('/api/outreach/google/callback/'),
            'grant_type': 'authorization_code',
        })

        if token_response.status_code != 200:
            return Response({"error": "Token exchange failed.", "details": token_response.json()}, status=status.HTTP_400_BAD_REQUEST)

        tokens = token_response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')

        # Fetch user's Gmail address from Google
        profile_response = http_requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        email_address = profile_response.json().get('email', '')

        # Create or update the EmailAccount
        account, created = EmailAccount.objects.get_or_create(
            user=user,
            email_address=email_address,
            defaults={'provider': 'google'}
        )
        account.access_token = access_token
        if refresh_token:
            account.refresh_token = refresh_token
        account.save()

        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}/outreach?connected={email_address}")


class CampaignAnalyticsView(APIView):
    """
    GET /api/outreach/campaigns/<pk>/analytics/

    Returns aggregate stats for a campaign:
    - Total emails sent
    - Total opened / open rate
    - Total replied / reply rate
    - Total bounced
    - Active / completed leads
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            campaign = Campaign.objects.get(pk=pk, user=request.user)
        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Conditional aggregation: 2 queries instead of 7 separate COUNT queries
        lead_stats = CampaignLead.objects.filter(campaign=campaign).aggregate(
            total_enrolled=Count('id'),
            total_replied=Count(Case(When(status='replied', then='id'))),
            total_bounced=Count(Case(When(status='bounced', then='id'))),
            total_active=Count(Case(When(status='active', then='id'))),
            total_completed=Count(Case(When(status='completed', then='id'))),
        )

        msg_stats = OutreachMessage.objects.filter(
            campaign_lead__campaign=campaign
        ).aggregate(
            total_sent=Count('id'),
            total_opened=Count('id', filter=Q(opened_at__isnull=False)),
        )

        total_enrolled = lead_stats['total_enrolled']
        total_sent = msg_stats['total_sent']
        total_opened = msg_stats['total_opened']
        total_replied = lead_stats['total_replied']

        open_rate = round((total_opened / total_sent * 100), 2) if total_sent > 0 else 0.0
        reply_rate = round((total_replied / total_enrolled * 100), 2) if total_enrolled > 0 else 0.0

        return Response({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "status": campaign.status,
            "total_enrolled": total_enrolled,
            "total_sent": total_sent,
            "total_opened": total_opened,
            "open_rate": open_rate,
            "total_replied": total_replied,
            "reply_rate": reply_rate,
            "total_bounced": lead_stats['total_bounced'],
            "total_active": lead_stats['total_active'],
            "total_completed": lead_stats['total_completed'],
        })



class SendEmailView(APIView):
    """
    POST /api/outreach/send-email/ {lead_id, subject, body}
    One-off send (e.g. an AI pitch) through the user's connected email
    account. Counts against the email_send quota.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from leads.models import Lead
        from freelanceleads.quota_guard import check, increment
        from outreach.utils import send_email_via_account
        from rest_framework.exceptions import PermissionDenied

        lead_id = request.data.get("lead_id")
        subject = (request.data.get("subject") or "").strip()
        body = (request.data.get("body") or "").strip()

        if not lead_id or not subject or not body:
            return Response(
                {"error": "lead_id, subject and body are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

        if not lead.email:
            return Response(
                {"error": "This lead has no email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account = EmailAccount.objects.filter(user=request.user).first()
        if not account:
            return Response(
                {"error": "No email account connected. Connect one in Outreach → Email Accounts first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            check(request.user, "email_send")
        except PermissionDenied as e:
            return Response(e.detail, status=status.HTTP_403_FORBIDDEN)

        # Respect the account's daily cap (shared with campaign sends)
        from datetime import timedelta
        day_ago = timezone.now() - timedelta(hours=24)
        from django.db.models import Q as _Q
        sent_today = OutreachMessage.objects.filter(
            _Q(email_account=account) | _Q(campaign_lead__campaign__email_account=account),
            sent_at__gte=day_ago,
        ).distinct().count()
        if sent_today >= (account.daily_send_limit or 40):
            return Response(
                {"error": f"Daily send limit ({account.daily_send_limit}) reached for {account.email_address}. Try again tomorrow — this protects your sender reputation."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        from outreach.models import UnsubscribedEmail
        if UnsubscribedEmail.objects.filter(user=request.user, email__iexact=lead.email).exists():
            return Response(
                {"error": "This recipient has unsubscribed from your emails."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            message_id = send_email_via_account(account, lead.email, subject, body)
        except Exception as e:
            return Response(
                {"error": f"Send failed: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Record the send so daily caps, open tracking and reply matching
        # cover one-off emails exactly like campaign emails
        OutreachMessage.objects.create(
            campaign_lead=None,
            email_account=account,
            lead=lead,
            message_id=message_id,
            subject=subject,
            body=body,
        )

        increment(request.user, "email_send")
        return Response(
            {"status": "sent", "to": lead.email, "from": account.email_address},
            status=status.HTTP_200_OK,
        )


class UnsubscribeView(APIView):
    """GET /api/outreach/unsubscribe/<token>/ — public one-click unsubscribe."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        from django.http import HttpResponse
        from outreach.models import UnsubscribedEmail

        try:
            data = signing.loads(token, salt="unsubscribe", max_age=60 * 60 * 24 * 365)
        except signing.BadSignature:
            return HttpResponse("Invalid unsubscribe link.", status=400)

        UnsubscribedEmail.objects.get_or_create(user_id=data["u"], email=data["e"].lower())
        CampaignLead.objects.filter(
            campaign__user_id=data["u"], lead__email__iexact=data["e"], status="active"
        ).update(status="unsubscribed")
        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
            "<h2>You've been unsubscribed.</h2><p>You won't receive further emails.</p>"
            "</body></html>"
        )

    # RFC 8058 one-click POST from mail clients
    def post(self, request, token):
        return self.get(request, token)


class EmailAccountDeleteView(APIView):
    """DELETE /api/outreach/accounts/<pk>/ — disconnect + wipe stored tokens."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = EmailAccount.objects.filter(id=pk, user=request.user).delete()
        if not deleted:
            return Response({"error": "Account not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CampaignStepDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CampaignStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CampaignStep.objects.filter(campaign__user=self.request.user)
