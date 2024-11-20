from rest_framework import serializers
from .models import Client, Conversation, Message


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "external_id", "name", "email", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "client", "created_at"]

    def create(self, validated_data):
        client = validated_data.get("client")
        if Conversation.objects.filter(client=client).exists():
            raise serializers.ValidationError(
                "A conversation already exists for this client."
            )
        return super().create(validated_data)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "content", "timestamp"]

    def create(self, validated_data):
        conversation = validated_data.get("conversation")
        if not Conversation.objects.filter(id=conversation.id).exists():
            raise serializers.ValidationError("The conversation does not exist.")
        return super().create(validated_data)


from rest_framework import serializers
from .models import AiData, Category


class AiDataSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all()
    )

    class Meta:
        model = AiData
        fields = ["id", "heading", "content", "categories"]
