from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from agrolease.models import AgroProfile, Land, LeaseRequest
from core.services import AuditService


class AdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_superuser(
            username='superadmin',
            email='superadmin@example.com',
            password='test-password',
        )
        cls.staff = user_model.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='test-password',
            is_staff=True,
        )
        cls.farmer = user_model.objects.create_user(
            username='farmer',
            email='farmer@example.com',
            password='test-password',
        )
        staff_group = Group.objects.create(name='Staff')
        cls.staff.groups.add(staff_group)

    def test_superadmin_can_open_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Control Center')
        self.assertContains(response, 'Super administrator')

    def test_staff_can_open_dashboard_but_cannot_manage_superusers(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff administrator')
        self.assertNotContains(response, 'Super administrator')

    def test_farmer_is_redirected_from_admin(self):
        self.client.force_login(self.farmer)
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_audit_log_serializes_uploaded_documents(self):
        profile = AgroProfile.objects.create(
            user=self.farmer,
            role='owner',
            government_id_document=SimpleUploadedFile('id.txt', b'id'),
        )

        AuditService.log('UPDATE', model_obj=profile, new_values={
            'government_id_document': profile.government_id_document,
        })

        document_name = profile._meta.model.objects.get(
            pk=profile.pk
        ).government_id_document.name
        self.assertTrue(document_name.startswith('verification/government_id/'))
        self.assertTrue(document_name.endswith('.txt'))

    def test_unverified_owner_documents_are_required_for_verification(self):
        profile = AgroProfile.objects.create(user=self.farmer, role='owner')
        profile.is_verified = True

        with self.assertRaises(ValidationError):
            profile.full_clean()


class AgroLeaseOtpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username='9876543210')
        AgroProfile.objects.create(
            user=cls.user,
            phone_number='9876543210',
            role='farmer',
            roles=['farmer'],
        )

    def test_login_sends_otp_and_verification_logs_user_in(self):
        response = self.client.post(reverse('agrolease:login'), {
            'phone': '9876543210',
            'role': 'farmer',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['otp_sent'])
        otp = self.client.session['agrolease_otp']['code']

        response = self.client.post(reverse('agrolease:otp'), {'otp': otp})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('agrolease:role_selection'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)


class AgroLeaseLandUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username='owner9876543210')
        AgroProfile.objects.create(
            user=cls.user,
            phone_number='9876543210',
            role='owner',
            roles=['owner'],
            is_verified=True,
        )

    def test_land_image_is_saved_from_multipart_form(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('agrolease:add_land'), {
            'location': 'Village, District, State',
            'size': '5',
            'soil_type': 'red',
            'water_source': 'well',
            'suitable_crops': 'Rice',
            'rent_amount': '2000',
            'rent_period': 'season',
            'duration': '1',
            'images': SimpleUploadedFile('land.jpg', b'image-data', content_type='image/jpeg'),
        })

        self.assertEqual(response.status_code, 302)
        land = Land.objects.get(owner=self.user)
        self.assertTrue(land.image.name.startswith('land_images/'))
        self.assertTrue(land.image.name.endswith('.jpg'))


class LeaseRequestValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username='farmer-request')
        AgroProfile.objects.create(
            user=cls.user,
            phone_number='9876543210',
            role='farmer',
            roles=['farmer'],
        )
        cls.land = Land.objects.create(
            owner=user_model.objects.create_user(username='land-owner'),
            location='Kolkata',
            size_acres=5,
            soil_type='alluvial',
            water_source='well',
            suitable_crops='Rice',
            rent_amount=2000,
            duration_months=1,
            status='available',
        )

    def test_terms_are_required(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('agrolease:request_lease', args=[self.land.pk]), {
            'farmer_name': 'Test Farmer',
            'contact_number': '9876543210',
            'farming_experience': 'beginner',
            'intended_crops': 'Rice',
            'lease_duration': 'season',
            'message': 'I would like to lease this land.',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeaseRequest.objects.count(), 0)
        self.assertContains(response, 'agree to the AgroLease terms')

    def test_valid_request_preserves_proposal_details(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('agrolease:request_lease', args=[self.land.pk]), {
            'farmer_name': 'Test Farmer',
            'contact_number': '9876543210',
            'farming_experience': 'experienced',
            'intended_crops': 'Rice, wheat',
            'lease_duration': 'year',
            'message': 'I have experience with irrigated crops.',
            'terms_agreed': 'on',
        })

        self.assertEqual(response.status_code, 302)
        lease_request = LeaseRequest.objects.get()
        self.assertIn('Test Farmer', lease_request.message)
        self.assertIn('Rice, wheat', lease_request.message)
        self.assertIn('year', lease_request.message)