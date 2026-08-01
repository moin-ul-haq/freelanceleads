from .views import (
    RegisterView,
    LoginView,
    ProfileView,
    ChangePasswordView,
    TeamView,
    InviteMemberView,
    TeamMembersView,
    RemoveMemberView,
    LeaveTeamView,
    NotificationsView,
)
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path("token/refresh/", TokenRefreshView.as_view()),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

    # Team management
    path("team/", TeamView.as_view(), name="team"),
    path("team/invite/", InviteMemberView.as_view(), name="team-invite"),
    path("team/members/", TeamMembersView.as_view(), name="team-members"),
    path("team/members/<int:seat_id>/", RemoveMemberView.as_view(), name="remove-member"),
    path("team/leave/", LeaveTeamView.as_view(), name="team-leave"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
]

