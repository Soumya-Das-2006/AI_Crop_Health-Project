from django.db import models
from django.contrib.auth.models import User

class AgroProfile(models.Model):
    ROLE_CHOICES = (
        ('owner', 'Land Owner'),
        ('farmer', 'Farmer'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agroprofile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='farmer')
    phone_number = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Land(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('pending_approval', 'Pending Admin Approval'),
        ('leased', 'Leased'),
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lands')
    location = models.CharField(max_length=255)
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
