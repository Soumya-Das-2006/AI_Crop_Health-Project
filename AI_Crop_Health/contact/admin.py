from django.contrib import admin
from .models import Contact, NewsletterSubscriber, Service, Testimonial, BiodegradableCompany, WasteSubmission
from core.admin import AuditModelAdminMixin
from core.services import AuditService

@admin.register(Contact)
class ContactAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'email', 'location', 'related_work', 'subject', 'created_date', 'is_read')
    list_filter = ('is_read', 'created_date', 'related_work')
    search_fields = ('name', 'email', 'subject')
    readonly_fields = ('created_date',)
    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        for contact in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=contact, request=request, metadata={'status': 'read'})
        self.message_user(request, f'{queryset.count()} contact(s) marked as read.')
    mark_as_read.short_description = "Mark selected contacts as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        for contact in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=contact, request=request, metadata={'status': 'unread'})
        self.message_user(request, f'{queryset.count()} contact(s) marked as unread.')
    mark_as_unread.short_description = "Mark selected contacts as unread"

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('email', 'subscribed_date')
    list_filter = ('subscribed_date',)
    search_fields = ('email',)
    readonly_fields = ('subscribed_date',)

@admin.register(Service)
class ServiceAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    ordering = ('order', 'created_at')

@admin.register(Testimonial)
class TestimonialAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'message')
    readonly_fields = ('created_at',)

@admin.register(BiodegradableCompany)
class BiodegradableCompanyAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'email', 'materials_accepted', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'email', 'materials_accepted')
    readonly_fields = ('created_at',)

@admin.register(WasteSubmission)
class WasteSubmissionAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('farmer_name', 'crop_type', 'waste_type', 'quantity', 'submitted_at', 'is_processed')
    list_filter = ('waste_type', 'submitted_at', 'is_processed')
    search_fields = ('farmer_name', 'crop_type', 'village', 'district', 'state')
    readonly_fields = ('submitted_at',)
    actions = ['mark_as_processed', 'mark_as_unprocessed']

    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True)
        for submission in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=submission, request=request, metadata={'status': 'processed'})
        self.message_user(request, f'{queryset.count()} waste submission(s) marked as processed.')
    mark_as_processed.short_description = "Mark selected submissions as processed"

    def mark_as_unprocessed(self, request, queryset):
        queryset.update(is_processed=False)
        for submission in queryset:
            AuditService.log('STATUS_CHANGE', model_obj=submission, request=request, metadata={'status': 'unprocessed'})
        self.message_user(request, f'{queryset.count()} waste submission(s) marked as unprocessed.')
    mark_as_unprocessed.short_description = "Mark selected submissions as unprocessed"
