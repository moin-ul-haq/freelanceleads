# leads/urls.py

from django.urls import path
from .views import (
    LeadSearchView,
    SaveLeadView,
    SavedLeadsListView,
    LeadDetailView,
    LeadStatusView,
)

urlpatterns = [
    path("search/", LeadSearchView.as_view()),  # POST
    path("status/", LeadStatusView.as_view()),  # POST — poll audit progress, no quota
    path("saved/", SavedLeadsListView.as_view()),  # GET
    path("<int:lead_id>/", LeadDetailView.as_view()),  # GET
    path("<int:lead_id>/save/", SaveLeadView.as_view()),  # POST + DELETE
]
