from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class MarketPrice(models.Model):
    # Choices for category
    CATEGORY_CHOICES = [
        ('Rice', 'Rice'),
        ('Wheat', 'Wheat'),
        ('Vegetables', 'Vegetables'),
        ('Fruits', 'Fruits'),
        ('Pulses', 'Pulses'),
        ('Other', 'Other'),
    ]

    # Choices for price_trend
    TREND_CHOICES = [
        ('Up', 'Up'),
        ('Down', 'Down'),
        ('Stable', 'Stable'),
    ]

    # Choices for quality_grade
    GRADE_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
    ]

    crop_name = models.CharField(max_length=100, help_text="Name of the crop")
    crop_image = models.ImageField(upload_to='market_prices/', help_text="Image of the crop")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, help_text="Category of the crop")
    market_location = models.CharField(max_length=100, help_text="Location of the market")
    price_per_quintal = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per quintal in rupees")
    price_unit = models.CharField(max_length=20, default="₹ / Quintal", help_text="Unit of price")
    price_trend = models.CharField(max_length=10, choices=TREND_CHOICES, help_text="Trend of the price")
    quality_grade = models.CharField(max_length=1, choices=GRADE_CHOICES, blank=True, null=True, help_text="Quality grade (optional)")
    description = models.TextField(blank=True, null=True, help_text="Additional notes or description")
    last_updated = models.DateTimeField(auto_now=True, help_text="Last updated timestamp")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    is_active = models.BooleanField(default=True, help_text="Is this price active?")

    class Meta:
        ordering = ['-last_updated']
        verbose_name = "Market Price"
        verbose_name_plural = "Market Prices"

    def __str__(self):
        return f"{self.crop_name} - {self.market_location} - ₹{self.price_per_quintal}"
class CropInfo(models.Model):

    CATEGORY_CHOICES = [
        ('Cereals', 'Cereals'),
        ('Pulses', 'Pulses'),
        ('Vegetables', 'Vegetables'),
        ('Fruits', 'Fruits'),
        ('Oilseeds', 'Oilseeds'),
        ('Spices', 'Spices'),
    ]

    SEASON_CHOICES = [
        ('Kharif', 'Kharif'),
        ('Rabi', 'Rabi'),
        ('Zaid', 'Zaid'),
    ]

    crop_name = models.CharField(max_length=100, help_text="Crop name")
    crop_image = models.ImageField(upload_to='crop_info/', help_text="Crop image")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    season = models.CharField(max_length=20, choices=SEASON_CHOICES)

    soil_type = models.CharField(max_length=100)
    climate = models.CharField(max_length=100)
    sowing_time = models.CharField(max_length=100)
    harvesting_time = models.CharField(max_length=100)
    water_requirement = models.CharField(max_length=100)

    fertilizer_requirement = models.TextField()
    common_diseases = models.TextField()
    prevention_tips = models.TextField()

    average_yield = models.CharField(max_length=100)
    description = models.TextField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['crop_name']
        verbose_name = "Crop Information"
        verbose_name_plural = "Crop Information"

    def __str__(self):
        return self.crop_name

class SchemeCategory(models.Model):
    """Category model for government schemes"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Scheme Categories"
        ordering = ['display_order', 'name']
        app_label = 'features'

    def __str__(self):
        return self.name


class GovernmentScheme(models.Model):
    """Main model for government schemes"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.ForeignKey(SchemeCategory, on_delete=models.CASCADE, related_name='schemes')
    ministry = models.CharField(max_length=200)
    budget = models.DecimalField(max_digits=15, decimal_places=2, help_text="Budget in Crore Rupees")
    description = models.TextField()
    benefits = models.TextField()
    eligibility = models.TextField()
    application_process = models.TextField()
    fiscal_year = models.CharField(max_length=20, default="FY2025-26")
    last_updated = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=100, default="fas fa-seedling",
                           help_text="FontAwesome icon class")

    # Additional fields for future use
    website_url = models.URLField(blank=True)
    contact_info = models.TextField(blank=True)
    documents_required = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_updated', 'name']
        indexes = [
            models.Index(fields=['name', 'ministry']),
            models.Index(fields=['category', 'is_active']),
        ]
        app_label = 'features'

    def __str__(self):
        return f"{self.name} ({self.ministry})"

    def get_budget_display(self):
        """Format budget with ₹ symbol"""
        return f"₹{self.budget:,.0f}"

    @property
    def is_recently_updated(self):
        """Check if scheme was updated within last 30 days"""
        return (timezone.now().date() - self.last_updated).days <= 30


class Suggestion(models.Model):
    """Model for agricultural suggestions"""
    CATEGORY_CHOICES = [
        ('General', 'General'),
        ('Urgent', 'Urgent'),
        ('Seasonal', 'Seasonal'),
        ('Crop-specific', 'Crop-specific'),
    ]

    title = models.CharField(max_length=200, help_text="Title of the suggestion")
    description = models.TextField(help_text="Detailed description of the suggestion")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='General',
                               help_text="Category of the suggestion")
    crop = models.CharField(max_length=100, blank=True, null=True,
                           help_text="Specific crop if applicable")
    is_active = models.BooleanField(default=True, help_text="Is this suggestion active?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Suggestion"
        verbose_name_plural = "Suggestions"

    def __str__(self):
        return f"{self.title} ({self.category})"


class SupportMessage(models.Model):
    """Model for farmer-admin support messages"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages',
                            help_text="Farmer who sent the message")
    message = models.TextField(help_text="Message content")
    is_from_admin = models.BooleanField(default=False, help_text="Is this message from admin?")
    is_read = models.BooleanField(default=False, help_text="Has this message been read?")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Message timestamp")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Support Message"
        verbose_name_plural = "Support Messages"

    def __str__(self):
        sender = "Admin" if self.is_from_admin else f"Farmer ({self.user.username})"
        return f"{sender}: {self.message[:50]}..."
