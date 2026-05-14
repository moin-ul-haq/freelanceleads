from .views import RegisterView,LoginView,ProfileView,ChangePasswordView
from django.urls import path,include
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view()),
    path('register/',RegisterView.as_view(),name='register'),
    path('login/',LoginView.as_view(),name='login'),
    path('me/',ProfileView.as_view(),name='profile'),
    path('change-password/',ChangePasswordView.as_view(),name='change_password'),
    ]