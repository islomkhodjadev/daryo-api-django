from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.contrib import admin
from .models import Client, Conversation, Message, Muhbir, UsageLimit


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


from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from .models import Client, Conversation, Message
from django.utils import timezone
from .utils import get_ai_response


class ConversationAdmin(admin.ModelAdmin):
    """
    Custom admin to display conversations with an extra link to a chat view.
    Muhbirs can only see their own conversations.
    """

    list_display = ("client", "created_at", "view_chat_link")
    readonly_fields = ("created_at",)
    list_filter = ("created_at", "client__is_muhbir")

    def get_queryset(self, request):
        """
        Override the queryset to ensure that Muhbirs only see their own conversation.
        Admins still see everything.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superusers see all conversations
        else:
            try:
                # Limit Muhbir to see only their own conversation
                client = request.user.muhbir.client
                if client.is_muhbir:
                    return qs.filter(client=client)
                return qs.none()
            except Client.DoesNotExist:
                return qs.none()

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
        """Custom view to display the conversation as a chat interface and handle user input."""
        conversation = Conversation.objects.get(id=conversation_id)
        messages = conversation.messages.all().order_by("timestamp")

        if request.method == "POST":
            # Check if the client can still send messages today
            if not conversation.can_send_message():
                # If the client has reached their daily limit, send an error message
                time_remaining = conversation.time_until_reset()

                # Convert the time remaining into hours and minutes
                hours, remainder = divmod(time_remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                # Error message with time until reset
                error_message = f"Sizda kunlik limit tugadi. Iltimos, {hours} soat va {minutes} minutdan keyin yana urinib ko'ring."
                context = {
                    "conversation": conversation,
                    "messages": messages,
                    "error_message": error_message,
                }
                return render(request, "admin/conversation_chat.html", context)
            # Get the Muhbir's message from the input form
            user_message = request.POST.get("message_content")

            # Create a new message object for the client message
            Message.objects.create(
                conversation=conversation,
                sender="client",
                content=user_message,
                timestamp=timezone.now(),
            )

            # Simulate AI response (you can replace this with actual AI integration)
            ai_response = get_ai_response(
                user_message,
                extra_data="\nyou are now responding to reporters of daro\n",
            )

            # Create a new message object for the AI response
            Message.objects.create(
                conversation=conversation,
                sender="ai",
                content=ai_response,
                timestamp=timezone.now(),
            )

            # Redirect to the same chat view to display the updated messages
            return redirect(request.path)

        context = {"conversation": conversation, "messages": messages}
        return render(request, "admin/conversation_chat.html", context)


@admin.register(Muhbir)
class MuhbirAdmin(admin.ModelAdmin):
    list_display = ("user", "client")
    search_fields = ("user__username", "client__name")

    def get_queryset(self, request):
        """
        Superusers see all Muhbirs, but each Muhbir can only see their own client.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superusers can see all
        else:
            return qs.filter(user=request.user)  # Muhbirs only see themselves


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin interface for managing clients.
    """

    list_display = (
        "name",
        "email",
        "external_id",
        "is_muhbir",
        "created_at",
    )
    search_fields = ("name", "email", "external_id")
    list_filter = (
        "is_muhbir",
        "created_at",
    )  # Add filters for is_muhbir and created_at


admin.site.register(Conversation, ConversationAdmin)


@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = ("is_muhbir", "daily_limit")
    list_filter = ("is_muhbir",)
