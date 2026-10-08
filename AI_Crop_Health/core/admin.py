from django.contrib import admin, messages
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .admin_mixins import (
    CompressImagesForm, ExportCsvMixin, ReadOnlyAdminMixin, ThumbnailMixin,
)
from .models import (
    AuditLog, FeatureCard, HeroSlide, NotificationRecord,
    NotificationTemplate, SiteSettings,
)
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


# ======================================================================
# SITE SETTINGS - the single page an administrator customises the site from
# ======================================================================

class SiteSettingsForm(CompressImagesForm):
    compress_fields = ('logo', 'social_preview_image')

    class Meta:
        model = SiteSettings
        fields = '__all__'


class HeroSlideForm(CompressImagesForm):
    compress_fields = ('image',)

    class Meta:
        model = HeroSlide
        fields = '__all__'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    """
    Singleton admin.

    A changelist with exactly one row is pure friction, so the list view
    redirects straight into the edit form. Add and delete are disabled: there is
    only ever one configuration.
    """

    save_on_top = True
    readonly_fields = ('updated_at', 'updated_by', 'preview_social_image', 'preview_logo')

    fieldsets = (
        ('Identity', {
            'fields': ('site_name', 'tagline', 'logo', 'preview_logo'),
            'description': 'Shown in the browser tab, the header and link previews.',
        }),
        ('Link preview (WhatsApp, Facebook, X)', {
            'fields': ('social_preview_image', 'preview_social_image'),
            'description': 'A 1200x630 image works best. Leave blank to use the bundled default.',
        }),
        ('Contact details', {
            'fields': ('contact_email', 'contact_phone', 'whatsapp_number', 'address'),
        }),
        ('Social profiles', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url',
                       'linkedin_url', 'youtube_url',
                       'telegram_url', 'github_url'),
            'description': 'Leave blank to hide that icon. A blank field never '
                           'renders a dead link.',
        }),
        ('Analytics', {
            'fields': ('analytics_script_url', 'analytics_site_id'),
            'classes': ('collapse',),
            'description': 'Only loaded after a visitor accepts the cookie banner.',
        }),
        ('Features on / off', {
            'fields': ('enable_marketplace', 'enable_iot', 'enable_chatbot',
                       'enable_agrolease', 'enable_registration'),
            'description': 'Switch a whole section of the site off without a deploy.',
        }),
        ('Crop diagnosis', {
            'fields': ('diagnosis_confidence_threshold', 'diagnosis_disclaimer'),
            'description': 'The threshold flags low-confidence results to farmers. '
                           'It is NOT a measure of how accurate the model is.',
        }),
        ('Maintenance & announcements', {
            'fields': ('maintenance_mode', 'maintenance_message', 'announcement'),
            'classes': ('collapse',),
        }),
        ('Last changed', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Current logo')
    def preview_logo(self, obj):
        if not obj.logo:
            return 'Using the bundled default logo.'
        return format_html('<img src="{}" style="max-height:60px">', obj.logo.url)

    @admin.display(description='Current preview image')
    def preview_social_image(self, obj):
        if not obj.social_preview_image:
            return 'Using the bundled default preview image.'
        return format_html(
            '<img src="{}" style="max-width:320px;border:1px solid #ddd">',
            obj.social_preview_image.url,
        )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        config = SiteSettings.load()
        return HttpResponseRedirect(
            reverse('admin:core_sitesettings_change', args=[config.pk or 1])
        )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        AuditService.log('UPDATE', model_obj=obj, request=request)
        self.message_user(
            request,
            'Site settings saved. Changes appear within 5 minutes, or '
            'immediately on the next page load.',
            level=messages.SUCCESS,
        )


# ======================================================================
# HOMEPAGE CONTENT - editable marketing copy, no developer required
# ======================================================================

@admin.register(HeroSlide)
class HeroSlideAdmin(ThumbnailMixin, admin.ModelAdmin):
    form = HeroSlideForm
    list_display = ('thumbnail', 'heading', 'cta_label', 'sort_order', 'is_active')
    list_display_links = ('heading',)
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('heading', 'body')
    ordering = ('sort_order', 'id')
    actions = ('activate', 'deactivate')

    fieldsets = (
        (None, {'fields': ('heading', 'body', 'is_active', 'sort_order')}),
        ('Image', {
            'fields': ('image', 'image_alt'),
            'description': 'Large uploads are compressed automatically. '
                           'Always write alt text - it is read aloud by screen readers.',
        }),
        ('Button', {
            'fields': ('cta_label', 'cta_url'),
            'description': 'Leave the label blank to show no button on this slide.',
        }),
    )

    @admin.action(description='Show selected slides')
    def activate(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_active=True)} slide(s) now visible.')

    @admin.action(description='Hide selected slides')
    def deactivate(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_active=False)} slide(s) hidden.')


@admin.register(FeatureCard)
class FeatureCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'link_label', 'sort_order', 'is_active')
    list_display_links = ('title',)
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    ordering = ('sort_order', 'id')
