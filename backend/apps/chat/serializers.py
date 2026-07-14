from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import DirectMessage, Message, UserPublicKey

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "room_id", "username", "content", "created_at"]
        read_only_fields = ["id", "created_at"]


class MessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=4096,
        help_text="The text content of the chat message.",
    )

    class Meta:
        ref_name = "ChatMessageCreate"


class ChatRoomSerializer(serializers.Serializer):
    room_id = serializers.CharField(help_text="Unique identifier for the chat room.")
    last_message = serializers.CharField(
        help_text="Content of the most recent message in the room."
    )
    last_message_at = serializers.DateTimeField(
        help_text="Timestamp of the most recent message."
    )
    participant_count = serializers.IntegerField(
        help_text="Number of distinct users who have sent messages in this room."
    )

    class Meta:
        ref_name = "ChatRoom"


class UserPublicKeySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserPublicKey
        fields = ["id", "username", "public_key", "created_at", "updated_at"]
        read_only_fields = ["id", "username", "created_at", "updated_at"]


class DirectMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)

    class Meta:
        model = DirectMessage
        fields = [
            "id",
            "sender_username",
            "recipient_username",
            "encrypted_content",
            "nonce",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "sender_username", "created_at"]


class DirectMessageCreateSerializer(serializers.Serializer):
    recipient_username = serializers.CharField()
    encrypted_content = serializers.CharField(
        help_text="Base64-encoded ciphertext. Must be encrypted by the sender client-side."
    )
    nonce = serializers.CharField(
        max_length=64,
        help_text="Base64-encoded 24-byte nonce used during encryption.",
    )

    class Meta:
        ref_name = "DirectMessageCreate"
