from django.contrib import admin
from django.utils import timezone
from .models import AgroProfile, Land, LeaseRequest, LeaseAgreement
from core.admin import AuditModelAdminMixin
from core.services import AuditService


@admin.register(AgroProfile)
class AgroProfileAdmin(AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('user', 'role', 'phone_number', 'document_status', 'is_verified', 'verified_at', 'verified_by')
	list_filter = ('role', 'is_verified')
	search_fields = ('user__username', 'user__email', 'user__first_name', 'phone_number')
	list_select_related = ('user',)
	actions = ('verify_owners', 'unverify_owners')
	readonly_fields = ('verification_submitted_at', 'verified_at', 'verified_by')

	def save_model(self, request, obj, form, change):
		if obj.is_verified:
			obj.verified_at = obj.verified_at or timezone.now()
			obj.verified_by = obj.verified_by or request.user
		else:
			obj.verified_at = None
			obj.verified_by = None
		super().save_model(request, obj, form, change)

	fieldsets = (
		(None, {'fields': ('user', 'role', 'roles', 'phone_number', 'is_verified')}),
		('Verification documents', {'fields': ('government_id_type', 'government_id_document', 'ownership_proof', 'address_proof', 'selfie_photo')}),
		('Verification audit', {'fields': ('verification_submitted_at', 'verified_at', 'verified_by')}),
	)

	@admin.display(description='Documents')
	def document_status(self, obj):
		return 'Complete' if all((obj.government_id_document, obj.ownership_proof, obj.address_proof)) else 'Incomplete'

	@admin.action(description='Verify selected owner profiles')
	def verify_owners(self, request, queryset):
		updated = 0
		for profile in queryset:
			if profile.role == 'owner' or 'owner' in (profile.roles or []):
				if profile.government_id_document and profile.ownership_proof and profile.address_proof:
					profile.is_verified = True
					profile.verified_at = timezone.now()
					profile.verified_by = request.user
					profile.save(update_fields=('is_verified', 'verified_at', 'verified_by'))
					AuditService.log('VERIFY', model_obj=profile, request=request)
					updated += 1
		self.message_user(request, f'{updated} owner profile(s) verified.')

	@admin.action(description='Remove verification from selected owners')
	def unverify_owners(self, request, queryset):
		updated = queryset.filter(role='owner').update(is_verified=False, verified_at=None, verified_by=None)
		for profile in queryset.filter(role='owner'):
			AuditService.log('STATUS_CHANGE', model_obj=profile, request=request, metadata={'action': 'unverified'})
		self.message_user(request, f'{updated} owner profile(s) marked pending.')


@admin.register(Land)
class LandAdmin(AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('location', 'owner', 'owner_verified', 'size_acres', 'soil_type', 'rent_amount', 'status', 'created_at')
	list_filter = ('status', 'soil_type', 'water_source', 'created_at')
	search_fields = ('location', 'owner__username', 'owner__first_name', 'suitable_crops')
	list_select_related = ('owner',)
	readonly_fields = ('created_at', 'updated_at', 'latitude', 'longitude')
	date_hierarchy = 'created_at'
	actions = ('approve_listings', 'reject_listings')

	@admin.display(boolean=True, description='Owner verified')
	def owner_verified(self, obj):
		profile = getattr(obj.owner, 'agroprofile', None)
		return bool(profile and profile.is_verified)

	@admin.action(description='Approve selected land listings')
	def approve_listings(self, request, queryset):
		updated = 0
		blocked = 0
		for land in queryset:
			profile = getattr(land.owner, 'agroprofile', None)
			if profile and profile.is_verified:
				land.status = 'available'
				land.save(update_fields=('status', 'updated_at'))
				AuditService.log('APPROVE', model_obj=land, request=request)
				updated += 1
			else:
				blocked += 1
		self.message_user(request, f'{updated} land listing(s) approved and visible to farmers.')
		if blocked:
			self.message_user(request, f'{blocked} listing(s) were not approved because the owner is not verified.', level='WARNING')

	@admin.action(description='Reject selected land listings')
	def reject_listings(self, request, queryset):
		updated = queryset.update(status='rejected')
		for land in queryset:
			AuditService.log('REJECT', model_obj=land, request=request)
		self.message_user(request, f'{updated} land listing(s) rejected and hidden from farmers.')


@admin.register(LeaseRequest)
class LeaseRequestAdmin(AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('land', 'farmer', 'status', 'request_date')
	list_filter = ('status', 'request_date')
	search_fields = ('land__location', 'farmer__username', 'farmer__first_name', 'message')
	list_select_related = ('land', 'farmer')
	readonly_fields = ('request_date',)
	actions = ('approve_leases', 'reject_leases', 'complete_leases')
	date_hierarchy = 'request_date'

	@admin.action(description='Approve owner-approved lease requests')
	def approve_leases(self, request, queryset):
		updated = 0
		for lease_request in queryset.select_related('land', 'farmer').filter(status='owner_approved'):
			lease_request.status = 'approved'
			lease_request.save(update_fields=('status',))
			lease_request.land.status = 'leased'
			lease_request.land.save(update_fields=('status', 'updated_at'))
			LeaseAgreement.objects.get_or_create(
				lease_request=lease_request,
				defaults={
					'terms_text': (
						f'Lease of {lease_request.land.location} to '
						f'{lease_request.farmer.get_full_name() or lease_request.farmer.username} '
						f'for {lease_request.land.duration_months} months at '
						f'₹{lease_request.land.rent_amount} {lease_request.land.rent_frequency}.'
					),
				},
			)
			AuditService.log('APPROVE', model_obj=lease_request, request=request)
			updated += 1
		self.message_user(request, f'{updated} lease request(s) approved and activated.')

	@admin.action(description='Reject selected lease requests')
	def reject_leases(self, request, queryset):
		updated = queryset.filter(status__in=('pending', 'owner_approved')).update(status='rejected')
		self.message_user(request, f'{updated} lease request(s) rejected.')

	@admin.action(description='Mark approved leases completed')
	def complete_leases(self, request, queryset):
		updated = 0
		for lease_request in queryset.select_related('land').filter(status='approved'):
			lease_request.status = 'completed'
			lease_request.save(update_fields=('status',))
			lease_request.land.status = 'available'
			lease_request.land.save(update_fields=('status', 'updated_at'))
			updated += 1
		self.message_user(request, f'{updated} lease request(s) marked completed.')


@admin.register(LeaseAgreement)
class LeaseAgreementAdmin(AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('lease_request', 'signed_by_owner', 'signed_by_farmer', 'created_at')
	list_filter = ('signed_by_owner', 'signed_by_farmer', 'created_at')
	search_fields = ('lease_request__land__location', 'lease_request__farmer__username')
	list_select_related = ('lease_request',)
	readonly_fields = ('created_at',)
