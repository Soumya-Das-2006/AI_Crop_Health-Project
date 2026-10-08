from django.contrib import admin

from core.admin_mixins import ExportCsvMixin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(ExportCsvMixin, admin.ModelAdmin):
    """
    The global identity profile (phone, address), separate from the blog author
    profile and the AgroLease role profile. It was not registered at all, so a
    staff member could not look up the phone number a farmer signs in with.
    """

    list_display = ('user', 'phone_number', 'is_phone_verified',
                    'is_email_verified', 'city', 'district', 'state', 'created_at')
    list_filter = ('is_phone_verified', 'is_email_verified', 'state', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name',
                     'user__last_name', 'phone_number', 'city', 'district')
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)
    actions = ('export_as_csv', 'mark_phone_verified')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {'fields': ('user',)}),
        ('Identity & verification', {
            'fields': ('phone_number', 'is_phone_verified', 'is_email_verified'),
        }),
        ('Location', {'fields': ('address', 'city', 'district', 'state', 'pincode')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.action(description='Mark phone as verified')
    def mark_phone_verified(self, request, queryset):
        updated = queryset.update(is_phone_verified=True)
        self.message_user(request, f'{updated} profile(s) marked phone-verified.')
