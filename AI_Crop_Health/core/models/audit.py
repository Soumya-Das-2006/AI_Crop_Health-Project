from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import json

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PERMISSION_CHANGE', 'Permission Change'),
        ('ROLE_CHANGE', 'Role Change'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('VERIFY', 'Verify'),
        ('STATUS_CHANGE', 'Status Change'),
        ('AI_REVIEW', 'AI Review'),
        ('NOTIFICATION_SENT', 'Notification Sent'),
        ('NOTIFICATION_FAILED', 'Notification Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    
    # Target Object Info
    app_label = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=255, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    
    # Changes
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changed_fields = models.JSONField(null=True, blank=True, help_text="List of fields that were changed")
    
    # Request Info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(default=True)
    metadata = models.JSONField(null=True, blank=True, help_text="Any additional context")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['app_label', 'model_name']),
            models.Index(fields=['object_id']),
            models.Index(fields=['user', 'action']),
        ]

    def __str__(self):
        status = "Success" if self.success else "Failed"
        if self.object_repr:
            return f"[{self.timestamp}] {self.user} {self.action} {self.object_repr} ({status})"
        return f"[{self.timestamp}] {self.user} {self.action} ({status})"
