from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.contrib import admin
from django.utils import timezone
from .models import Client, Conversation, Message, Muhbir, UsageLimit, APIKey
from .utils import get_ai_response, content, content_for_chooser


# APIKey Admin
@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "created_at", "is_active")
    readonly_fields = ("key", "created_at")
    list_filter = ("is_active",)
    search_fields = ("key",)


# Conversation Admin
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Custom admin to display conversations with an extra link to a chat view.
    Muhbirs can only see their own conversations.
    """

    list_display = ("client", "created_at", "view_chat_link")
    readonly_fields = ("created_at",)
    list_filter = ("created_at", "client__is_muhbir")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if (
            request.user.is_superuser
            or request.user.groups.filter(name="DaryoAdmin").exists()
        ):
            return qs
        try:
            client = request.user.muhbir.client
            return qs.filter(client=client) if client.is_muhbir else qs.none()
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
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return render(request, "admin/conversation_not_found.html")

        messages = conversation.messages.all().order_by("timestamp")

        if request.method == "POST":
            if not conversation.can_send_message():
                time_remaining = conversation.time_until_reset()
                hours, remainder = divmod(time_remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                error_message = f"Sizda kunlik limit tugadi. Iltimos, {hours} soat va {minutes} minutdan keyin yana urinib ko'ring."
                context = {
                    "conversation": conversation,
                    "messages": messages,
                    "error_message": error_message,
                }
                return render(request, "admin/conversation_chat.html", context)

            user_message = request.POST.get("message_content", "").strip()
            if not user_message:
                error_message = "Iltimos, xabar kiriting."
                context = {
                    "conversation": conversation,
                    "messages": messages,
                    "error_message": error_message,
                }
                return render(request, "admin/conversation_chat.html", context)

            Message.objects.create(
                conversation=conversation,
                sender="client",
                content=user_message,
                timestamp=timezone.now(),
            )

            try:
                ai_response = get_ai_response(
                    user_message=user_message,
                    user_history=conversation.get_all_messages_str,
                    extra_data="\nyou are now responding to reporters of daro be serious and official you are helper for them, use official emojies\n",
                )
            except Exception as e:
                print(f"Error getting AI response: {e}")
                ai_response = "Kechirasiz, hozirda javob bera olmadim."

            Message.objects.create(
                conversation=conversation,
                sender="ai",
                content=ai_response,
                timestamp=timezone.now(),
            )

            return redirect(request.path)

        context = {"conversation": conversation, "messages": messages}
        return render(request, "admin/conversation_chat.html", context)


# Muhbir Admin
@admin.register(Muhbir)
class MuhbirAdmin(admin.ModelAdmin):
    list_display = ("user", "client")
    search_fields = ("user__username", "client__name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


# Client Admin
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin interface for managing clients.
    """

    list_display = ("name", "email", "external_id", "is_muhbir", "created_at")
    search_fields = ("name", "email", "external_id")
    list_filter = ("is_muhbir", "created_at")


def calculate_tokens(content):
    """
    Estimate the number of tokens used based on the content length.
    This is a simplified approximation.
    """
    return len(content) // 4 + 1  # Adjust as needed based on your tokenization strategy


# Usage Limit Admin
@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = ("is_muhbir", "daily_limit", "total_tokens_spent", "price")
    list_filter = ("is_muhbir",)

    def total_tokens_spent(self, obj):
        """Calculate total tokens spent by clients based on message content."""
        messages = Message.objects.filter(conversation__client__is_muhbir=obj.is_muhbir)

        total_input_tokens = 0
        total_output_tokens = 0
        extra_text = content_for_chooser + content

        # Build a full conversation history string
        history = ""
        for message in messages:
            if message.sender == "ai":
                total_output_tokens += calculate_tokens(message.content)
                history += f"AI: {message.content}\n"
            else:
                history += f"User: {message.content}\n"
                input_content = history + extra_text  # Include history and extra text
                total_input_tokens += (
                    calculate_tokens(input_content)
                    + AiData.getMeanContentLength()
                    + calculate_tokens(AiData.getAllHeadings())
                )

        return total_input_tokens, total_output_tokens

    def price(self, obj):
        """Calculate the total cost based on token usage."""
        input_tokens, output_tokens = self.total_tokens_spent(obj)

        input_price = (input_tokens / 1_000_000) * 0.150  # Cost for input tokens
        output_price = (output_tokens / 1_000_000) * 0.600  # Cost for output tokens

        return f"{input_price + output_price:.4f} $"  # Total price

    total_tokens_spent.short_description = "Total Tokens Spent (Input/Output)"
    price.short_description = "Total Cost"


from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import admin, messages
import pandas as pd
from .models import AiData
from .forms import ExcelUploadForm
from django.utils.html import format_html


@admin.register(AiData)
class AiDataAdmin(admin.ModelAdmin):
    list_display = ("id", "heading", "content")
    search_fields = ("heading",)

    # Add a custom URL for the upload form
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "upload-data/",
                self.admin_site.admin_view(self.upload_data),
                name="upload_data",
            ),
        ]
        return custom_urls + urls

    # Add the custom link to the changelist page
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["upload_data_url"] = "admin:upload_data"
        return super().changelist_view(request, extra_context=extra_context)

    # Function to handle the data upload
    def upload_data(self, request):
        if request.method == "POST":
            form = ExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                try:
                    # Read the Excel file into a pandas DataFrame
                    df = pd.read_excel(excel_file)

                    # Check for required columns 'heading' and 'content'
                    if "heading" in df.columns and "content" in df.columns:
                        # Insert each row from the Excel file into the AiData model
                        for index, row in df.iterrows():
                            AiData.objects.create(
                                heading=row["heading"], content=row["content"]
                            )
                        messages.success(request, "Data uploaded successfully!")
                        return redirect("..")
                    else:
                        messages.error(
                            request,
                            "The Excel file must contain 'heading' and 'content' columns.",
                        )
                except Exception as e:
                    messages.error(request, f"Error processing file: {e}")
        else:
            form = ExcelUploadForm()

        context = {"form": form}
        return render(request, "admin/upload_data.html", context)

    # Add a method to display the link on the changelist page
    def changelist_upload_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Upload Data</a>',
            "/admin/api/aidata/upload-data/",
        )

    changelist_upload_button.short_description = "Upload Data"
