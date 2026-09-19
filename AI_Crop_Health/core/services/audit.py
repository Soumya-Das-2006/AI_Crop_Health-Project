import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.files import FieldFile
from core.models import AuditLog
from core.middleware import get_current_request

class AuditService:
    SENSITIVE_KEYS = {
        'password', 'password_hash', 'api_key', 'secret', 'token',
        'access_token', 'refresh_token', 'smtp_password', 'whatsapp_token',
        'sms_api_key', 'authorization', 'csrfmiddlewaretoken'
    }

    @classmethod
    def _sanitize_data(cls, data):
        """Recursively removes sensitive values from dicts/lists."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                # Case-insensitive match for sensitive keys
                if any(sensitive in str(k).lower() for sensitive in cls.SENSITIVE_KEYS):
                    sanitized[k] = '********'
                else:
                    sanitized[k] = cls._sanitize_data(v)
            return sanitized
        elif isinstance(data, list):
            return [cls._sanitize_data(item) for item in data]
        elif isinstance(data, tuple):
            return [cls._sanitize_data(item) for item in data]
        elif isinstance(data, FieldFile):
            return data.name or None
        return data

    @classmethod
    def _get_client_ip(cls, request):
        if not request:
            return None
        # Use X-Forwarded-For cautiously. In production, this should be trusted 
        # only if the web server is configured to set it properly.
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @classmethod
    def log(cls, action, model_obj=None, old_values=None, new_values=None, request=None, user=None, success=True, metadata=None):
        """
        Creates an AuditLog entry.
        """
        req = request or get_current_request()
        
        actor = user
        if not actor and req and hasattr(req, 'user') and req.user.is_authenticated:
            actor = req.user

        ip_address = cls._get_client_ip(req)
        user_agent = req.META.get('HTTP_USER_AGENT', '')[:1000] if req else ''

        app_label = ''
        model_name = ''
        object_id = ''
        object_repr = ''

        if model_obj:
            app_label = model_obj._meta.app_label
            model_name = model_obj._meta.model_name
            object_id = str(model_obj.pk)
            object_repr = str(model_obj)[:255]

        # Calculate changed fields
        changed_fields = []
        if old_values and new_values:
            for k, v in new_values.items():
                if k in old_values and old_values[k] != v:
                    changed_fields.append(k)

        # Ensure json serializable and sanitized
        safe_old = cls._sanitize_data(old_values) if old_values else None
        safe_new = cls._sanitize_data(new_values) if new_values else None

        # Convert to strings/basic types using DjangoJSONEncoder and back to dict for the JSONField
        if safe_old:
            safe_old = json.loads(json.dumps(safe_old, cls=DjangoJSONEncoder))
        if safe_new:
            safe_new = json.loads(json.dumps(safe_new, cls=DjangoJSONEncoder))

        AuditLog.objects.create(
            user=actor,
            action=action,
            app_label=app_label,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            old_values=safe_old,
            new_values=safe_new,
            changed_fields=changed_fields,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            metadata=metadata
        )
