from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    """Persistent AI-assistant conversation history, one thread per user."""

    ROLE_CHOICES = (("user", "user"), ("assistant", "assistant"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"{self.user_id}/{self.role}: {self.content[:40]}"
