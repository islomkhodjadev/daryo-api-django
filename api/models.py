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


class UsageLimit(models.Model):
    """
    Model representing daily message limits for different types of clients.
    """

    is_muhbir = models.BooleanField(
        default=False
    )  # True for Muhbirs, False for regular clients
    daily_limit = models.IntegerField(default=20)  # Default limit for ordinary clients

    def __str__(self):
        client_type = "Muhbir" if self.is_muhbir else "Ordinary Client"
        return f"{client_type}: {self.daily_limit} messages per day"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_muhbir"], name="unique_usage_limit_for_client_type"
            )
        ]


class Client(models.Model):
    """
    Model representing a client who is interacting with the AI.
    Includes an external ID for referencing the client from another database.
    """

    is_muhbir = models.BooleanField(default=False)

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


from django.conf import settings


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
        return f"/{settings.BASE_URL}/admin/api/conversation/{self.id}/chat/"

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
        Get the number of messages sent by the client today.
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        return self.messages.filter(
            sender="client", timestamp__range=(today_start, today_end)
        ).count()

    def can_send_message(self):
        """
        Check if the client can still send messages today based on their usage limit.
        """
        if self.client.is_muhbir:
            # Fetch the usage limit for Muhbirs
            usage_limit = UsageLimit.objects.get(is_muhbir=True).daily_limit
        else:
            # Fetch the usage limit for ordinary clients
            usage_limit = UsageLimit.objects.get(is_muhbir=False).daily_limit

        return self.daily_usage() < usage_limit

    def time_until_reset(self):
        """
        Calculate the time remaining until midnight (when the message limit resets).
        """
        now = timezone.now()
        # Find the next midnight
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        time_remaining = midnight - now

        # Return the time remaining as a timedelta object
        return time_remaining


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


class Muhbir(models.Model):
    """
    Model representing a Muhbir (user) who can access their conversation.
    Each Muhbir is linked to a Client.
    """

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE
    )  # Links to the Django User model
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE
    )  # Links to the Client model

    def __str__(self):
        return f"Muhbir: {self.user.username}"


from django.core.exceptions import ObjectDoesNotExist


class AiData(models.Model):
    heading = models.TextField()
    content = models.TextField()

    @classmethod
    def getData(cls, id):
        try:
            id = int(id)
        except (ValueError, TypeError):
            return None  # Invalid ID format

        # Safely retrieve data, handling potential errors
        try:
            data = cls.objects.get(id=id)
            return data
        except ObjectDoesNotExist:
            return None  # Handle if the object does not exist
        except Exception as e:
            # Optionally log the exception or handle other errors
            return None

    @classmethod
    def getAllHeadings(cls):
        # Retrieve all records from the database
        all_data = cls.objects.all()
        # Format each record as 'id:{number}-heading:{heading};'
        result = []
        for data in all_data:
            result.append(f"id:({data.id})-heading:({data.heading});")
        # Return the list of formatted strings
        return " ".join(result)

    @classmethod
    def getMeanContentLength(cls):
        # Retrieve all records
        all_data = cls.objects.all()
        # Get the total length of content and count of records
        total_length = sum(len(data.content) for data in all_data)
        count = all_data.count()

        # If there are no records, return 0 to avoid division by zero
        if count == 0:
            return 0

        # Calculate mean content length
        mean_length = total_length // count
        return mean_length
