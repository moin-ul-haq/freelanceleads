from django.urls import path
from outreach.views import (
    EmailAccountListCreateView,
    CampaignListCreateView,
    CampaignDetailView,
    CampaignStepCreateView,
    CampaignEnrollView,
    CampaignLeadsListView,
    UnifiedInboxView,
    TrackingPixelView,
    GoogleAuthURLView,
    GoogleCallbackView,
)

urlpatterns = [
    path('accounts/', EmailAccountListCreateView.as_view(), name='outreach-accounts'),
    path('campaigns/', CampaignListCreateView.as_view(), name='outreach-campaigns'),
    path('campaigns/<int:pk>/', CampaignDetailView.as_view(), name='outreach-campaign-detail'),
    path('campaigns/<int:pk>/leads/', CampaignLeadsListView.as_view(), name='outreach-campaign-leads'),
    path('campaigns/steps/', CampaignStepCreateView.as_view(), name='outreach-campaign-steps'),
    path('campaigns/<int:pk>/enroll/', CampaignEnrollView.as_view(), name='outreach-campaign-enroll'),
    path('inbox/', UnifiedInboxView.as_view(), name='outreach-inbox'),
    path('track/<str:message_id>.gif', TrackingPixelView.as_view(), name='outreach-track'),
    path('google/auth-url/', GoogleAuthURLView.as_view(), name='outreach-google-auth'),
    path('google/callback/', GoogleCallbackView.as_view(), name='outreach-google-callback'),
]
