from django.db import models
from django.utils import timezone
from datetime import timedelta


from django.db import models
import uuid
from django.utils import timezone


class APIKey(models.Model):
    """
    Model to store API keys that can be managed from the Django admin panel.
    """

    key = models.CharField(
        max_length=255, unique=True, default=uuid.uuid4, editable=False
    )
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)  # Enable or disable the API key

    def __str__(self):
        return f"API Key {self.key}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = str(uuid.uuid4())  # Generate a new API key if one doesn't exist
        super().save(*args, **kwargs)


class Client(models.Model):
    """
    Model representing a client who is interacting with the AI.
    Includes an external ID for referencing the client from another database.
    """

    external_id = models.CharField(
        max_length=255, unique=True
    )  # External ID from another database
    name = models.CharField(max_length=255)  # Client's name
    email = models.EmailField(
        unique=True, blank=True, null=True
    )  # Optional, can be blank
    created_at = models.DateTimeField(
        default=timezone.now
    )  # Timestamp of when the client was created

    def __str__(self):
        return f"Client: {self.name} (External ID: {self.external_id})"


class Conversation(models.Model):
    """
    Model representing a single conversation between a client and the AI.
    Each client can have only one conversation.
    """

    client = models.OneToOneField(
        Client, on_delete=models.CASCADE
    )  # Each client has only one conversation
    created_at = models.DateTimeField(
        default=timezone.now
    )  # Timestamp of when the conversation was started

    def __str__(self):
        return f"Conversation with {self.client.name}"

    def get_chat_url(self):
        """Generates the URL for the custom chat view"""
        return f"/admin/api/conversation/{self.id}/chat/"

    @property
    def get_all_messages_str(self):
        # Retrieve all messages related to this conversation
        messages = (
            self.messages.all()
        )  # 'messages' is the related_name from the Message model

        # Build a formatted string with time, sender, and content
        message_list = []
        for message in messages:
            timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            sender = "User" if message.sender == "client" else "AI"
            formatted_message = f"{timestamp} - {sender}: {message.content}"
            message_list.append(formatted_message)

        # Join the messages into a single string separated by newlines
        return "\n".join(message_list)

    def daily_usage(self):
        """
        Get the number of requests (messages) sent by the client today.
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        return self.messages.filter(
            sender="client", timestamp__range=(today_start, today_end)
        ).count()

    def can_send_message(self):
        """
        Check if the client can still send messages today (max 20 per day).
        """
        return self.daily_usage() < 20


class Message(models.Model):
    """
    Model representing an individual message in a conversation.
    """

    ROLE_CHOICES = [
        ("client", "Client"),
        ("ai", "AI"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )  # Link to the conversation
    sender = models.CharField(max_length=6, choices=ROLE_CHOICES)  # 'client' or 'ai'
    content = models.TextField()  # The actual message content
    timestamp = models.DateTimeField(default=timezone.now)  # When the message was sent

    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"

    class Meta:
        ordering = ["timestamp"]  # Messages ordered by time
