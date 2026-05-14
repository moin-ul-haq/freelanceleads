from django.urls import path
from .views import PlanListView,PlanDetailView,SubscriptionDetailView,CheckoutSessionView,StripeWebhookView,UsageStatsView,CancelSubscriptionView


urlpatterns=[
    path('plans/',PlanListView.as_view(),name='list-plans'),
    path('plans/<int:pk>/',PlanDetailView.as_view(),name='plan-detail'),
    path('subscription/',SubscriptionDetailView.as_view(),name='subscription-detail'),
    path('checkout/',CheckoutSessionView.as_view()),
    path('webhook/',StripeWebhookView.as_view()),
    path('usage/', UsageStatsView.as_view()),
    path('cancel/', CancelSubscriptionView.as_view()),




]