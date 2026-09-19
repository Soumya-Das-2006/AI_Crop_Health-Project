from django.contrib import admin
from django.forms.models import model_to_dict
from .models import AuditLog, NotificationRecord, NotificationTemplate
from .services import AuditService

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'model_name', 'object_repr', 'success']
    list_filter = ['action', 'success', 'app_label', 'model_name', 'timestamp']
    search_fields = ['user__username', 'object_repr', 'ip_address']
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name', 'subject']


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'recipient_contact', 'channel', 'status', 'retry_count']
    list_filter = ['channel', 'status', 'created_at']
    search_fields = ['recipient_contact', 'subject', 'provider_message_id']
    readonly_fields = ['created_at', 'sent_at', 'delivered_at', 'failed_at', 'failure_reason', 'retry_count']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # We shouldn't change records directly except maybe to manually retry
        return False


class AuditModelAdminMixin:
    """
    Mixin for ModelAdmin to integrate AuditService for change/delete/add tracking.
    """
    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        old_values = None
        
        if change:
            # Re-fetch old obj to get old values. 
            # (Note: For performance on huge objects, you might want a more optimized approach)
            try:
                old_obj = obj.__class__.objects.get(pk=obj.pk)
                old_values = model_to_dict(old_obj)
            except obj.__class__.DoesNotExist:
                pass
                
        super().save_model(request, obj, form, change)
        
        new_values = model_to_dict(obj)
        action = 'UPDATE' if change else 'CREATE'
        
        AuditService.log(
            action=action,
            model_obj=obj,
            old_values=old_values,
            new_values=new_values,
            request=request
        )

    def delete_model(self, request, obj):
        old_values = model_to_dict(obj)
        super().delete_model(request, obj)
        AuditService.log(
            action='DELETE',
            model_obj=obj,
            old_values=old_values,
            request=request
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            AuditService.log(
                action='DELETE',
                model_obj=obj,
                old_values=model_to_dict(obj),
                request=request
            )
        super().delete_queryset(request, queryset)
