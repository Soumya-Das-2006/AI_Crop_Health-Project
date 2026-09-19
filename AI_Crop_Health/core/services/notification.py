from django.template import Context, Template
from core.models import NotificationRecord, NotificationTemplate
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @classmethod
    def send(cls, recipient, recipient_contact, channel, template_name, context_dict, provider=''):
        """
        Creates a NotificationRecord and attempts delivery.
        In production, the delivery part should be handed off to Celery.
        """
        try:
            template = NotificationTemplate.objects.get(name=template_name)
        except NotificationTemplate.DoesNotExist:
            logger.error(f"NotificationTemplate {template_name} not found.")
            return False

        # Render template
        django_template = Template(template.body)
        rendered_message = django_template.render(Context(context_dict))
        
        subject = template.subject
        if subject:
            subj_template = Template(subject)
            subject = subj_template.render(Context(context_dict))

        # Create Record
        record = NotificationRecord.objects.create(
            recipient=recipient,
            recipient_contact=recipient_contact,
            channel=channel,
            template=template,
            subject=subject,
            message=rendered_message,
            provider=provider,
            status='PENDING'
        )

        # Dispatch
        # TODO: Implement actual Celery integration here instead of synchronous dispatch
        success = cls._dispatch(record)
        return success

    @classmethod
    def _dispatch(cls, record):
        """
        Dummy dispatcher for now. 
        Will update the status to SENT or FAILED based on provider logic.
        """
        # Example dispatch logic based on channel
        # If credentials aren't set, fail safely.
        from django.utils import timezone
        
        try:
            # Fake sending logic
            # In a real app, instantiate provider class like EmailProvider().send(...)
            record.status = 'SENT'
            record.sent_at = timezone.now()
            record.save()
            return True
        except Exception as e:
            record.status = 'FAILED'
            record.failed_at = timezone.now()
            record.failure_reason = str(e)
            record.save()
            
            # Log failure in audit service too
            from .audit import AuditService
            AuditService.log('NOTIFICATION_FAILED', model_obj=record, success=False, metadata={'error': str(e)})
            return False
