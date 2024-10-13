from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Client, Conversation, Message
from .serializers import ClientSerializer, MessageSerializer
from .utils import get_ai_response

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.conf import settings


class ClientConversationView(APIView):
    """
    View to handle client login (based on external_id), conversation management, and message creation.
    """

    def post(self, request):
        # Get client credentials and message from the request
        external_id = request.data.get("external_id")
        name = request.data.get("name")
        email = request.data.get("email")
        user_message = request.data.get("message")  # Message sent by the user

        # Ensure that the user's message is provided
        if not user_message:
            return Response(
                {"error": "User message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Check if the client already exists
            client, created = Client.objects.get_or_create(
                external_id=external_id, defaults={"name": name, "email": email}
            )
            if created and settings.CLIENTS_COUNT < Client.objects.all().count():
                # New client created
                client_serializer = ClientSerializer(client)
                client.delete()
                return Response(
                    {"error": "You have exceeded the maximum allowed limit of users."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {"error": f"An error occurred while accessing the client: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Check if a conversation exists for the client
            conversation, created = Conversation.objects.get_or_create(client=client)
        except Exception as e:
            return Response(
                {
                    "error": f"An error occurred while accessing the conversation: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not conversation.can_send_message():
            return Response(
                {"error": "Daily message limit reached. Please try again tomorrow."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Now that we have the conversation, store the user's message
        message_data = {
            "conversation": conversation.id,
            "sender": "client",  # The user is sending the message
            "content": user_message,
        }

        # Save the message to the conversation
        message_serializer = MessageSerializer(data=message_data)
        if message_serializer.is_valid():
            message_serializer.save()
        else:
            return Response(
                message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        # Get AI response based on the conversation history
        conversation_history = (
            conversation.get_all_messages_str
        )  # Fetch the formatted history

        try:
            ai_response, token_input, token_output = get_ai_response(
                user_message=user_message, user_history=conversation_history
            )
            request.api_key.use_tokens(token_input + token_output)
        except Exception as e:
            return Response(
                {"error": f"An error occurred while getting AI response: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Save the AI's response as a message in the conversation
        ai_message_data = {
            "conversation": conversation.id,
            "sender": "ai",  # The AI is sending the response
            "content": ai_response,
        }

        ai_message_serializer = MessageSerializer(data=ai_message_data)
        if ai_message_serializer.is_valid():
            ai_message_serializer.save()
        else:
            return Response(
                ai_message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        # Respond with the AI's message
        return Response(
            {
                "response": ai_response,  # Return the AI's response
            },
            status=status.HTTP_200_OK,
        )

    def get(self, request):
        # Get the client based on external_id provided in query parameters
        external_id = request.query_params.get("external_id")
        if not external_id:
            return Response(
                {"error": "Client external_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Retrieve the client by external_id
            client = Client.objects.get(external_id=external_id)
        except Client.DoesNotExist:
            return Response(
                {"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred while accessing the client: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get the conversation for the client
            conversation = Conversation.objects.get(client=client)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found for this client."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {
                    "error": f"An error occurred while accessing the conversation: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all messages related to the conversation
        messages = Message.objects.filter(conversation=conversation).order_by(
            "timestamp"
        )

        # Serialize the conversation and messages
        conversation_data = {
            "client": ClientSerializer(client).data,
            "conversation_id": conversation.id,
            "created_at": conversation.created_at,
            "messages": MessageSerializer(messages, many=True).data,
        }

        return Response(conversation_data, status=status.HTTP_200_OK)


def chat_view(self, request, conversation_id):
    """Custom view to display the conversation as a chat interface and handle user input."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.messages.all().order_by("timestamp")

    if request.method == "POST":
        # Get the user's message from the input form
        user_message = request.POST.get("message_content")

        if not user_message:
            error_message = "Iltimos, xabar kiriting."
            context = {
                "conversation": conversation,
                "messages": messages,
                "error_message": error_message,
            }
            return render(request, "admin/conversation_chat.html", context)

        # Create a new message object for the client message
        Message.objects.create(
            conversation=conversation,
            sender="client",
            content=user_message,
            timestamp=timezone.now(),
        )

        # Attempt to get the AI response
        try:
            ai_response, token_input, token_output = get_ai_response(
                user_message,
                extra_data="\nyou are now answering for reporters of daryo not for ordinary client\n",
            )
        except Exception as e:
            print(f"Error getting AI response: {e}")
            ai_response = "Kechirasiz, hozirda javob bera olmadim."

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
