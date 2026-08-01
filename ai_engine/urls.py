# ai_engine/urls.py

from django.urls import path
from .views import GeneratePitchView, BulkGeneratePitchView, ChatView, ChatHistoryView, GenerateProposalView

urlpatterns = [
    path("generate-pitch/", GeneratePitchView.as_view()),  # POST
    path("bulk-pitch/", BulkGeneratePitchView.as_view()),  # POST — Max plan
    path("chat/", ChatView.as_view()),  # POST
    path("chat/history/", ChatHistoryView.as_view()),  # GET + DELETE
    path("generate-proposal/", GenerateProposalView.as_view()),  # POST
]

