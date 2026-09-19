from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .services import AuditService
from .middleware import get_current_request

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditService.log(
        action='LOGIN',
        user=user,
        request=request,
        success=True,
        metadata={'message': 'User logged in'}
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    AuditService.log(
        action='LOGOUT',
        user=user,
        request=request,
        success=True,
        metadata={'message': 'User logged out'}
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', 'Unknown')
    AuditService.log(
        action='LOGIN_FAILED',
        request=request,
        success=False,
        metadata={'attempted_username': username}
    )

# Track User changes
# We use pre_save to get the old instance, and post_save to log the difference
_user_old_states = {}

@receiver(pre_save, sender=User)
def cache_user_old_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            _user_old_states[instance.pk] = {
                'is_superuser': old_user.is_superuser,
                'is_staff': old_user.is_staff,
                'is_active': old_user.is_active,
                'password': old_user.password,
            }
        except User.DoesNotExist:
            pass

@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    request = get_current_request()
    
    if created:
        AuditService.log(
            action='CREATE',
            model_obj=instance,
            request=request,
            metadata={'message': 'New user created'}
        )
        return

    old_state = _user_old_states.pop(instance.pk, None)
    if not old_state:
        return

    actions = []
    metadata = {}
    
    if old_state['is_superuser'] != instance.is_superuser:
        action = 'SUPERUSER_MODIFIED'
        metadata['superuser_change'] = f"{old_state['is_superuser']} -> {instance.is_superuser}"
        actions.append(action)
        
    if old_state['is_staff'] != instance.is_staff:
        action = 'STAFF_PERMISSION_CHANGED'
        metadata['staff_change'] = f"{old_state['is_staff']} -> {instance.is_staff}"
        actions.append(action)

    if old_state['is_active'] != instance.is_active:
        action = 'ACCOUNT_DISABLED' if not instance.is_active else 'STATUS_CHANGE'
        metadata['active_change'] = f"{old_state['is_active']} -> {instance.is_active}"
        actions.append(action)

    if old_state['password'] != instance.password:
        action = 'PASSWORD_CHANGE'
        metadata['password_changed'] = True
        actions.append(action)
        
    for action in actions:
        AuditService.log(
            action=action,
            model_obj=instance,
            request=request,
            metadata=metadata
        )
