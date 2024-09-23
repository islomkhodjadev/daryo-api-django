from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.contrib import admin
from .models import Client, Conversation, Message


from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "created_at",
        "is_active",
    )  # Show these fields in the admin list
    readonly_fields = ("key", "created_at")  # Make API key and creation date read-only
    list_filter = ("is_active",)  # Filter by active/inactive status
    search_fields = ("key",)  # Allow searching by API key


class ConversationAdmin(admin.ModelAdmin):
    """
    Custom admin to display conversations with an extra link to a Telegram-like chat view.
    """

    list_display = ("client", "created_at", "view_chat_link")
    readonly_fields = ("client", "created_at")

    def view_chat_link(self, obj):
        """Adds a link to the custom conversation chat view"""
        return mark_safe(f'<a href="{obj.get_chat_url()}">View Chat</a>')

    view_chat_link.short_description = "Chat View"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:conversation_id>/chat/",
                self.admin_site.admin_view(self.chat_view),
                name="conversation_chat",
            ),
        ]
        return custom_urls + urls

    def chat_view(self, request, conversation_id):
        """Custom view to display the conversation as a chat interface"""
        conversation = Conversation.objects.get(id=conversation_id)
        messages = conversation.messages.all().order_by("timestamp")

        # Render the custom template with context
        context = {"conversation": conversation, "messages": messages}

        return render(request, "admin/conversation_chat.html", context)


admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Client)
