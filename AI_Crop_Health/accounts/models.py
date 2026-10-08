from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

import logging

logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='global_profile')
    
    # Global Identifiers & Verification
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    
    # Optional Location Data
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every User has a global profile.

    get_or_create on both branches keeps legacy users (created before this model
    existed) backfilled, and is idempotent so a second signal firing cannot
    raise IntegrityError. Wrapped because post_save shares the caller's
    transaction: an exception here would roll back registration itself.
    """
    try:
        UserProfile.objects.get_or_create(user=instance)
    except Exception:
        logger.exception(
            "Could not ensure global UserProfile for user id=%s", instance.pk,
        )
