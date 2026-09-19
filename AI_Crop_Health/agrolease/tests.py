from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.test import RequestFactory, TestCase
from unittest.mock import patch

from .admin import LeaseRequestAdmin
from .models import AgroProfile, Land, LeaseAgreement, LeaseMessage, LeaseRequest


class OwnerLeaseWorkflowTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner = user_model.objects.create_user(
			username='owner', email='owner@example.com', first_name='Land Owner'
		)
		AgroProfile.objects.create(
			user=self.owner, role='owner', roles=['owner'], is_verified=True,
			government_id_document='verification/id.pdf',
			ownership_proof='verification/ownership.pdf',
			address_proof='verification/address.pdf',
		)
		self.farmer = user_model.objects.create_user(
			username='farmer', email='farmer@example.com', first_name='Asha'
		)
		AgroProfile.objects.create(
			user=self.farmer, role='farmer', roles=['farmer'], phone_number='9876543210'
		)
		self.land = Land.objects.create(
			owner=self.owner,
			location='Pune',
			size_acres=4,
			soil_type='Loamy',
			water_source='Canal',
			suitable_crops='Wheat',
			rent_amount=25000,
			rent_frequency='per month',
			duration_months=12,
			status='available',
		)
		self.lease_request = LeaseRequest.objects.create(
			land=self.land,
			farmer=self.farmer,
			message='I have five years of farming experience.',
		)

	def test_owner_can_review_farmer_details(self):
		self.client.force_login(self.owner)

		response = self.client.get(reverse(
			'agrolease:owner_request_detail', args=[self.lease_request.id]
		))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'farmer@example.com')
		self.assertContains(response, '9876543210')
		self.assertContains(response, 'five years of farming experience')

	def test_owner_approval_waits_for_admin_before_revenue_starts(self):
		self.client.force_login(self.owner)

		response = self.client.post(reverse(
			'agrolease:approve_lease_request', args=[self.lease_request.id]
		))

		self.assertRedirects(response, reverse(
			'agrolease:owner_request_detail', args=[self.lease_request.id]
		))
		self.lease_request.refresh_from_db()
		self.land.refresh_from_db()
		self.assertEqual(self.lease_request.status, 'owner_approved')
		self.assertEqual(self.land.status, 'available')
		self.assertFalse(LeaseAgreement.objects.filter(lease_request=self.lease_request).exists())

		admin_request = RequestFactory().get('/admin/')
		admin_request.user = get_user_model().objects.create_superuser(
			username='admin', email='admin@example.com', password='password'
		)
		lease_admin = LeaseRequestAdmin(LeaseRequest, AdminSite())
		with patch.object(lease_admin, 'message_user'):
			lease_admin.approve_leases(
				admin_request,
				LeaseRequest.objects.filter(pk=self.lease_request.pk),
			)

		self.lease_request.refresh_from_db()
		self.land.refresh_from_db()
		self.assertEqual(self.lease_request.status, 'approved')
		self.assertEqual(self.land.status, 'leased')
		self.assertTrue(LeaseAgreement.objects.filter(lease_request=self.lease_request).exists())

		dashboard = self.client.get(reverse('agrolease:owner_dashboard'))
		self.assertContains(dashboard, '₹25000')

	def test_owner_and_farmer_can_chat_about_request(self):
		self.client.force_login(self.owner)
		self.client.post(reverse('agrolease:lease_chat', args=[self.lease_request.id]), {
			'body': 'Please confirm your intended lease duration.'
		})
		self.assertTrue(LeaseMessage.objects.filter(body__icontains='intended lease duration').exists())

		self.client.force_login(self.farmer)
		response = self.client.get(reverse('agrolease:lease_chat', args=[self.lease_request.id]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Please confirm your intended lease duration.')

	def test_approved_request_without_agreement_is_repaired(self):
		self.lease_request.status = 'approved'
		self.lease_request.save(update_fields=('status',))
		self.client.force_login(self.farmer)

		response = self.client.get(reverse(
			'agrolease:agreement_preview', args=[self.lease_request.id]
		))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(LeaseAgreement.objects.filter(lease_request=self.lease_request).exists())
		self.assertContains(response, 'Lease of Pune to Asha')

	def test_farmer_can_accept_agreement(self):
		self.lease_request.status = 'approved'
		self.lease_request.save(update_fields=('status',))
		LeaseAgreement.objects.create(
			lease_request=self.lease_request,
			terms_text='Lease terms',
		)
		self.client.force_login(self.farmer)

		response = self.client.post(reverse(
			'agrolease:agreement_action',
			args=[self.lease_request.id, 'accept'],
		))

		self.assertRedirects(response, reverse('agrolease:farmer_dashboard'))
		self.assertTrue(LeaseAgreement.objects.get(lease_request=self.lease_request).signed_by_farmer)

	def test_other_owner_cannot_view_or_approve_request(self):
		other_owner = get_user_model().objects.create_user(username='other-owner')
		AgroProfile.objects.create(user=other_owner, role='owner', roles=['owner'])
		self.client.force_login(other_owner)

		detail = self.client.get(reverse(
			'agrolease:owner_request_detail', args=[self.lease_request.id]
		))
		approval = self.client.post(reverse(
			'agrolease:approve_lease_request', args=[self.lease_request.id]
		))

		self.assertEqual(detail.status_code, 404)
		self.assertEqual(approval.status_code, 404)
