from django import template
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Avg
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from core.models import AuditLog, NotificationRecord
from agrolease.models import Land
from detection.models import DiagnosisLog
import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.simple_tag(takes_context=True)
def get_dashboard_metrics(context):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    is_super = user.is_superuser
    is_staff = user.is_staff
    
    metrics = {
        'role': 'Super administrator' if is_super else 'Staff administrator' if is_staff else 'Administrator',
        'is_superuser': is_super,
        'is_staff': is_staff,
        'platform': None,
        'crop_health': None,
        'ai': None,
        'notifications': None,
        'needs_attention': [],
        'system_health': [],
        'quick_actions': []
    }
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # 1. Platform Metrics (Superadmin only or users with view_user)
    if is_super or user.has_perm('auth.view_user'):
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        staff = User.objects.filter(is_staff=True).count()
        new_users = User.objects.filter(date_joined__gte=thirty_days_ago).count()
        
        metrics['platform'] = {
            'total': total_users,
            'active': active_users,
            'staff': staff,
            'new': new_users
        }
        if user.has_perm('auth.add_user') or is_super:
            metrics['quick_actions'].append({
                'label': 'Add user',
                'url': reverse('admin:auth_user_add'),
                'description': 'Create a farmer or staff account'
            })
        
    # 2. Crop Health (Users with view_land and view_diagnosislog)
    if is_super or (user.has_perm('agrolease.view_land') and user.has_perm('detection.view_diagnosislog')):
        total_lands = Land.objects.count()
        total_diagnoses = DiagnosisLog.objects.count()
        healthy = DiagnosisLog.objects.filter(predicted_disease__icontains='Healthy').count()
        disease = DiagnosisLog.objects.exclude(predicted_disease__icontains='Healthy').exclude(predicted_disease__icontains='Unknown').count()
        pending_reviews = DiagnosisLog.objects.filter(admin_reviewed=False).count()
        
        metrics['crop_health'] = {
            'lands': total_lands,
            'diagnoses': total_diagnoses,
            'healthy': healthy,
            'disease': disease,
            'pending': pending_reviews
        }
        
        if pending_reviews > 0:
            metrics['needs_attention'].append({
                'label': f"{pending_reviews} Pending diagnosis reviews",
                'url': f"{reverse('admin:detection_diagnosislog_changelist')}?admin_reviewed__exact=0",
                'icon': 'warning'
            })
            
    # 3. AI Metrics (Users with view_diagnosislog)
    if is_super or user.has_perm('detection.view_diagnosislog'):
        total_preds = DiagnosisLog.objects.count()
        confidence_values = DiagnosisLog.objects.filter(calibrated_confidence__isnull=False)
        high_conf = confidence_values.filter(calibrated_confidence__gte=80).count()
        med_conf = confidence_values.filter(calibrated_confidence__gte=50, calibrated_confidence__lt=80).count()
        low_conf = confidence_values.filter(calibrated_confidence__lt=50).count()
        avg_conf = confidence_values.aggregate(avg=Avg('calibrated_confidence'))['avg'] or 0
        
        metrics['ai'] = {
            'total': total_preds,
            'high': high_conf,
            'med': med_conf,
            'low': low_conf,
            'avg': round(avg_conf, 1)
        }
        
        if low_conf > 0:
            metrics['needs_attention'].append({
                'label': f"{low_conf} Low-confidence predictions",
                'url': f"{reverse('admin:detection_diagnosislog_changelist')}?calibrated_confidence__lt=50",
                'icon': 'warning'
            })
            
    # 4. Notifications
    if is_super or user.has_perm('core.view_notificationrecord'):
        sent = NotificationRecord.objects.filter(status='SENT').count()
        delivered = NotificationRecord.objects.filter(status='DELIVERED').count()
        failed = NotificationRecord.objects.filter(status='FAILED').count()
        pending = NotificationRecord.objects.filter(status='PENDING').count()
        
        metrics['notifications'] = {
            'sent': sent,
            'delivered': delivered,
            'failed': failed,
            'pending': pending
        }
        
        if failed > 0:
            metrics['needs_attention'].append({
                'label': f"{failed} Failed notifications",
                'url': f"{reverse('admin:core_notificationrecord_changelist')}?status__exact=FAILED",
                'icon': 'error'
            })

    # 5. Security Events (AuditLogs with LOGIN_FAILED, SUPERUSER_MODIFIED, etc)
    if is_super or user.has_perm('core.view_auditlog'):
        sec_events = AuditLog.objects.filter(action__in=[
            'LOGIN_FAILED', 'SUPERUSER_MODIFIED', 'STAFF_PERMISSION_CHANGED'
        ], timestamp__gte=thirty_days_ago).count()
        
        if sec_events > 0:
            metrics['needs_attention'].append({
                'label': f"{sec_events} recent security events",
                'url': f"{reverse('admin:core_auditlog_changelist')}?action__in=LOGIN_FAILED,SUPERUSER_MODIFIED,STAFF_PERMISSION_CHANGED",
                'icon': 'error'
            })

    if is_super:
        metrics['quick_actions'].extend([
            {
                'label': 'Manage staff permissions',
                'url': reverse('admin:auth_group_changelist'),
                'description': 'Review groups and access control'
            },
            {
                'label': 'Review audit log',
                'url': reverse('admin:core_auditlog_changelist'),
                'description': 'Inspect platform activity'
            }
        ])

    # 6. System Health
    # DB check
    db_healthy = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_healthy = False
        
    metrics['system_health'].append({'name': 'Database', 'healthy': db_healthy})
    # Mocking external services for now since we don't have real integrations yet
    metrics['system_health'].append({'name': 'AI Service', 'healthy': True})
    metrics['system_health'].append({'name': 'Notifications', 'healthy': True})

    return metrics
