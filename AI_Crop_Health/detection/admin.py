from django.contrib import admin

# Register your models here.
from django.utils.html import format_html
from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone
from datetime import timedelta
from core.admin_mixins import ExportCsvMixin

from .models import (
    DetectionHistory,
    DiagnosisLog,
    QualityRejectionLog,
    FarmerFeedback,
    AgricultureSuggestion,
    AgricultureAlert,
    UserReaction,  # ADDED
    APIAccessLog,  # ADDED
    DiagnosisConversation,
    DiagnosisMessage,
    InsectIdentificationLog,
    ChatSession,
    ChatMessage,
)
from core.admin import AuditModelAdminMixin
from core.services import AuditService

@admin.register(DiagnosisLog)
class DiagnosisLogAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    """
    Mission-critical admin interface for auditing AI predictions.
    Enables regulatory compliance and continuous model improvement.
    """
    
    list_display = [
        'timestamp',
        'image_thumbnail',
        'predicted_crop',
        'predicted_disease',
        'confidence_display',
        'status_badge',
        'treatment_provided',
        'farmer_feedback_status',
        'needs_review',
    ]

    list_filter = [
        'diagnosis_status',
        'predicted_crop',
        'passed_quality_check',
        'solutions_shown',
        'used_gemini_validation',
        'admin_reviewed',
        'is_false_positive',
        ('timestamp', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'predicted_crop',
        'predicted_disease',
        'class_label',
        'user_ip',
        'warning_message'
    ]
    
    readonly_fields = [
        'timestamp',
        'image_preview',
        'image_resolution',
        'image_size_kb',
        'quality_score',
        'sharpness_score',
        'brightness_score',
        'class_index',
        'class_label',
        'raw_confidence',
        'calibrated_confidence',
        'entropy_score',
        'gemini_confidence',
        'gemini_recommendation',
        'gemini_concerns',
    ]
    
    fieldsets = [
        ('Request Metadata', {
            'fields': ['timestamp', 'session_id', 'user_ip']
        }),
        ('Uploaded Image', {
            'fields': ['image_preview', 'uploaded_image', 'image_resolution', 'image_size_kb']
        }),
        ('Image Quality Assessment', {
            'fields': [
                'passed_quality_check',
                'quality_score',
                'sharpness_score',
                'brightness_score',
                'quality_failure_reason'
            ]
        }),
        ('ML Prediction', {
            'fields': [
                'predicted_crop',
                'predicted_disease',
                'class_index',
                'class_label'
            ]
        }),
        ('Confidence Analysis', {
            'fields': [
                'raw_confidence',
                'calibrated_confidence',
                'entropy_score',
                'diagnosis_status'
            ],
            'description': 'Raw vs calibrated confidence shows model certainty adjustment'
        }),
        ('Gemini Cross-Validation', {
            'fields': [
                'used_gemini_validation',
                'gemini_confidence',
                'gemini_recommendation',
                'gemini_concerns'
            ],
            'classes': ['collapse']
        }),
        ('Treatment Recommendations', {
            'fields': ['solutions_shown', 'warning_message']
        }),
        ('Farmer Feedback', {
            'fields': [
                'farmer_confirmed',
                'farmer_feedback',
                'farmer_feedback_date'
            ],
            'classes': ['collapse']
        }),
        ('Admin Review', {
            'fields': [
                'admin_reviewed',
                'is_false_positive',
                'correct_diagnosis',
                'admin_notes'
            ]
        })
    ]
    
    actions = [
        'mark_as_reviewed',
        'flag_as_false_positive',
        'export_for_retraining'
    ]
    
    # Custom display methods
    def image_thumbnail(self, obj):
        if obj.uploaded_image:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; object-fit: cover;" />',
                obj.uploaded_image.url
            )
        return '-'
    image_thumbnail.short_description = 'Image'
    
    def image_preview(self, obj):
        if obj.uploaded_image:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px;" />',
                obj.uploaded_image.url
            )
        return '-'
    image_preview.short_description = 'Full Image'
    
    def confidence_display(self, obj):
        calibrated = obj.calibrated_confidence
        raw = obj.raw_confidence

        if not isinstance(calibrated, (int, float)):
            return format_html('<span style="color:red;">Invalid</span>')

        if not isinstance(raw, (int, float)):
            raw = 0.0

        if calibrated >= 98:
            color = 'green'
        elif calibrated >= 95:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<strong style="color:{};">{}%</strong><br>'
            '<small style="color:gray;">Raw: {}%</small>',
            color,
            round(calibrated, 2),
            round(raw, 2),
        )

    confidence_display.short_description = 'Confidence'
    
    def status_badge(self, obj):
        """Visual status badge"""
        colors = {
            'highly_reliable': '#28a745',
            'moderate_confidence': '#ffc107',
            'unreliable': '#dc3545'
        }
        labels = {
            'highly_reliable': '≥98% ✓',
            'moderate_confidence': '95-97%',
            'unreliable': '<95% ✗'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.diagnosis_status, '#6c757d'),
            labels.get(obj.diagnosis_status, obj.diagnosis_status)
        )
    status_badge.short_description = 'Status'
    
    def confidence_display(self, obj):
        calibrated = obj.calibrated_confidence
        raw = obj.raw_confidence

        if not isinstance(calibrated, (int, float)):
            return format_html('<span style="color:red;">Invalid</span>')

        if not isinstance(raw, (int, float)):
            raw = 0.0

        if calibrated >= 98:
            color = 'green'
        elif calibrated >= 95:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<strong style="color:{};">{}%</strong><br>'
            '<small style="color:gray;">Raw: {}%</small>',
            color,
            round(calibrated, 2),
            round(raw, 2),
        )

    confidence_display.short_description = 'Confidence'


    def treatment_provided(self, obj):
        """Did farmer receive treatment advice?"""
        if obj.solutions_shown:
            return format_html('<span style="color: green;">✓ Yes</span>')
        else:
            return format_html('<span style="color: red;">✗ Blocked</span>')
    treatment_provided.short_description = 'Treatment'
    
    def farmer_feedback_status(self, obj):
        """Has farmer provided feedback?"""
        if obj.farmer_confirmed is not None:
            if obj.farmer_confirmed:
                return format_html('<span style="color: green;">✓ Correct</span>')
            else:
                return format_html('<span style="color: red;">✗ Wrong</span>')
        return '-'
    farmer_feedback_status.short_description = 'Feedback'
    
    def needs_review(self, obj):
        """Flag cases needing admin attention"""
        flags = []
        
        # High confidence but near threshold
        if 98 <= obj.calibrated_confidence < 99:
            flags.append('borderline')
        
        # Entropy concerns
        if obj.entropy_score and obj.entropy_score > 0.6:
            flags.append('confused')
        
        # Gemini disagreement
        if obj.used_gemini_validation and obj.gemini_recommendation == 'reject':
            flags.append('rejected')
        
        # Farmer reported wrong
        if obj.farmer_confirmed is False:
            flags.append('WRONG')
        
        if flags:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', ' | '.join(flags))
        return '-'
    needs_review.short_description = 'Flags'
    
    # Custom actions
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(admin_reviewed=True)
        for obj in queryset:
            AuditService.log('AI_REVIEW', model_obj=obj, request=request, metadata={'reviewed': True})
        self.message_user(request, f'{updated} diagnoses marked as reviewed.')
    mark_as_reviewed.short_description = 'Mark selected as reviewed'
    
    def flag_as_false_positive(self, request, queryset):
        updated = queryset.update(is_false_positive=True, admin_reviewed=True)
        for obj in queryset:
            AuditService.log('AI_REVIEW', model_obj=obj, request=request, metadata={'false_positive': True})
        self.message_user(request, f'{updated} diagnoses flagged as false positives.')
    flag_as_false_positive.short_description = 'Flag as false positive'
    
    def export_for_retraining(self, request, queryset):
        # Implement CSV export logic here
        # Export image paths + correct labels for model retraining
        self.message_user(request, 'Export feature coming soon.')
    export_for_retraining.short_description = 'Export for model retraining'
    
    # Analytics in changelist
    def changelist_view(self, request, extra_context=None):
        # Calculate key metrics
        extra_context = extra_context or {}
        
        # Last 7 days stats
        week_ago = timezone.now() - timedelta(days=7)
        recent = DiagnosisLog.objects.filter(timestamp__gte=week_ago)
        
        extra_context['total_diagnoses'] = DiagnosisLog.objects.count()
        extra_context['recent_diagnoses'] = recent.count()
        extra_context['avg_confidence'] = recent.aggregate(Avg('calibrated_confidence'))['calibrated_confidence__avg'] or 0
        extra_context['high_confidence_rate'] = (
            recent.filter(diagnosis_status='highly_reliable').count() / max(recent.count(), 1) * 100
        )
        extra_context['false_positive_rate'] = (
            recent.filter(is_false_positive=True).count() / max(recent.count(), 1) * 100
        )
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(QualityRejectionLog)
class QualityRejectionLogAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    """
    Track images rejected before reaching the model.
    Helps identify farmer education needs.
    """
    list_display = [
        'timestamp',
        'image_thumbnail',
        'image_resolution',
        'quality_score',
        'rejection_summary',
        'user_ip'
    ]
    
    list_filter = [
        ('timestamp', admin.DateFieldListFilter),
    ]
    
    readonly_fields = [
        'timestamp',
        'image_preview',
        'rejection_reasons',
        'image_resolution',
        'sharpness_score',
        'brightness_score',
        'quality_score',
        'user_ip'
    ]
    
    def image_thumbnail(self, obj):
        if obj.uploaded_image:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; object-fit: cover;" />',
                obj.uploaded_image.url
            )
        return '-'
    image_thumbnail.short_description = 'Image'
    
    def image_preview(self, obj):
        if obj.uploaded_image:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px;" />',
                obj.uploaded_image.url
            )
        return '-'
    image_preview.short_description = 'Full Image'
    
    def rejection_summary(self, obj):
        """Summarize why image was rejected"""
        reasons = obj.rejection_reasons
        if isinstance(reasons, dict):
            failed = [k for k, v in reasons.items() if not v.get('passed', True)]
            return ', '.join(failed) if failed else 'Unknown'
        return str(reasons)[:50]
    rejection_summary.short_description = 'Rejection Reasons'


@admin.register(FarmerFeedback)
class FarmerFeedbackAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    """
    Gold standard: Farmer reports on diagnosis accuracy.
    Critical for continuous improvement.
    """
    list_display = [
        'feedback_date',
        'diagnosis_link',
        'was_correct',
        'treatment_worked',
        'actual_disease',
        'has_comments'
    ]
    
    list_filter = [
        'was_correct',
        'treatment_worked',
        ('feedback_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'actual_disease',
        'comments',
        'farmer_location'
    ]
    
    readonly_fields = ['diagnosis_log', 'feedback_date']
    
    def diagnosis_link(self, obj):
        """Link to original diagnosis"""
        url = f'/admin/detection/diagnosislog/{obj.diagnosis_log.id}/change/'
        return format_html(
            '<a href="{}">{} - {}</a>',
            url,
            obj.diagnosis_log.predicted_crop,
            obj.diagnosis_log.predicted_disease
        )
    diagnosis_link.short_description = 'Original Diagnosis'
    
    def has_comments(self, obj):
        return '✓' if obj.comments else '-'
    has_comments.short_description = 'Comments'


# ======================================================
# AGRICULTURE SUGGESTION ADMIN
# ======================================================

@admin.register(AgricultureSuggestion)
class AgricultureSuggestionAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    """
    Admin interface for managing agriculture suggestions.
    """
    
    list_display = [
        'title_preview',
        'category_badge',
        'priority_badge',
        'status_indicator',
        'applicability',
        'engagement_stats',
        'publish_date',
        'expiry_status',
    ]
    
    list_filter = [
        'is_active',
        'category',
        'priority',
        'is_global',
        ('publish_date', admin.DateFieldListFilter),
        ('expiry_date', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'title',
        'description',
        'applicable_locations',
        'affected_crops',
    ]
    
    readonly_fields = [
        'view_count',
        'helpful_count',
        'not_helpful_count',
        'engagement_rate',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        ('Content', {
            'fields': [
                'title',
                'category',
                'description',
            ]
        }),
        ('Targeting & Filters', {
            'fields': [
                'is_global',
                'applicable_locations',
                'applicable_soil_types',
                'applicable_seasons',
            ],
            'description': 'Define who sees this suggestion based on their context'
        }),
        ('Priority & Scheduling', {
            'fields': [
                'priority',
                'is_active',
                'publish_date',
                'expiry_date',
            ]
        }),
        ('Analytics', {
            'fields': [
                'view_count',
                'helpful_count',
                'not_helpful_count',
                'engagement_rate',
            ],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': [
                'created_by',
                'created_at',
                'updated_at',
            ],
            'classes': ['collapse']
        }),
    ]
    
    actions = [
        'activate_suggestions',
        'deactivate_suggestions',
        'mark_as_global',
        'duplicate_suggestion',
        'export_analytics',
    ]
    
    date_hierarchy = 'publish_date'
    
    # Custom display methods
    
    def title_preview(self, obj):
        """Show title with truncation"""
        if len(obj.title) > 60:
            return f"{obj.title[:60]}..."
        return obj.title
    title_preview.short_description = 'Title'
    
    def category_badge(self, obj):
        """Color-coded category badge"""
        colors = {
            'crop': '#28a745',
            'weather': '#17a2b8',
            'soil': '#8B4513',
            'fertilizer': '#6f42c1',
            'pest': '#dc3545',
            'market': '#fd7e14',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.category, '#6c757d'),
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'
    
    def priority_badge(self, obj):
        """Priority indicator"""
        colors = {
            'high': '#dc3545',
            'medium': '#ffc107',
            'low': '#28a745',
        }
        icons = {
            'high': '⬆️',
            'medium': '➡️',
            'low': '⬇️',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            colors.get(obj.priority, '#6c757d'),
            icons.get(obj.priority, ''),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_indicator(self, obj):
        """Active/inactive status"""
        if not obj.is_active:
            return format_html('<span style="color: red;">● Inactive</span>')
        elif obj.is_expired:
            return format_html('<span style="color: orange;">● Expired</span>')
        elif obj.is_currently_active:
            return format_html('<span style="color: green;">● Active</span>')
        else:
            return format_html('<span style="color: gray;">● Scheduled</span>')
    status_indicator.short_description = 'Status'
    
    def applicability(self, obj):
        """Show targeting scope"""
        if obj.is_global:
            return format_html('<strong style="color: blue;">🌍 Global</strong>')

        locations = obj.get_applicable_locations_list()
        soils = obj.get_applicable_soil_types_list()
        seasons = obj.get_applicable_seasons_list()

        parts = []
        if locations:
            parts.append(f"📍 {len(locations)} location(s)")
        if 'any' not in soils:
            parts.append(f"🌱 {len(soils)} soil(s)")
        if 'all' not in seasons:
            parts.append(f"🌦️ {len(seasons)} season(s)")

        content = '<br>'.join(parts) if parts else 'All contexts'
        html = f'<small>{content}</small>'
        return format_html(html)
    applicability.short_description = 'Targeting'
    
    def engagement_stats(self, obj):
        """User engagement metrics"""
        if obj.view_count == 0:
            return '-'
        
        helpful_rate = (obj.helpful_count / obj.view_count * 100) if obj.view_count > 0 else 0
        
        return format_html(
            '<small>👁 {} | 👍 {} | 👎 {}<br>Rate: {:.1f}%</small>',
            obj.view_count,
            obj.helpful_count,
            obj.not_helpful_count,
            helpful_rate
        )
    engagement_stats.short_description = 'Engagement'
    
    def expiry_status(self, obj):
        """Show expiry information"""
        if not obj.expiry_date:
            return format_html('<span style="color: gray;">No expiry</span>')
        
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        
        days_left = (obj.expiry_date - timezone.now()).days
        if days_left <= 3:
            return format_html('<span style="color: orange;">{} days left</span>', days_left)
        
        return format_html('<span style="color: green;">{} days left</span>', days_left)
    expiry_status.short_description = 'Expiry'
    
    def engagement_rate(self, obj):
        """Calculate engagement rate"""
        if obj.view_count == 0:
            return "0%"
        rate = (obj.helpful_count / obj.view_count * 100)
        return f"{rate:.1f}%"
    engagement_rate.short_description = 'Helpfulness Rate'
    
    # Custom actions
    
    def activate_suggestions(self, request, queryset):
        """Bulk activate suggestions"""
        updated = queryset.update(is_active=True)
        for obj in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=obj, request=request, metadata={'action': 'activated'})
        self.message_user(request, f'{updated} suggestion(s) activated.')
    activate_suggestions.short_description = 'Activate selected suggestions'
    
    def deactivate_suggestions(self, request, queryset):
        """Bulk deactivate suggestions"""
        updated = queryset.update(is_active=False)
        for obj in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=obj, request=request, metadata={'action': 'deactivated'})
        self.message_user(request, f'{updated} suggestion(s) deactivated.')
    deactivate_suggestions.short_description = 'Deactivate selected suggestions'
    
    def mark_as_global(self, request, queryset):
        """Mark suggestions as global"""
        updated = queryset.update(is_global=True)
        self.message_user(request, f'{updated} suggestion(s) marked as global.')
    mark_as_global.short_description = 'Mark as global (all users)'
    
    def duplicate_suggestion(self, request, queryset):
        """Duplicate selected suggestions"""
        count = 0
        for obj in queryset:
            obj.pk = None
            obj.title = f"{obj.title} (Copy)"
            obj.is_active = False
            obj.save()
            count += 1
        self.message_user(request, f'{count} suggestion(s) duplicated (marked inactive).')
    duplicate_suggestion.short_description = 'Duplicate selected'
    
    def export_analytics(self, request, queryset):
        """Export analytics (placeholder)"""
        self.message_user(request, 'Analytics export feature coming soon.')
    export_analytics.short_description = 'Export analytics'
    
    # Dashboard metrics
    
    def changelist_view(self, request, extra_context=None):
        """Add analytics to admin dashboard"""
        extra_context = extra_context or {}
        
        # Overall stats
        total = AgricultureSuggestion.objects.count()
        active = AgricultureSuggestion.objects.filter(is_active=True).count()
        global_count = AgricultureSuggestion.objects.filter(is_global=True).count()
        
        # Engagement stats
        total_views = AgricultureSuggestion.objects.aggregate(Sum('view_count'))['view_count__sum'] or 0
        total_helpful = AgricultureSuggestion.objects.aggregate(Sum('helpful_count'))['helpful_count__sum'] or 0
        
        # Category breakdown
        by_category = AgricultureSuggestion.objects.values('category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        extra_context.update({
            'total_suggestions': total,
            'active_suggestions': active,
            'global_suggestions': global_count,
            'total_views': total_views,
            'total_helpful': total_helpful,
            'avg_helpfulness': (total_helpful / total_views * 100) if total_views > 0 else 0,
            'by_category': by_category,
        })
        
        return super().changelist_view(request, extra_context=extra_context)


# ======================================================
# AGRICULTURE ALERT ADMIN
# ======================================================

@admin.register(AgricultureAlert)
class AgricultureAlertAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    """
    Admin interface for managing agriculture alerts.
    """
    
    list_display = [
        'title_preview',
        'alert_type_badge',
        'severity_badge',
        'status_indicator',
        'validity_period',
        'applicability',
        'pin_status',
        'view_count',
    ]
    
    list_filter = [
        'is_active',
        'alert_type',
        'severity',
        'is_pinned',
        'is_global',
        ('valid_from', admin.DateFieldListFilter),
        ('valid_until', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'title',
        'message',
        'affected_crops',
        'applicable_locations',
    ]
    
    readonly_fields = [
        'view_count',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        ('Alert Details', {
            'fields': [
                'alert_type',
                'severity',
                'title',
                'message',
                'affected_crops',
            ]
        }),
        ('Targeting & Filters', {
            'fields': [
                'is_global',
                'applicable_locations',
                'applicable_soil_types',
            ],
            'description': 'Define who sees this alert'
        }),
        ('Validity & Display', {
            'fields': [
                'valid_from',
                'valid_until',
                'is_active',
                'is_pinned',
            ]
        }),
        ('Analytics', {
            'fields': [
                'view_count',
            ],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': [
                'created_by',
                'created_at',
                'updated_at',
            ],
            'classes': ['collapse']
        }),
    ]
    
    actions = [
        'activate_alerts',
        'deactivate_alerts',
        'pin_alerts',
        'unpin_alerts',
        'extend_validity',
    ]
    
    date_hierarchy = 'valid_from'
    
    # Custom display methods
    
    def title_preview(self, obj):
        """Show title with truncation"""
        if len(obj.title) > 60:
            return f"{obj.title[:60]}..."
        return obj.title
    title_preview.short_description = 'Title'
    
    def alert_type_badge(self, obj):
        """Color-coded alert type"""
        colors = {
            'weather': '#17a2b8',
            'pest': '#dc3545',
            'market': '#fd7e14',
            'disease': '#e83e8c',
            'advisory': '#6c757d',
        }
        icons = {
            'weather': '🌦️',
            'pest': '🐛',
            'market': '💰',
            'disease': '🦠',
            'advisory': '📢',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            colors.get(obj.alert_type, '#6c757d'),
            icons.get(obj.alert_type, ''),
            obj.get_alert_type_display()
        )
    alert_type_badge.short_description = 'Type'
    
    def severity_badge(self, obj):
        """Severity indicator with color"""
        colors = {
            'critical': '#dc3545',
            'warning': '#ffc107',
            'info': '#17a2b8',
        }
        icons = {
            'critical': '🔴',
            'warning': '🟡',
            'info': '🔵',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{} {}</span>',
            colors.get(obj.severity, '#6c757d'),
            icons.get(obj.severity, ''),
            obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'

    def status_indicator(self, obj):
        """Active/inactive status"""
        if not obj.is_active:
            return format_html('<span style="color: red;">● Inactive</span>')
        elif not obj.is_currently_valid:
            return format_html('<span style="color: orange;">● Expired</span>')
        else:
            return format_html('<span style="color: green;">● Active</span>')
    status_indicator.short_description = 'Status'
    
    def validity_period(self, obj):
        """Show validity time range"""
        now = timezone.now()
        
        if obj.valid_until < now:
            status = '<span style="color: red;">Expired</span>'
        elif obj.valid_from > now:
            status = '<span style="color: gray;">Future</span>'
        else:
            hours_left = int((obj.valid_until - now).total_seconds() / 3600)
            if hours_left < 24:
                status = f'<span style="color: orange;">{hours_left}h left</span>'
            else:
                days_left = hours_left // 24
                status = f'<span style="color: green;">{days_left}d left</span>'
        
        return format_html(
            '<small>{}<br>{}</small>',
            status,
            obj.valid_until.strftime('%Y-%m-%d %H:%M')
        )
    validity_period.short_description = 'Valid Until'
    
    def applicability(self, obj):
        """Show targeting scope"""
        if obj.is_global:
            return format_html('<strong style="color: blue;">🌍 Global</strong>')
        
        locations = obj.get_applicable_locations_list()
        soils = obj.get_applicable_soil_types_list()
        crops = obj.get_affected_crops_list()
        
        parts = []
        if locations:
            parts.append(f"📍 {len(locations)} location(s)")
        if 'any' not in soils:
            parts.append(f"🌱 {len(soils)} soil(s)")
        if crops:
            parts.append(f"🌾 {len(crops)} crop(s)")
        
        return format_html('<small>{}</small>', '<br>'.join(parts) if parts else 'All')
    applicability.short_description = 'Scope'
    
    def pin_status(self, obj):
        """Show if alert is pinned"""
        if obj.is_pinned:
            return format_html('<span style="color: red; font-size: 18px;">📌</span>')
        return '-'
    pin_status.short_description = 'Pinned'
    
    # Custom actions
    
    def activate_alerts(self, request, queryset):
        """Bulk activate alerts"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} alert(s) activated.')
    activate_alerts.short_description = 'Activate selected alerts'
    
    def deactivate_alerts(self, request, queryset):
        """Bulk deactivate alerts"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} alert(s) deactivated.')
    deactivate_alerts.short_description = 'Deactivate selected alerts'
    
    def pin_alerts(self, request, queryset):
        """Pin alerts to top"""
        updated = queryset.update(is_pinned=True)
        self.message_user(request, f'{updated} alert(s) pinned.')
    pin_alerts.short_description = 'Pin to top'
    
    def unpin_alerts(self, request, queryset):
        """Unpin alerts"""
        updated = queryset.update(is_pinned=False)
        self.message_user(request, f'{updated} alert(s) unpinned.')
    unpin_alerts.short_description = 'Unpin'
    
    def extend_validity(self, request, queryset):
        """Extend validity by 7 days"""
        for alert in queryset:
            alert.valid_until = alert.valid_until + timedelta(days=7)
            alert.save()
        self.message_user(request, f'{queryset.count()} alert(s) extended by 7 days.')
    extend_validity.short_description = 'Extend validity by 7 days'
    
    # Dashboard metrics
    
    def changelist_view(self, request, extra_context=None):
        """Add analytics to admin dashboard"""
        extra_context = extra_context or {}
        
        now = timezone.now()
        
        # Overall stats
        total = AgricultureAlert.objects.count()
        active = AgricultureAlert.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).count()
        
        # Severity breakdown
        critical = AgricultureAlert.objects.filter(severity='critical', is_active=True).count()
        warning = AgricultureAlert.objects.filter(severity='warning', is_active=True).count()
        
        # Total views
        total_views = AgricultureAlert.objects.aggregate(Sum('view_count'))['view_count__sum'] or 0
        
        extra_context.update({
            'total_alerts': total,
            'active_alerts': active,
            'critical_alerts': critical,
            'warning_alerts': warning,
            'total_alert_views': total_views,
        })
        
        return super().changelist_view(request, extra_context=extra_context)


# ======================================================
# USER REACTION ADMIN
# ======================================================

@admin.register(UserReaction)
class UserReactionAdmin(admin.ModelAdmin):
    """
    Admin interface for tracking user reactions to suggestions and alerts.
    """
    
    list_display = [
        'created_at',
        'content_type',
        'reaction_type',
        'user_location',
        'user_soil_type',
        'user_season',
        'session_id',
    ]
    
    list_filter = [
        'reaction_type',
        'user_soil_type',
        'user_season',
        ('created_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'session_id',
        'user_ip',
        'user_location',
    ]
    
    readonly_fields = [
        'created_at',
        'session_id',
        'user_ip',
        'user_location',
        'user_soil_type',
        'user_season',
    ]
    
    fieldsets = [
        ('Content', {
            'fields': [
                'suggestion',
                'alert',
                'reaction_type',
            ]
        }),
        ('User Context', {
            'fields': [
                'user_location',
                'user_soil_type',
                'user_season',
            ],
            'classes': ['collapse']
        }),
        ('Tracking', {
            'fields': [
                'session_id',
                'user_ip',
                'created_at',
            ],
            'classes': ['collapse']
        }),
    ]
    
    actions = [
        'export_reactions',
    ]
    
    date_hierarchy = 'created_at'
    
    # Custom display methods
    
    def content_type(self, obj):
        """Show whether this is for a suggestion or alert"""
        if obj.suggestion:
            return format_html('<span style="color: blue;">📋 Suggestion</span>')
        elif obj.alert:
            return format_html('<span style="color: orange;">⚠️ Alert</span>')
        return '-'
    content_type.short_description = 'Content Type'
    
    # Custom actions
    
    def export_reactions(self, request, queryset):
        """Export reaction data (placeholder)"""
        self.message_user(request, 'Export feature coming soon.')
    export_reactions.short_description = 'Export selected reactions'
    
    # Analytics
    
    def changelist_view(self, request, extra_context=None):
        """Add analytics to admin dashboard"""
        extra_context = extra_context or {}
        
        # Overall stats
        total = UserReaction.objects.count()
        by_reaction_type = UserReaction.objects.values('reaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        recent = UserReaction.objects.filter(created_at__gte=week_ago).count()
        
        extra_context.update({
            'total_reactions': total,
            'by_reaction_type': by_reaction_type,
            'recent_reactions': recent,
        })
        
        return super().changelist_view(request, extra_context=extra_context)


# ======================================================
# API ACCESS LOG ADMIN
# ======================================================

@admin.register(APIAccessLog)
class APIAccessLogAdmin(admin.ModelAdmin):
    """
    Admin interface for monitoring API access attempts.
    """
    
    list_display = [
        'timestamp',
        'api_key_status',
        'location',
        'http_status_badge',
        'suggestions_count',
        'alerts_count',
        'user_ip',
    ]
    
    list_filter = [
        'is_valid_key',
        'http_status',
        ('timestamp', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'location',
        'soil_type',
        'season',
        'user_ip',
        'error_message',
    ]
    
    readonly_fields = [
        'timestamp',
        'api_key_provided',
        'is_valid_key',
        'location',
        'soil_type',
        'season',
        'http_status',
        'suggestions_count',
        'alerts_count',
        'user_ip',
        'user_agent',
        'error_message',
    ]
    
    fieldsets = [
        ('Authentication', {
            'fields': [
                'api_key_provided',
                'is_valid_key',
            ]
        }),
        ('Request Parameters', {
            'fields': [
                'location',
                'soil_type',
                'season',
            ]
        }),
        ('Response', {
            'fields': [
                'http_status',
                'suggestions_count',
                'alerts_count',
                'error_message',
            ]
        }),
        ('Client Info', {
            'fields': [
                'user_ip',
                'user_agent',
            ],
            'classes': ['collapse']
        }),
    ]
    
    actions = [
        'export_access_logs',
    ]
    
    date_hierarchy = 'timestamp'
    
    # Custom display methods
    
    def api_key_status(self, obj):
        """Show API key status"""
        if obj.is_valid_key:
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Invalid</span>')
    api_key_status.short_description = 'API Key'
    
    def http_status_badge(self, obj):
        """Color-coded HTTP status"""
        if 200 <= obj.http_status < 300:
            color = 'green'
        elif 400 <= obj.http_status < 500:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.http_status
        )
    http_status_badge.short_description = 'Status'
    
    # Custom actions
    
    def export_access_logs(self, request, queryset):
        """Export access logs (placeholder)"""
        self.message_user(request, 'Export feature coming soon.')
    export_access_logs.short_description = 'Export selected logs'
    
    # Analytics
    
    def changelist_view(self, request, extra_context=None):
        """Add analytics to admin dashboard"""
        extra_context = extra_context or {}
        
        # Overall stats
        total = APIAccessLog.objects.count()
        valid_keys = APIAccessLog.objects.filter(is_valid_key=True).count()
        invalid_keys = APIAccessLog.objects.filter(is_valid_key=False).count()
        
        # Status breakdown
        success_count = APIAccessLog.objects.filter(http_status=200).count()
        error_count = APIAccessLog.objects.filter(Q(http_status=400) | Q(http_status=403) | Q(http_status=500)).count()
        
        # Last 24 hours
        day_ago = timezone.now() - timedelta(days=1)
        recent = APIAccessLog.objects.filter(timestamp__gte=day_ago).count()
        
        # API usage by location
        top_locations = APIAccessLog.objects.values('location').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        extra_context.update({
            'total_logs': total,
            'valid_keys': valid_keys,
            'invalid_keys': invalid_keys,
            'success_rate': (success_count / total * 100) if total > 0 else 0,
            'error_rate': (error_count / total * 100) if total > 0 else 0,
            'recent_requests': recent,
            'top_locations': top_locations,
        })
        
        return super().changelist_view(request, extra_context=extra_context)

# ======================================================
# ASK AI ADMIN
# ======================================================

class DiagnosisMessageInline(admin.TabularInline):
    """Full thread, read-only, shown inline on the conversation page."""

    model = DiagnosisMessage
    extra = 0
    can_delete = False
    fields = [
        'created_at', 'role', 'preset', 'content',
        'treatment_gated', 'latency_ms', 'error', 'flagged_by_admin',
    ]
    readonly_fields = [
        'created_at', 'role', 'preset', 'content',
        'treatment_gated', 'latency_ms', 'error',
    ]
    ordering = ['created_at', 'id']

    def has_add_permission(self, request, obj=None):
        # Transcripts are evidence of what a farmer was told. Admins review
        # and flag them; they do not author turns after the fact.
        return False


@admin.register(DiagnosisConversation)
class DiagnosisConversationAdmin(admin.ModelAdmin):
    """Audit view of Ask AI threads, anchored to the diagnosed photo."""

    list_display = [
        'id',
        'created_at',
        'image_thumbnail',
        'diagnosis_summary',
        'who',
        'turns',
        'gated_badge',
        'error_badge',
    ]
    list_filter = [
        'created_at',
        'language',
        'diagnosis_log__diagnosis_status',
        'diagnosis_log__provider',
    ]
    search_fields = [
        'messages__content',
        'diagnosis_log__predicted_crop',
        'diagnosis_log__predicted_disease',
        'user__username',
        'session_id',
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at', 'diagnosis_log', 'user', 'session_id']
    inlines = [DiagnosisMessageInline]

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('diagnosis_log', 'user')
            .prefetch_related('messages')
        )

    @admin.display(description='Photo')
    def image_thumbnail(self, obj):
        image = obj.diagnosis_log.uploaded_image if obj.diagnosis_log else None
        if not image:
            return '-'
        return format_html(
            '<img src="{}" style="width:56px;height:56px;object-fit:cover;border-radius:4px;" />',
            image.url,
        )

    @admin.display(description='Diagnosis')
    def diagnosis_summary(self, obj):
        log = obj.diagnosis_log
        if not log:
            return '-'
        return format_html(
            '{} / {} <span style="color:#888;">({:.0f}% - {})</span>',
            log.predicted_crop or '?',
            log.predicted_disease or '?',
            log.calibrated_confidence or 0,
            log.diagnosis_status,
        )

    @admin.display(description='Asked by')
    def who(self, obj):
        if obj.user_id:
            return obj.user.username
        return format_html('<span style="color:#888;">anon {}</span>', (obj.session_id or '')[:8])

    @admin.display(description='Turns')
    def turns(self, obj):
        return obj.messages.count()

    @admin.display(description='Treatment gated')
    def gated_badge(self, obj):
        """
        Whether the safety gate suppressed chemical advice in this thread.
        This is the column a reviewer checks first: it says whether the farmer
        was correctly steered to a human instead of to a pesticide shop.
        """
        gated = obj.messages.filter(treatment_gated=True).exists()
        if gated:
            return format_html('<span style="color:#b36b00;">withheld</span>')
        return format_html('<span style="color:#1a7f37;">allowed</span>')

    @admin.display(description='Errors')
    def error_badge(self, obj):
        count = obj.messages.exclude(error__isnull=True).exclude(error='').count()
        if not count:
            return '-'
        return format_html('<span style="color:#b00020;">{} failed</span>', count)


@admin.register(DiagnosisMessage)
class DiagnosisMessageAdmin(admin.ModelAdmin):
    """
    Flat view of every turn, for spotting patterns across conversations -
    which preset questions farmers actually press, and where answers fail.
    """

    list_display = [
        'created_at', 'role', 'preset', 'short_content',
        'treatment_gated', 'latency_ms', 'has_error', 'flagged_by_admin',
    ]
    list_filter = [
        'role', 'preset', 'treatment_gated', 'flagged_by_admin', 'created_at', 'model_name',
    ]
    search_fields = ['content', 'admin_note']
    date_hierarchy = 'created_at'
    list_editable = ['flagged_by_admin']
    readonly_fields = [
        'conversation', 'role', 'content', 'preset', 'created_at',
        'model_name', 'latency_ms', 'error', 'treatment_gated',
    ]
    actions = ['flag_for_review', 'clear_flag']

    @admin.display(description='Message')
    def short_content(self, obj):
        if obj.error:
            return format_html('<em style="color:#b00020;">failed</em>')
        return (obj.content[:90] + '...') if len(obj.content) > 90 else obj.content

    @admin.display(description='Error', boolean=True)
    def has_error(self, obj):
        return bool(obj.error)

    @admin.action(description='Flag selected messages for expert review')
    def flag_for_review(self, request, queryset):
        updated = queryset.update(flagged_by_admin=True)
        self.message_user(request, f"{updated} message(s) flagged for review.")

    @admin.action(description='Clear review flag')
    def clear_flag(self, request, queryset):
        updated = queryset.update(flagged_by_admin=False)
        self.message_user(request, f"{updated} message(s) unflagged.")


@admin.register(DetectionHistory)
class DetectionHistoryAdmin(ExportCsvMixin, admin.ModelAdmin):
    """
    Scans a farmer explicitly saved to their profile.

    Was not registered, so support had no way to see what a farmer had kept
    when they called about a past diagnosis.
    """

    list_display = ('saved_at', 'user', 'crop', 'disease', 'confidence', 'short_notes')
    list_filter = ('saved_at',)
    search_fields = ('user__username', 'user__email', 'notes',
                     'diagnosis_log__predicted_crop', 'diagnosis_log__predicted_disease')
    list_select_related = ('user', 'diagnosis_log')
    date_hierarchy = 'saved_at'
    readonly_fields = ('saved_at', 'user', 'diagnosis_log')
    actions = ('export_as_csv',)
    csv_export_fields = ('id', 'saved_at', 'notes')

    @admin.display(description='Crop', ordering='diagnosis_log__predicted_crop')
    def crop(self, obj):
        return obj.diagnosis_log.predicted_crop

    @admin.display(description='Disease', ordering='diagnosis_log__predicted_disease')
    def disease(self, obj):
        return obj.diagnosis_log.predicted_disease

    @admin.display(description='Confidence')
    def confidence(self, obj):
        value = obj.diagnosis_log.calibrated_confidence
        return f'{value:.1f}%' if value is not None else '-'

    @admin.display(description='Notes')
    def short_notes(self, obj):
        if not obj.notes:
            return '-'
        return (obj.notes[:60] + '...') if len(obj.notes) > 60 else obj.notes

    def has_add_permission(self, request):
        # Created by farmers from the app, never by staff.
        return False


# ======================================================
# INSECT IDENTIFICATION ADMIN
# ======================================================

@admin.register(InsectIdentificationLog)
class InsectIdentificationLogAdmin(admin.ModelAdmin):
    """
    Audit view for insect identifications.

    pest_status is editable here on purpose: insect.id reports danger-to-humans
    for only about 3.5% of taxa, so the app ships every row as 'unknown'. An
    agronomist curating this column over time is how a trustworthy pest list
    gets built - from reviewed real identifications rather than from a guess
    baked into code.
    """

    list_display = [
        'timestamp',
        'image_thumbnail',
        'identified_as',
        'confidence_display',
        'status_badge',
        'pest_status',
        'farmer_confirmed',
        'admin_reviewed',
    ]
    list_filter = [
        'identification_status',
        'pest_status',
        'admin_reviewed',
        'farmer_confirmed',
        'timestamp',
    ]
    search_fields = ['common_name', 'scientific_name', 'taxon_id', 'correct_identification']
    date_hierarchy = 'timestamp'
    list_editable = ['pest_status', 'admin_reviewed']
    readonly_fields = [
        'timestamp', 'user', 'session_id', 'user_ip', 'uploaded_image',
        'image_resolution', 'image_size_kb', 'common_name', 'scientific_name',
        'taxon_id', 'confidence', 'top_predictions', 'margin', 'entropy_score',
        'identification_status', 'provider', 'model_version',
    ]

    @admin.display(description='Photo')
    def image_thumbnail(self, obj):
        if not obj.uploaded_image:
            return '-'
        return format_html(
            '<img src="{}" style="width:56px;height:56px;object-fit:cover;border-radius:4px;" />',
            obj.uploaded_image.url,
        )

    @admin.display(description='Identified as')
    def identified_as(self, obj):
        if not obj.common_name and not obj.scientific_name:
            return '-'
        if obj.scientific_name and obj.scientific_name != obj.common_name:
            return format_html(
                '{}<br><em style="color:#888;font-size:.85em;">{}</em>',
                obj.common_name or '-', obj.scientific_name,
            )
        return obj.common_name or obj.scientific_name

    @admin.display(description='Confidence')
    def confidence_display(self, obj):
        colour = '#1a7f37' if obj.confidence >= 55 else (
            '#b36b00' if obj.confidence >= 25 else '#b00020'
        )
        return format_html(
            '<span style="color:{};font-weight:600;">{:.1f}%</span>', colour, obj.confidence
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colours = {
            'reliable': '#1a7f37',
            'caution': '#b36b00',
            'unreliable': '#b00020',
            'not_an_insect': '#888',
        }
        return format_html(
            '<span style="color:{};">{}</span>',
            colours.get(obj.identification_status, '#888'),
            obj.get_identification_status_display(),
        )


# ======================================================
# CHATBOT ADMIN
# ======================================================

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    can_delete = False
    fields = ['created_at', 'role', 'content', 'provider', 'latency_ms',
              'used_fallback', 'error', 'flagged_by_admin']
    readonly_fields = ['created_at', 'role', 'content', 'provider', 'latency_ms',
                       'used_fallback', 'error']
    ordering = ['created_at', 'id']

    def has_add_permission(self, request, obj=None):
        # Transcripts are a record of what a farmer was told, not a draft.
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """
    What farmers actually ask.

    More valuable than the answers: the questions show which crops, seasons and
    problems the product should cover next, straight from real users.
    """

    list_display = ['id', 'started_at', 'who', 'language', 'turns',
                    'providers_used', 'first_question']
    list_filter = ['language', 'started_at', 'messages__provider',
                   'messages__used_fallback']
    search_fields = ['messages__content', 'user__username', 'session_key']
    date_hierarchy = 'started_at'
    readonly_fields = ['user', 'session_key', 'user_ip', 'started_at',
                       'last_active_at', 'language']
    inlines = [ChatMessageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('messages')

    @admin.display(description='Asked by')
    def who(self, obj):
        if obj.user_id:
            return obj.user.username
        return format_html('<span style="color:#888;">anon {}</span>', obj.session_key[:8])

    @admin.display(description='Turns')
    def turns(self, obj):
        return obj.messages.count()

    @admin.display(description='Answered by')
    def providers_used(self, obj):
        """
        Which provider carried this conversation. If Gemini is answering
        everything, Groq is failing silently and this is where you notice.
        """
        names = sorted({m.provider for m in obj.messages.all() if m.provider})
        if not names:
            return '-'
        colour = '#b36b00' if 'gemini' in names and 'groq' not in names else '#1a7f37'
        return format_html('<span style="color:{};">{}</span>', colour, ', '.join(names))

    @admin.display(description='First question')
    def first_question(self, obj):
        first = obj.messages.filter(role=ChatMessage.ROLE_USER).first()
        if not first:
            return '-'
        return (first.content[:70] + '...') if len(first.content) > 70 else first.content


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Flat view across conversations, for spotting patterns and failures."""

    list_display = ['created_at', 'role', 'language', 'short_content',
                    'provider', 'latency_ms', 'used_fallback', 'has_error',
                    'flagged_by_admin']
    list_filter = ['role', 'provider', 'language', 'used_fallback',
                   'flagged_by_admin', 'created_at']
    search_fields = ['content', 'admin_note']
    date_hierarchy = 'created_at'
    list_editable = ['flagged_by_admin']
    readonly_fields = ['session', 'role', 'content', 'language', 'created_at',
                       'provider', 'model_name', 'latency_ms', 'error',
                       'used_fallback']
    actions = ['flag_for_review', 'clear_flag']

    @admin.display(description='Message')
    def short_content(self, obj):
        if obj.error:
            return format_html('<em style="color:#b00020;">failed</em>')
        return (obj.content[:90] + '...') if len(obj.content) > 90 else obj.content

    @admin.display(description='Error', boolean=True)
    def has_error(self, obj):
        return bool(obj.error)

    @admin.action(description='Flag selected messages for expert review')
    def flag_for_review(self, request, queryset):
        updated = queryset.update(flagged_by_admin=True)
        self.message_user(request, f"{updated} message(s) flagged.")

    @admin.action(description='Clear review flag')
    def clear_flag(self, request, queryset):
        updated = queryset.update(flagged_by_admin=False)
        self.message_user(request, f"{updated} message(s) unflagged.")
