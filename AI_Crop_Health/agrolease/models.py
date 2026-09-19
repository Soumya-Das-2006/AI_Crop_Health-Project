from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class AgroProfile(models.Model):
    ROLE_CHOICES = (
        ('owner', 'Land Owner'),
        ('farmer', 'Farmer'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agroprofile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='farmer')
    roles = models.JSONField(default=list, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)
    government_id_type = models.CharField(max_length=30, blank=True)
    government_id_document = models.FileField(upload_to='verification/government_id/', blank=True, null=True)
    ownership_proof = models.FileField(upload_to='verification/ownership/', blank=True, null=True)
    address_proof = models.FileField(upload_to='verification/address/', blank=True, null=True)
    selfie_photo = models.ImageField(upload_to='verification/selfies/', blank=True, null=True)
    verification_submitted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='verified_agro_profiles')

    def clean(self):
        super().clean()
        owner_roles = self.roles or []
        if self.is_verified:
            if self.role != 'owner' and 'owner' not in owner_roles:
                raise ValidationError({'role': 'Only a land owner can be verified.'})
            missing_documents = [
                label for label, document in (
                    ('government ID', self.government_id_document),
                    ('ownership proof', self.ownership_proof),
                    ('address proof', self.address_proof),
                ) if not document
            ]
            if missing_documents:
                raise ValidationError({
                    'is_verified': 'Upload all required documents before verification: '
                    + ', '.join(missing_documents) + '.'
                })

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Land(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('pending_approval', 'Pending Admin Approval'),
        ('rejected', 'Rejected'),
        ('leased', 'Leased'),
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lands')
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    size_acres = models.DecimalField(max_digits=6, decimal_places=2)
    soil_type = models.CharField(max_length=100)
    water_source = models.CharField(max_length=100)
    suitable_crops = models.CharField(max_length=255)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rent_frequency = models.CharField(max_length=50, default='per season')
    duration_months = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='land_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.size_acres} acres in {self.location}"


class LeaseRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('owner_approved', 'Owner Approved - Admin Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )
    land = models.ForeignKey(Land, on_delete=models.CASCADE, related_name='lease_requests')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='farmer_requests')
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farmer.username} request for {self.land.location}"


class LeaseAgreement(models.Model):
    lease_request = models.OneToOneField(LeaseRequest, on_delete=models.CASCADE)
    terms_text = models.TextField()
    signed_by_owner = models.BooleanField(default=False)
    signed_by_farmer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class LeaseMessage(models.Model):
    lease_request = models.ForeignKey(LeaseRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lease_messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
