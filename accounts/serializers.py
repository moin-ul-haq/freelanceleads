from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import Team, TeamSeat

User = get_user_model()


# ─────────────────────────────────────────────────────────────
#  Auth Serializers
# ─────────────────────────────────────────────────────────────


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password", "password2")

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")

        # Generate a unique username from the email prefix.
        # If "john" is taken, try "john1", "john2", etc.
        base_username = validated_data["email"].split("@")[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        validated_data["username"] = username

        return User.objects.create_user(**validated_data)
        # Signal will auto-create free UserSubscription after this


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    # JWT tokens returned from view, not here


# ─────────────────────────────────────────────────────────────
#  User Serializers
# ─────────────────────────────────────────────────────────────


class UserMinimalSerializer(serializers.ModelSerializer):
    """Lightweight — use inside nested serializers (e.g. TeamSeat)."""

    class Meta:
        model = User
        fields = ("id", "email", "username")


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile — used in /auth/me/ endpoint."""

    active_team = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "active_team",
            "plan",
            "created_at",
        )

    def get_active_team(self, obj):
        team = obj.active_team
        if team:
            return TeamMinimalSerializer(team).data
        return None

    def get_plan(self, obj):
        # Safe access — subscription might not exist yet
        sub = getattr(obj, "subscription", None)
        return sub.plan.name if sub else "free"

    def validate_email(self, value):
        """Ensure the new email isn't already taken by another user."""
        if User.objects.filter(email=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def update(self, instance, validated_data):
        instance.username = validated_data.get("username", instance.username)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.email = validated_data.get("email", instance.email)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    refresh = serializers.CharField(
        write_only=True,
        help_text="Current refresh token — will be blacklisted after password change.",
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()


# ─────────────────────────────────────────────────────────────
#  Team Serializers
# ─────────────────────────────────────────────────────────────


class TeamMinimalSerializer(serializers.ModelSerializer):
    """Lightweight — used inside UserProfileSerializer."""

    class Meta:
        model = Team
        fields = ("id", "name")


class TeamSeatSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = TeamSeat
        fields = ("id", "user", "role", "joined_at")
        read_only_fields = ("joined_at",)


class TeamSerializer(serializers.ModelSerializer):
    owner = UserMinimalSerializer(read_only=True)
    seats = TeamSeatSerializer(many=True, read_only=True)
    seat_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ("id", "name", "owner", "seats", "seat_count", "created_at")
        read_only_fields = ("owner", "created_at")

    def get_seat_count(self, obj):
        # Use len() to avoid extra COUNT query when seats are already prefetched/serialized
        return obj.seats.count() if not hasattr(obj, '_prefetched_objects_cache') else len(obj.seats.all())

    def create(self, validated_data):
        owner = self.context["request"].user
        team = Team.objects.create(owner=owner, **validated_data)
        # Auto-create owner seat
        TeamSeat.objects.create(team=team, user=owner, role="owner")
        return team


class InviteMemberSerializer(serializers.Serializer):
    """POST /teams/{id}/invite/ — invite user by email."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["admin", "member"], default="member")

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email.")
        return value

    def validate(self, attrs):
        team = self.context["team"]
        user = User.objects.get(email=attrs["email"])
        # Check if user already has a seat anywhere (one team rule)
        if hasattr(user, "seat"):
            raise serializers.ValidationError("This user already belongs to a team.")
        return attrs
