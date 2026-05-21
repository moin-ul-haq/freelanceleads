# ai_engine/urls.py

from django.urls import path
from .views import GeneratePitchView, BulkGeneratePitchView, ChatView

urlpatterns = [
    path("generate-pitch/", GeneratePitchView.as_view()),  # POST
    path("bulk-pitch/", BulkGeneratePitchView.as_view()),  # POST — Max plan
    path("chat/", ChatView.as_view()),  # POST
]
