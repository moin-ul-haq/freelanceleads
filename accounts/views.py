from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ObjectDoesNotExist
from .models import Team, TeamSeat

User = get_user_model()
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    TeamSerializer,
    TeamSeatSerializer,
    InviteMemberSerializer,
)
from drf_spectacular.utils import extend_schema


def get_tokens_for_user(user):
    """JWT tokens generate karta hai — login aur register dono mein use hoga."""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        tokens = get_tokens_for_user(user)

        return Response(
            {
                "user": {"id": user.id, "email": user.email, "username": user.username},
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(
            request=request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if not user:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "user": {"id": user.id, "email": user.email, "username": user.username},
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Eager load subscription + plan to avoid 2 lazy-load queries in serializer
        user = User.objects.select_related("subscription__plan").get(pk=request.user.pk)
        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,  # only update fields that are sent
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Change User Password",
    description="Allows authenticated users to change password",
    request=ChangePasswordSerializer,
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}},
    tags=["Authentication"],
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        # Blacklist current refresh token so user must login again.
        # The refresh field is required, so it's always present in validated_data.
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            pass  # already invalid or expired, ignore

        # Issue a fresh token pair so the session continues seamlessly
        new_refresh = RefreshToken.for_user(request.user)
        return Response(
            {
                "message": "Password changed successfully.",
                "tokens": {
                    "refresh": str(new_refresh),
                    "access": str(new_refresh.access_token),
                },
            },
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════
#  Team Views
# ═══════════════════════════════════════════════════════════════


def _get_user_seat(user):
    """Return the user's TeamSeat, or None if they don't belong to a team."""
    try:
        return user.seat
    except TeamSeat.DoesNotExist:
        return None


def _get_team_seat_limit(user):
    """Return max seats allowed by the team owner's plan."""
    try:
        return user.subscription.plan.team_seat_limit
    except (AttributeError, ObjectDoesNotExist):
        return 1  # default to 1 (owner only) if no subscription


class TeamView(APIView):
    """
    GET  /api/auth/team/  — Get current user's team
    POST /api/auth/team/  — Create a new team
    PATCH /api/auth/team/ — Rename team (owner only)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"detail": "You are not part of any team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        team = seat.team
        serializer = TeamSerializer(team, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # Check user doesn't already belong to a team
        seat = _get_user_seat(request.user)
        if seat:
            return Response(
                {"error": "You already belong to a team. Leave your current team first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TeamSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        team = serializer.save()  # auto-creates owner seat via serializer.create()
        return Response(
            TeamSerializer(team, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"error": "You are not part of any team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if seat.role != "owner":
            return Response(
                {"error": "Only the team owner can rename the team."},
                status=status.HTTP_403_FORBIDDEN,
            )

        team = seat.team
        serializer = TeamSerializer(
            team, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        """DELETE /api/auth/team/ — Disband the team (owner only)."""
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"error": "You are not part of any team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if seat.role != "owner":
            return Response(
                {"error": "Only the team owner can disband the team."},
                status=status.HTTP_403_FORBIDDEN,
            )

        team = seat.team
        team.delete()  # cascades: deletes all TeamSeats too
        return Response(
            {"message": "Team disbanded successfully."},
            status=status.HTTP_200_OK,
        )


class InviteMemberView(APIView):
    """
    POST /api/auth/team/invite/
    Invite a registered user to join your team by email.
    Only owner/admin can invite. Enforces plan seat limits.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"error": "You must create a team first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if seat.role not in ("owner", "admin"):
            return Response(
                {"error": "Only owners and admins can invite members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        team = seat.team

        # Check seat limit based on owner's plan
        seat_limit = _get_team_seat_limit(team.owner)
        current_seats = team.seats.count()

        if seat_limit != -1 and current_seats >= seat_limit:
            return Response(
                {
                    "error": f"Team seat limit reached ({seat_limit}). Upgrade your plan for more seats.",
                    "current_seats": current_seats,
                    "limit": seat_limit,
                    "upgrade_url": "/api/billing/checkout/",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InviteMemberSerializer(
            data=request.data, context={"team": team, "request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model

        User = get_user_model()
        invited_user = User.objects.get(email=serializer.validated_data["email"])
        role = serializer.validated_data["role"]

        new_seat = TeamSeat.objects.create(team=team, user=invited_user, role=role)

        return Response(
            {
                "message": f"{invited_user.email} added to {team.name} as {role}.",
                "seat": TeamSeatSerializer(new_seat).data,
            },
            status=status.HTTP_201_CREATED,
        )


class TeamMembersView(APIView):
    """
    GET /api/auth/team/members/
    List all members of the current user's team.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"detail": "You are not part of any team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        seats = seat.team.seats.select_related("user").order_by("joined_at")
        serializer = TeamSeatSerializer(seats, many=True)

        return Response(
            {
                "team": seat.team.name,
                "members": serializer.data,
                "count": seats.count(),
                "seat_limit": _get_team_seat_limit(seat.team.owner),
            },
            status=status.HTTP_200_OK,
        )


class RemoveMemberView(APIView):
    """
    DELETE /api/auth/team/members/<seat_id>/
    Remove a member from the team. Owner/admin only. Cannot remove the owner.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, seat_id):
        my_seat = _get_user_seat(request.user)
        if not my_seat:
            return Response(
                {"error": "You are not part of any team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if my_seat.role not in ("owner", "admin"):
            return Response(
                {"error": "Only owners and admins can remove members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            target_seat = TeamSeat.objects.get(id=seat_id, team=my_seat.team)
        except TeamSeat.DoesNotExist:
            return Response(
                {"error": "Seat not found in your team."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if target_seat.role == "owner":
            return Response(
                {"error": "Cannot remove the team owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Admin cannot remove another admin — only owner can
        if target_seat.role == "admin" and my_seat.role != "owner":
            return Response(
                {"error": "Only the owner can remove admins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = target_seat.user.email
        target_seat.delete()

        return Response(
            {"message": f"{email} removed from the team."},
            status=status.HTTP_200_OK,
        )


class LeaveTeamView(APIView):
    """
    POST /api/auth/team/leave/
    Non-owner leaves the team. Owners must disband or transfer ownership.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        seat = _get_user_seat(request.user)
        if not seat:
            return Response(
                {"error": "You are not part of any team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if seat.role == "owner":
            return Response(
                {"error": "Team owners cannot leave. Disband the team or transfer ownership first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_name = seat.team.name
        seat.delete()

        return Response(
            {"message": f"You have left {team_name}."},
            status=status.HTTP_200_OK,
        )

