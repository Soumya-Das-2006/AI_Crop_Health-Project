from django.contrib import admin

# Register your models here.
from django.utils.html import format_html
from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone
from datetime import timedelta
from .models import (
    DiagnosisLog,
    QualityRejectionLog,
    FarmerFeedback,
    AgricultureSuggestion,
    AgricultureAlert,
    UserReaction,  # ADDED
    APIAccessLog,  # ADDED
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