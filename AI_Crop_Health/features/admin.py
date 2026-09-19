from django.contrib import admin
from .models import MarketPrice, CropInfo, SchemeCategory, GovernmentScheme, Suggestion, SupportMessage
from django.utils.html import format_html
from core.admin import AuditModelAdminMixin
from core.services import AuditService

@admin.register(CropInfo)
class CropInfoAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('crop_name', 'category', 'season', 'is_active', 'updated_at')
    search_fields = ('crop_name', 'category')
    list_filter = ('category', 'season', 'is_active')
    ordering = ('crop_name',)
    list_editable = ('is_active',)

@admin.register(MarketPrice)
class MarketPriceAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('crop_name', 'market_location', 'price_per_quintal', 'price_trend', 'last_updated')
    search_fields = ('crop_name', 'market_location')
    list_filter = ('category', 'price_trend', 'is_active')
    ordering = ('-last_updated',)
    list_editable = ('price_per_quintal', 'price_trend')

@admin.register(SchemeCategory)
class SchemeCategoryAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('display_order', 'is_active')


@admin.register(GovernmentScheme)
class GovernmentSchemeAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'category', 'ministry', 'budget_display', 'fiscal_year', 'is_active', 'last_updated')
    list_filter = ('category', 'is_active', 'fiscal_year', 'last_updated')
    search_fields = ('name', 'ministry', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'fiscal_year')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'ministry', 'budget', 'fiscal_year', 'icon')
        }),
        ('Scheme Details', {
            'fields': ('description', 'benefits', 'eligibility', 'application_process')
        }),
        ('Additional Information', {
            'fields': ('website_url', 'contact_info', 'documents_required')
        }),
        ('Status', {
            'fields': ('is_active', 'last_updated', 'created_at', 'updated_at')
        }),
    )

    def budget_display(self, obj):
        return f"₹{obj.budget:,.0f} Cr"
    budget_display.short_description = 'Budget'


@admin.register(Suggestion)
class SuggestionAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('title', 'category', 'crop', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'crop')
    ordering = ('-created_at',)
    list_editable = ('is_active',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category', 'crop')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
    )
    readonly_fields = ('created_at',)


@admin.register(SupportMessage)
class SupportMessageAdmin(AuditModelAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'get_sender', 'message_preview', 'is_read', 'is_from_admin', 'created_at')
    list_filter = ('is_from_admin', 'is_read', 'created_at')
    search_fields = ('user__username', 'message')
    ordering = ('-created_at',)
    list_editable = ('is_read',)

    fieldsets = (
        ('Message Details', {
            'fields': ('user', 'message', 'is_from_admin')
        }),
        ('Status', {
            'fields': ('is_read', 'created_at')
        }),
    )
    readonly_fields = ('created_at',)

    def get_sender(self, obj):
        return "Admin" if obj.is_from_admin else "Farmer"
    get_sender.short_description = 'Sender'

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message Preview'