from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from .models import AgroProfile, Land, LeaseMessage, LeaseRequest, LeaseAgreement
from core.admin import AuditModelAdminMixin
from core.services import AuditService
from core.admin_mixins import ExportCsvMixin


@admin.register(AgroProfile)
class AgroProfileAdmin(ExportCsvMixin, AuditModelAdminMixin, admin.ModelAdmin):
	"""
	Verification review queue.

	Both owners AND farmers are reviewed here. They need different documents:
	an owner must prove ownership, a farmer (who is leasing, not owning) cannot
	and instead provides a selfie. The required set comes from
	AgroProfile.REQUIRED_DOCUMENTS, so the actions below never hardcode it.
	"""
	list_display = ('user', 'role', 'phone_number', 'verification_status',
	                'document_status', 'is_verified', 'verified_at', 'verified_by')
	list_filter = ('role', 'verification_status', 'is_verified')
	search_fields = ('user__username', 'user__email', 'user__first_name', 'phone_number')
	list_select_related = ('user',)
	actions = ('verify_profiles', 'reject_profiles', 'unverify_profiles', 'export_as_csv')
	readonly_fields = ('verification_submitted_at', 'verified_at', 'verified_by',
	                   'required_documents_display', 'document_links')

	def save_model(self, request, obj, form, change):
		if obj.is_verified:
			obj.verified_at = obj.verified_at or timezone.now()
			obj.verified_by = obj.verified_by or request.user
		else:
			obj.verified_at = None
			obj.verified_by = None
		obj.sync_verification_status()
		super().save_model(request, obj, form, change)

	fieldsets = (
		(None, {'fields': ('user', 'role', 'roles', 'phone_number')}),
		('Verification decision', {
			'fields': ('verification_status', 'is_verified', 'rejection_reason'),
			'description': 'Tick "is verified" to approve. A rejection reason is '
			               'shown to the user, so write something actionable.',
		}),
		('Verification documents', {
			'fields': ('required_documents_display', 'document_links',
			           'government_id_type'),
		}),
		('Verification audit', {'fields': ('verification_submitted_at', 'verified_at', 'verified_by')}),
	)

	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path(
				'<int:object_id>/documents/<str:field_name>/',
				self.admin_site.admin_view(self.download_verification_document),
				name='agrolease_agroprofile_document',
			),
		]
		return custom_urls + urls

	def download_verification_document(self, request, object_id, field_name):
		profile = self.get_object(request, object_id)
		if profile is None:
			raise Http404
		if not self.has_view_or_change_permission(request, profile):
			raise PermissionDenied

		private_fields = {
			'government_id_document',
			'ownership_proof',
			'address_proof',
			'selfie_photo',
		}
		if field_name not in private_fields:
			raise Http404
		document = getattr(profile, field_name)
		if not document:
			raise Http404

		filename = document.name.rsplit('/', 1)[-1]
		response = FileResponse(
			document.open('rb'),
			as_attachment=True,
			filename=filename,
			content_type='application/octet-stream',
		)
		response['Cache-Control'] = 'private, no-store'
		response['X-Content-Type-Options'] = 'nosniff'
		return response

	@admin.display(description='Documents')
	def document_status(self, obj):
		missing = obj.missing_documents()
		if not missing:
			return 'Complete'
		return f'Missing: {", ".join(missing)}'

	@admin.display(description='Required for this role')
	def required_documents_display(self, obj):
		if not obj.pk:
			return '-'
		required = ', '.join(label for label, _ in obj.required_documents())
		return f'{obj.verification_role()}: {required}'

	@admin.display(description='Uploaded documents')
	def document_links(self, obj):
		if not obj.pk:
			return '-'
		links = []
		for label, field_name in obj.required_documents():
			document = getattr(obj, field_name, None)
			if document:
				url = reverse(
					'admin:agrolease_agroprofile_document',
					args=(obj.pk, field_name),
				)
				links.append(format_html('<a href="{}">{}</a>', url, label))
			else:
				links.append(format_html('<span style="color:#b00">{} (missing)</span>', label))
		return format_html_join(' &nbsp;|&nbsp; ', '{}', ((link,) for link in links))

	@admin.action(description='Approve verification (owners and farmers)')
	def verify_profiles(self, request, queryset):
		verified = 0
		blocked = []
		for profile in queryset:
			missing = profile.missing_documents()
			if missing:
				blocked.append(f'{profile.user.username} ({", ".join(missing)})')
				continue
			profile.is_verified = True
			profile.verified_at = timezone.now()
			profile.verified_by = request.user
			profile.sync_verification_status()
			profile.save(update_fields=(
				'is_verified', 'verified_at', 'verified_by',
				'verification_status', 'rejection_reason',
			))
			AuditService.log('VERIFY', model_obj=profile, request=request)
			verified += 1
		self.message_user(request, f'{verified} profile(s) verified.')
		if blocked:
			self.message_user(
				request,
				'Not verified, documents incomplete: ' + '; '.join(blocked),
				level=messages.WARNING,
			)

	@admin.action(description='Reject verification')
	def reject_profiles(self, request, queryset):
		rejected = 0
		for profile in queryset:
			profile.is_verified = False
			profile.verified_at = None
			profile.verified_by = None
			profile.verification_status = 'rejected'
			if not profile.rejection_reason:
				missing = profile.missing_documents()
				profile.rejection_reason = (
					'Missing or unreadable documents: ' + ', '.join(missing)
					if missing else
					'Documents did not pass review. Please re-upload clear copies.'
				)
			profile.save(update_fields=(
				'is_verified', 'verified_at', 'verified_by',
				'verification_status', 'rejection_reason',
			))
			AuditService.log('REJECT', model_obj=profile, request=request)
			rejected += 1
		self.message_user(
			request,
			f'{rejected} profile(s) rejected. The reason is shown to the user, '
			f'who can re-upload and resubmit.',
		)

	@admin.action(description='Remove verification (back to pending)')
	def unverify_profiles(self, request, queryset):
		updated = 0
		for profile in queryset:
			profile.is_verified = False
			profile.verified_at = None
			profile.verified_by = None
			profile.sync_verification_status()
			profile.save(update_fields=(
				'is_verified', 'verified_at', 'verified_by', 'verification_status',
			))
			AuditService.log('STATUS_CHANGE', model_obj=profile, request=request,
			                 metadata={'action': 'unverified'})
			updated += 1
		self.message_user(request, f'{updated} profile(s) marked pending.')


@admin.register(Land)
class LandAdmin(ExportCsvMixin, AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('location', 'owner', 'owner_verified', 'size_acres', 'soil_type', 'rent_amount', 'status', 'created_at')
	list_filter = ('status', 'soil_type', 'water_source', 'created_at')
	search_fields = ('location', 'owner__username', 'owner__first_name', 'suitable_crops')
	list_select_related = ('owner',)
	readonly_fields = ('created_at', 'updated_at', 'latitude', 'longitude')
	date_hierarchy = 'created_at'
	actions = ('approve_listings', 'reject_listings', 'export_as_csv')

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
class LeaseRequestAdmin(ExportCsvMixin, AuditModelAdminMixin, admin.ModelAdmin):
	list_display = ('land', 'farmer', 'status', 'request_date')
	list_filter = ('status', 'request_date')
	search_fields = ('land__location', 'farmer__username', 'farmer__first_name', 'message')
	list_select_related = ('land', 'farmer')
	readonly_fields = ('request_date',)
	actions = ('approve_leases', 'reject_leases', 'complete_leases', 'export_as_csv')
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


@admin.register(LeaseMessage)
class LeaseMessageAdmin(admin.ModelAdmin):
	"""
	Read-only view of the owner/farmer conversation on a lease.

	Registered so support can investigate a dispute. Messages are never editable
	here: altering what someone said would destroy the record's value.
	"""
	list_display = ('created_at', 'lease_request', 'sender', 'short_body')
	list_filter = ('created_at',)
	search_fields = ('body', 'sender__username', 'lease_request__land__location')
	list_select_related = ('sender', 'lease_request', 'lease_request__land')
	date_hierarchy = 'created_at'
	readonly_fields = ('lease_request', 'sender', 'body', 'created_at')

	@admin.display(description='Message')
	def short_body(self, obj):
		return (obj.body[:80] + '...') if len(obj.body) > 80 else obj.body

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return False
