from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

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
    token_limit = models.IntegerField(default=0)  # Total token limit
    tokens_used = models.IntegerField(default=0)  # Tokens used so far

    def __str__(self):
        return f"API Key {self.key}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = str(uuid.uuid4())  # Generate a new API key if one doesn't exist
        super().save(*args, **kwargs)

    def remaining_tokens(self):
        """Returns the number of remaining tokens."""
        return self.token_limit - self.tokens_used

    def can_use_tokens(self, tokens_requested):
        """
        Check if the API key has enough remaining tokens to fulfill the request.
        """

        return self.remaining_tokens() >= tokens_requested

    @transaction.atomic
    def use_tokens(self, tokens_requested):
        """
        Deduct the requested tokens from the available tokens if there are enough left,
        with transaction locking to avoid race conditions.
        Returns True if tokens were successfully deducted, False otherwise.
        """
        # Lock the row to avoid race conditions
        api_key = APIKey.objects.select_for_update().get(pk=self.pk)

        api_key.tokens_used += tokens_requested
        api_key.save()


class UsageLimit(models.Model):
    """
    Model representing daily message limits for different types of clients.
    """

    is_muhbir = models.BooleanField(
        default=False
    )  # True for Muhbirs, False for regular clients
    daily_limit = models.IntegerField(default=20)  # Default limit for ordinary clients
    history_tokens = models.PositiveIntegerField(default=0)

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

    last_refreshed = models.DateTimeField(
        null=True, blank=True
    )  # New field to track last refresh time

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
    def last_conversation_messages_str(self):
        """
        Return messages from the last refresh time until now. If more than 2 hours have passed since the
        last refresh, reset the history and update the refresh time to now, but include the last message from the user.
        """
        now = timezone.now()

        # If last_refreshed is not set or more than 2 hours have passed since last refresh
        if self.last_refreshed is None or (
            now - self.last_refreshed >= timedelta(hours=2)
        ):
            # Find the last user message (before resetting)
            last_user_message = (
                self.messages.filter(sender="client").order_by("-timestamp").first()
            )

            # Update last_refreshed to now (starting a new conversation)
            self.last_refreshed = now
            self.save()

            # Return the last user message if it exists
            if last_user_message:
                timestamp = last_user_message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                formatted_message = f"{timestamp} - User: {last_user_message.content}"
                return formatted_message

        messages = self.messages.filter(timestamp__gte=self.last_refreshed)

        message_list = []
        for message in messages:
            timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            sender = "User" if message.sender == "client" else "AI"
            formatted_message = f"{timestamp} - {sender}: {message.content}"
            message_list.append(formatted_message)

        return "\n".join(message_list)

    @classmethod
    def get_avarage_token_size_for_history(cls):
        convers = cls.objects.all()
        count = convers.count()

        total_length = (
            sum([len(con.last_conversation_messages_str) for con in convers]) // count
            if count != 0
            else 0
        )

        return total_length // 4

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


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    @classmethod
    def getAllCategories(cls):
        # Retrieve all records from the database
        all_data = cls.objects.all()
        # Format each record as 'id:{number}-heading:{heading};'
        result = []
        for data in all_data:
            result.append(f"id:({data.id})-category:({data.name});")
        # Return the list of formatted strings
        return " ".join(result)

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
    def calculate_avarage_cat_token_size(cls):
        # Retrieve all records
        all_data = cls.objects.all()

        # Get the total number of categories
        total_categories = all_data.count()

        if total_categories == 0:
            return 0  # Avoid division by zero if there are no categories

        # Calculate the total length of all category names combined
        total_length = sum(len(data.name) for data in all_data)

        # Calculate the average token size, dividing by total categories and then by 4
        average_token_size = (total_length / total_categories) // 4

        return average_token_size

    @classmethod
    def calculate_average_headings_token_by_cat(cls):
        """
        Calculate the average token size for headings across all categories.
        This method calculates the total token size for articles in each category,
        then averages it across all categories.
        """
        cats = cls.objects.all()

        if not cats.exists():
            return 0  # Return 0 if there are no categories

        total_tokens = 0
        total_categories = cats.count()

        for cat in cats:

            token_size_for_cat = AiData.get_token_size_by_category(category_id=cat.id)
            total_tokens += token_size_for_cat

        # Return the average token size for headings across all categories
        return total_tokens // total_categories if total_categories > 0 else 0


class AiData(models.Model):
    categories = models.ManyToManyField(Category, related_name="articles")
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
    def getAllHeadingsByCat(cls, cat):
        # Retrieve all records filtered by category
        all_data = cls.objects.filter(categories=cat)
        # Format each record as 'id:{number}-heading:{heading};'
        result = []
        for data in all_data:
            result.append(f"id:({data.id})-heading:({data.heading});")
        # Return the list of formatted strings
        return " ".join(result)

    @classmethod
    def getAllHeadingsLength(cls):
        # Retrieve all records from the database
        all_data = cls.objects.all()
        # Format each record as 'id:{number}-heading:{heading};'
        result = []
        for data in all_data:
            result.append(f"id:({data.id})-heading:({data.heading});")
        # Return the list of formatted strings
        return len(" ".join(result))

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

        mean_length = total_length // count
        return mean_length

    @classmethod
    def calculate_token_size(cls, content):
        """
        Simple token size calculation: assume 1 token for every 4 characters.
        """
        return len(content) // 4

    @classmethod
    def get_token_size_by_category(cls, category_id):
        """
        Calculate the total token size for all articles in the specified category.
        Uses a simple method of dividing content length by 4.
        """
        # Retrieve the category object first
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return 0  # Return 0 if the category doesn't exist

        # Retrieve all articles in this category
        articles = cls.objects.filter(categories=category)

        total_tokens = 0
        # Calculate token size for each article's content
        for article in articles:
            total_tokens += cls.calculate_token_size(article.heading)

        return total_tokens
