from django.urls import path
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
from django.contrib import admin
from django.utils import timezone
from .models import Client, Conversation, Message, Muhbir, UsageLimit, APIKey
from .utils import get_ai_response, token_size_calculate, avarage_request_token_size
from django.conf import settings


# APIKey Admin
@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "created_at", "is_active")
    readonly_fields = ("key", "created_at")
    list_filter = ("is_active",)
    search_fields = ("key",)


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
                    user_history=conversation.last_conversation_messages_str,
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
    return len(content) // 4  # Adjust as needed based on your tokenization strategy


from django.db import models

from functools import lru_cache
from django.db.models import Avg, Sum, F, Count


@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = (
        "is_muhbir",
        "daily_limit",
        "total_output_tokens",
        "price",
    )
    list_filter = ("is_muhbir",)

    def total_output_tokens(self, obj):
        """
        Calculate the total output tokens used by AI overall.
        """
        # Filter messages sent by AI and calculate total tokens
        messages = Message.objects.filter(
            conversation__client__is_muhbir=obj.is_muhbir,
            sender="ai",
        )

        total_output_tokens = sum(
            calculate_tokens(message.content) for message in messages
        )

        return total_output_tokens

    def price(self, obj):
        """
        Calculate the total cost based on output tokens.
        """
        total_output_tokens = self.total_output_tokens(obj)

        # Calculate price based on output tokens only
        output_price = (
            total_output_tokens / 1_000_000
        ) * 0.600  # Cost for output tokens

        return f"{output_price:.4f} $"  # Total price

    total_output_tokens.short_description = "Total Output Tokens (AI)"
    price.short_description = "Total Cost (Output Only)"


from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import admin, messages
import pandas as pd
from .models import AiData, Category
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
                    # Read data from Excel file
                    df = self.read_excel_data(excel_file)

                    # Validate and write data to the database
                    self.write_data_to_db(df, request)
                    return redirect("..")
                except Exception as e:
                    messages.error(request, f"Error processing file: {e}")
        else:
            form = ExcelUploadForm()

        context = {"form": form}
        return render(request, "admin/upload_data.html", context)

    # Method to read Excel data
    def read_excel_data(self, excel_file):
        """
        Reads the Excel file and returns a DataFrame.
        Raises an exception if there's an issue reading the file.
        """
        df = pd.read_excel(excel_file)

        # Check for required columns
        required_columns = ["heading", "content", "category"]
        if all(column in df.columns for column in required_columns):
            return df
        else:
            raise ValueError(
                "The Excel file must contain 'heading', 'content', and 'category' columns."
            )

    def write_data_to_db(self, df, request):
        """
        Writes the data from the DataFrame to the AiData model.
        Handles multiple categories for each article.
        Automatically creates any category that doesn't exist.
        """
        for index, row in df.iterrows():
            # Create the article
            article = AiData.objects.create(
                heading=row["heading"], content=row["content"]
            )

            # Handle categories, split by commas
            category_names = row["category"].split(",")
            for category_name in category_names:
                category_name = category_name.strip()  # Remove any extra spaces

                # Check if the category exists, if not create it
                category, created = Category.objects.get_or_create(name=category_name)

                # Add the category to the article
                article.categories.add(category)

        messages.success(request, "Data uploaded successfully!")

    # Add a method to display the link on the changelist page
    def changelist_upload_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Upload Data</a>',
            "/admin/api/aidata/upload-data/",
        )

    changelist_upload_button.short_description = "Upload Data"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
