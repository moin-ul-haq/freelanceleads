from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "short_content", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "user__email")
    readonly_fields = ("user", "role", "content", "created_at")

    def short_content(self, obj):
        return obj.content[:80]
