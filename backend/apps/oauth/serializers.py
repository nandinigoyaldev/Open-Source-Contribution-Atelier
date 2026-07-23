from rest_framework import serializers
from .models import OAuthClient, OAuthToken, OAuthAuthorizationCode


class OAuthClientSerializer(serializers.ModelSerializer):
    client_secret = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = OAuthClient
        fields = [
            "id",
            "name",
            "client_id",
            "client_secret",
            "client_type",
            "redirect_uris",
            "allowed_scopes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "client_id", "created_at", "updated_at"]

    def create(self, validated_data):
        import secrets

        raw_secret = validated_data.pop("client_secret", None) or secrets.token_urlsafe(
            32
        )
        client_id = f"client_{secrets.token_hex(12)}"
        client = OAuthClient(client_id=client_id, **validated_data)
        client.set_client_secret(raw_secret)
        client.save()
        client._raw_secret = raw_secret
        return client

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if hasattr(instance, "_raw_secret"):
            ret["client_secret"] = instance._raw_secret
        return ret


class OAuthTokenSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_id = serializers.CharField(source="client.client_id", read_only=True)

    class Meta:
        model = OAuthToken
        fields = [
            "id",
            "client_id",
            "client_name",
            "scope",
            "access_token_expires_at",
            "created_at",
            "is_revoked",
        ]


class AuthorizeRequestSerializer(serializers.Serializer):
    client_id = serializers.CharField()
    redirect_uri = serializers.CharField()
    response_type = serializers.CharField(default="code")
    scope = serializers.CharField(required=False, default="openid profile email")
    code_challenge = serializers.CharField(required=False, allow_blank=True, default="")
    code_challenge_method = serializers.CharField(
        required=False, allow_blank=True, default="S256"
    )
    state = serializers.CharField(required=False, allow_blank=True, default="")
    nonce = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_response_type(self, value):
        if value != "code":
            raise serializers.ValidationError(
                "Unsupported response_type. Must be 'code'."
            )
        return value


class TokenRequestSerializer(serializers.Serializer):
    grant_type = serializers.CharField()
    client_id = serializers.CharField(required=False, allow_blank=True)
    client_secret = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    redirect_uri = serializers.CharField(required=False, allow_blank=True)
    code_verifier = serializers.CharField(required=False, allow_blank=True)
    refresh_token = serializers.CharField(required=False, allow_blank=True)
    scope = serializers.CharField(required=False, allow_blank=True)

    def validate_grant_type(self, value):
        allowed = {"authorization_code", "client_credentials", "refresh_token"}
        if value not in allowed:
            raise serializers.ValidationError(
                f"Invalid grant_type. Supported: {', '.join(allowed)}"
            )
        return value


class TokenIntrospectionSerializer(serializers.Serializer):
    token = serializers.CharField()
    token_type_hint = serializers.CharField(required=False, allow_blank=True)


class TokenRevocationSerializer(serializers.Serializer):
    token = serializers.CharField()
    token_type_hint = serializers.CharField(required=False, allow_blank=True)
