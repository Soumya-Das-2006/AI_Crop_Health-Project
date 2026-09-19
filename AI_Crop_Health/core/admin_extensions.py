from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .services import AuditService
from .admin import AuditModelAdminMixin

# Unregister the original User admin
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(AuditModelAdminMixin, BaseUserAdmin):
    """
    Custom User Admin that enforces strict Staff boundaries.
    Staff cannot change Superusers or grant superuser/staff status.
    """
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(is_superuser=False)
        return qs

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            # Staff cannot edit these critical fields
            fields = list(fields)
            fields.extend(['is_superuser', 'is_staff', 'groups', 'user_permissions'])
            if obj and obj.is_superuser:
                # Staff cannot edit superusers at all
                fields.extend(['username', 'email', 'first_name', 'last_name', 'is_active', 'password'])
        return fields

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        # Prevent deleting yourself
        if obj and request.user == obj:
            return False
        return super().has_delete_permission(request, obj)
