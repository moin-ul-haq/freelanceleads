from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class User(AbstractUser):
    """Custom user with email-based authentication."""

    created_at = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(unique=True)
    timezone = models.CharField(max_length=50, default="UTC")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email

    @property
    def current_plan(self):
        """Return the user's active subscription plan, or None."""
        try:
            return self.subscription.plan
        except (AttributeError, ObjectDoesNotExist):
            return None

    @property
    def active_team(self):
        """Return the team this user belongs to, or None."""
        try:
            return self.seat.team
        except (AttributeError, ObjectDoesNotExist):
            return None


class Team(models.Model):
    """A workspace that groups users under a shared account."""

    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name="owned_teams"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TeamSeat(models.Model):
    """Links a user to a team with a specific role (owner / admin / member)."""

    ROLE_CHOICES = [("owner", "Owner"), ("admin", "Admin"), ("member", "Member")]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="seats")
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seat")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} — {self.team.name} — {self.role}"


class Notification(models.Model):
    """In-app notifications: email opened, reply received, site inquiry, etc."""

    TYPES = (
        ("open", "Email opened"),
        ("reply", "Reply received"),
        ("inquiry", "Demo site inquiry"),
        ("bounce", "Email bounced"),
        ("system", "System"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=12, choices=TYPES, default="system")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)  # in-app route, e.g. /outreach
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"[{self.type}] {self.title}"


def notify(user, type, title, body="", link=""):
    """One-liner used by outreach/demosites events. Never raises."""
    try:
        Notification.objects.create(user=user, type=type, title=title, body=body[:500], link=link)
    except Exception:
        pass
