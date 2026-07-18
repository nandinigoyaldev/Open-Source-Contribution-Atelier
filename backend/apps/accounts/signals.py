"""
Signals for JWT token invalidation.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def invalidate_tokens_on_password_change(sender, instance, **kwargs):
    """
    Invalidate JWT tokens when user password changes.
    """
    if not instance.pk:
        return
    
    try:
        old_user = User.objects.get(pk=instance.pk)
        # Check if password has changed
        if old_user.password != instance.password:
            # Increment token version in user profile
            if hasattr(instance, 'user_profile') and instance.user_profile:
                instance.user_profile.jwt_token_version += 1
                instance.user_profile.last_password_change = timezone.now()
                # We'll save it after the user save
                # Store a flag to save profile later
                instance._token_invalidated = True
            else:
                # Create profile if it doesn't exist
                from apps.accounts.models import UserProfile
                profile = UserProfile.objects.create(
                    user=instance,
                    jwt_token_version=2
                )
                instance._token_invalidated = True
                logger.info(f"Created profile for user {instance.username} during password change")
            
            logger.info(f"JWT tokens invalidated for user {instance.username}")
    except User.DoesNotExist:
        pass


@receiver(post_save, sender=User)
def save_profile_on_password_change(sender, instance, created, **kwargs):
    """
    Save profile after user save if token was invalidated.
    """
    if not created and hasattr(instance, '_token_invalidated') and instance._token_invalidated:
        if hasattr(instance, 'user_profile') and instance.user_profile:
            instance.user_profile.save(update_fields=['jwt_token_version', 'last_password_change'])
            logger.info(f"Profile saved for user {instance.username} after token invalidation")
        instance._token_invalidated = False