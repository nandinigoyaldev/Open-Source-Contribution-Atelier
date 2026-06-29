import secrets
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from .views import unique_username_from_value


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for django-allauth social authentication.
    Ensures unique usernames and proper user creation for GitHub OAuth.
    """

    def pre_social_login(self, request, sociallogin):
        """Hook before social login completion."""
        # Check if user already exists by email
        if sociallogin.is_existing:
            return

        try:
            email = sociallogin.account.extra_data.get("email")
            if email:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass

    def populate_user(self, request, sociallogin, data):
        """Populate user instance with data from social provider."""
        user = super().populate_user(request, sociallogin, data)
        
        # Ensure unique username from GitHub login or email
        github_login = data.get("login")
        email = data.get("email")
        username_source = github_login or email
        
        if username_source:
            user.username = unique_username_from_value(username_source)
        
        # Set a random password for social auth users
        user.set_password(secrets.token_urlsafe(24))
        
        return user