from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
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
        return Campaign.objects.filter(user=self.request.user).prefetch_related("steps")

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
            request.data._mutable = True  # allow modifying QueryDict
            request.data["email_account"] = user_accounts.first().id
            request.data._mutable = False

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

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CampaignDetailView(generics.RetrieveUpdateAPIView):
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
        campaign = Campaign.objects.get(id=campaign_id, user=self.request.user)
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

        created_count = 0
        skipped_ids = []
        missing_email_ids = []

        for lid in lead_ids:
            from leads.models import Lead

            try:
                lead = Lead.objects.get(id=lid)
            except Lead.DoesNotExist:
                skipped_ids.append({"lead_id": lid, "reason": "not_found"})
                continue

            if not lead.email:
                missing_email_ids.append(lid)

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
        ).order_by('-received_at')

class TrackingPixelView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, message_id):
        pixel_data = base64.b64decode(b"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        
        try:
            msg = OutreachMessage.objects.get(message_id=message_id)
            if not msg.opened_at:
                msg.opened_at = timezone.now()
                msg.save()
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

        params = urlencode({
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://mail.google.com/ https://www.googleapis.com/auth/userinfo.email',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': str(request.user.id),  # We pass user ID so callback knows who to link
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
        user_id = request.query_params.get('state')

        if not code or not user_id:
            return Response({"error": "Missing code or state."}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({
            "status": "connected",
            "email": email_address,
            "created": created,
        })
