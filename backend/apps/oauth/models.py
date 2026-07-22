import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

User = get_user_model()


class OAuthClient(models.Model):
    class ClientType(models.TextChoices):
        CONFIDENTIAL = "confidential", "Confidential"
        PUBLIC = "public", "Public"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="oauth_clients"
    )
    name = models.CharField(max_length=255)
    client_id = models.CharField(max_length=100, unique=True, db_index=True)
    client_secret_hash = models.CharField(max_length=255, blank=True)
    client_type = models.CharField(
        max_length=32, choices=ClientType.choices, default=ClientType.CONFIDENTIAL
    )
    redirect_uris = models.JSONField(default=list)
    allowed_scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_client_secret(self, raw_secret: str):
        self.client_secret_hash = make_password(raw_secret)

    def check_client_secret(self, raw_secret: str) -> bool:
        if not self.client_secret_hash:
            return False
        return check_password(raw_secret, self.client_secret_hash)

    def __str__(self):
        return f"{self.name} ({self.client_id})"


class OAuthAuthorizationCode(models.Model):
    client = models.ForeignKey(
        OAuthClient, on_delete=models.CASCADE, related_name="codes"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="oauth_codes")
    code = models.CharField(max_length=128, unique=True, db_index=True)
    redirect_uri = models.TextField()
    scope = models.TextField()
    code_challenge = models.CharField(max_length=255, blank=True, default="")
    code_challenge_method = models.CharField(max_length=10, blank=True, default="S256")
    nonce = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self) -> bool:
        return not self.is_used and self.expires_at > timezone.now()

    def __str__(self):
        return f"Code for {self.client.name} (user: {self.user.username})"


class OAuthToken(models.Model):
    client = models.ForeignKey(
        OAuthClient, on_delete=models.CASCADE, related_name="tokens"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="oauth_tokens",
    )
    access_token = models.CharField(max_length=255, unique=True, db_index=True)
    refresh_token = models.CharField(
        max_length=255, unique=True, db_index=True, null=True, blank=True
    )
    scope = models.TextField()
    access_token_expires_at = models.DateTimeField()
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_access_token_valid(self) -> bool:
        return not self.is_revoked and self.access_token_expires_at > timezone.now()

    def is_refresh_token_valid(self) -> bool:
        if self.is_revoked or not self.refresh_token:
            return False
        if (
            self.refresh_token_expires_at
            and self.refresh_token_expires_at <= timezone.now()
        ):
            return False
        return True

    def __str__(self):
        return f"Token for {self.client.name}"
