from django.db import models
from django.utils import timezone

class Contact(models.Model):
    RELATED_WORK_CHOICES = [
        ('farmer_api_key', 'Farmer API Key Request'),
        ('crop_disease_api', 'Crop Disease Prediction API'),
        ('soil_analysis', 'AI Soil Analysis'),
        ('weather_forecast', 'Weather Forecast Integration'),
        ('smart_irrigation', 'Smart Irrigation System'),
        ('dashboard_access', 'Agriculture Dashboard Access'),
        ('model_training', 'Model Training / Custom AI Model'),
        ('technical_support', 'Technical Support'),
        ('partnership', 'Partnership / Collaboration'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=100)
    related_work = models.CharField(max_length=50, choices=RELATED_WORK_CHOICES, default='other')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_date = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_date']

    def __str__(self):
        return f'Contact from {self.name}: {self.subject}'

class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-subscribed_date']

    def __str__(self):
        return self.email

class Service(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    icon_svg = models.TextField(blank=True, help_text="SVG code for the service icon")
    order = models.PositiveIntegerField(default=0, help_text="Order for displaying services")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    message = models.TextField()
    image = models.ImageField(upload_to='testimonials/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Testimonial from {self.name}'

class BiodegradableCompany(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    email = models.EmailField()
    materials_accepted = models.TextField(help_text="Comma-separated list of materials accepted")
    benefits_offered = models.TextField()
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class WasteSubmission(models.Model):
    WASTE_TYPES = [
        ('stubble', 'Stubble'),
        ('damaged_crop', 'Damaged Crop'),
        ('husks', 'Husks'),
        ('biomass', 'Biomass'),
        ('other', 'Other'),
    ]

    farmer_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15)
    village = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    crop_type = models.CharField(max_length=100)
    waste_type = models.CharField(max_length=20, choices=WASTE_TYPES)
    quantity = models.CharField(max_length=50)
    image = models.ImageField(upload_to='waste_submissions/', blank=True, null=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_processed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.farmer_name} - {self.crop_type} ({self.quantity})'
