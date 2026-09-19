from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Q  # ADD THIS IMPORT
from django.db import models

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User

class DetectionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='detection_histories')
    diagnosis_log = models.ForeignKey('DiagnosisLog', on_delete=models.CASCADE, related_name='saved_histories')
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-saved_at']
        verbose_name_plural = "Detection Histories"

    def __str__(self):
        return f"{self.user.username} - {self.diagnosis_log.predicted_crop}"

class DiagnosisLog(models.Model):
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)

    uploaded_image = models.ImageField(upload_to='diagnoses/%Y/%m/%d/', null=True, blank=True)
    image_resolution = models.CharField(max_length=20)
    image_size_kb = models.IntegerField()

    quality_score = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    sharpness_score = models.FloatField(null=True, blank=True)
    brightness_score = models.FloatField(null=True, blank=True)
    passed_quality_check = models.BooleanField(default=False)
    quality_failure_reason = models.TextField(null=True, blank=True)

    predicted_crop = models.CharField(max_length=100)
    predicted_disease = models.CharField(max_length=200)
    class_index = models.IntegerField()
    class_label = models.CharField(max_length=200)

    raw_confidence = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    calibrated_confidence = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    entropy_score = models.FloatField(null=True, blank=True)

    diagnosis_status = models.CharField(
        max_length=30,
        choices=[
            ('highly_reliable', 'Highly Reliable (≥98%)'),
            ('moderate_confidence', 'Moderate Confidence (95–97%)'),
            ('unreliable', 'Unreliable (<95%)'),
        ]
    )

    used_gemini_validation = models.BooleanField(default=False)
    gemini_confidence = models.FloatField(null=True, blank=True)
    gemini_recommendation = models.CharField(max_length=50, null=True, blank=True)
    gemini_concerns = models.JSONField(null=True, blank=True)

    solutions_shown = models.BooleanField(default=False)
    warning_message = models.TextField(null=True, blank=True)

    farmer_confirmed = models.BooleanField(null=True, blank=True)
    farmer_feedback = models.TextField(null=True, blank=True)
    farmer_feedback_date = models.DateTimeField(null=True, blank=True)

    admin_reviewed = models.BooleanField(default=False)
    admin_notes = models.TextField(null=True, blank=True)
    is_false_positive = models.BooleanField(null=True, blank=True)
    correct_diagnosis = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['diagnosis_status']),
            models.Index(fields=['predicted_crop', 'predicted_disease']),
            models.Index(fields=['calibrated_confidence']),
        ]

    def __str__(self):
        confidence = (
            f"{self.calibrated_confidence:.1f}%"
            if isinstance(self.calibrated_confidence, (int, float))
            else "N/A"
        )
        return f"{self.predicted_crop} - {self.predicted_disease} ({confidence})"

    @property
    def is_safe_for_treatment(self):
        return (
            isinstance(self.calibrated_confidence, (int, float))
            and self.calibrated_confidence >= 98.0
            and self.diagnosis_status == 'highly_reliable'
        )

    @property
    def accuracy_category(self):
        if not isinstance(self.calibrated_confidence, (int, float)):
            return 'Unknown'
        if self.calibrated_confidence >= 98:
            return 'Highly Reliable'
        elif self.calibrated_confidence >= 95:
            return 'Moderate'
        elif self.calibrated_confidence >= 90:
            return 'Low'
        return 'Very Low'

class QualityRejectionLog(models.Model):
    """
    Log images rejected before inference (pre-flight quality check).
    Critical for understanding farmer image capture patterns.
    """
    timestamp = models.DateTimeField(default=timezone.now)
    uploaded_image = models.ImageField(upload_to='rejected/%Y/%m/%d/')
    
    rejection_reasons = models.JSONField()  # All failed checks
    image_resolution = models.CharField(max_length=20)
    
    sharpness_score = models.FloatField(null=True)
    brightness_score = models.FloatField(null=True)
    quality_score = models.FloatField()
    
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Rejected: {self.image_resolution} @ {self.timestamp}"


class FarmerFeedback(models.Model):
    """
    Farmer reports on diagnosis accuracy after field application.
    Gold standard for model retraining.
    """
    diagnosis_log = models.OneToOneField(DiagnosisLog, on_delete=models.CASCADE)
    
    feedback_date = models.DateTimeField(default=timezone.now)
    
    was_correct = models.BooleanField(
        help_text="Did the diagnosis match field symptoms?"
    )
    
    treatment_worked = models.BooleanField(
        null=True, blank=True,
        help_text="Did recommended treatment work?"
    )
    
    actual_disease = models.CharField(
        max_length=200, null=True, blank=True,
        help_text="What was the actual disease (if different)?"
    )
    
    comments = models.TextField(blank=True)
    
    # Contact info (optional, for follow-up)
    farmer_phone = models.CharField(max_length=20, null=True, blank=True)
    farmer_location = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        ordering = ['-feedback_date']
    
    def __str__(self):
        status = "✓ Correct" if self.was_correct else "✗ Incorrect"
        return f"{status}: {self.diagnosis_log.predicted_disease}"


"""
Agriculture Advisory Board Models
==================================
Admin-controlled, context-aware suggestions and alerts system.

STRICT RULES:
- NO chatbot functionality
- Read-only for users
- Admin controls all content
- API key validation required
- Context-based filtering (location, soil, season)
"""


# ======================================================
# SUGGESTION MODEL
# ======================================================

class AgricultureSuggestion(models.Model):
    """
    Admin-created agriculture recommendations.
    Dynamically filtered by location, soil type, and season.
    """
    
    CATEGORY_CHOICES = [
        ('crop', 'Crop Management'),
        ('weather', 'Weather Advisory'),
        ('soil', 'Soil Health'),
        ('fertilizer', 'Fertilizer Recommendation'),
        ('pest', 'Pest Control'),
        ('market', 'Market Intelligence'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
    ]
    
    SEASON_CHOICES = [
        ('all', 'All Seasons'),
        ('monsoon', 'Monsoon'),
        ('summer', 'Summer'),
        ('winter', 'Winter'),
        ('spring', 'Spring'),
        ('autumn', 'Autumn'),
    ]
    
    SOIL_TYPE_CHOICES = [
        ('any', 'Any Soil Type'),
        ('loamy', 'Loamy'),
        ('sandy', 'Sandy'),
        ('clay', 'Clay'),
        ('silt', 'Silt'),
        ('peaty', 'Peaty'),
        ('chalky', 'Chalky'),
        ('mixed', 'Mixed'),
    ]
    
    # Core content
    title = models.CharField(
        max_length=200,
        help_text="Clear, actionable title (e.g., 'Plant Drought-Resistant Crops')"
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        db_index=True
    )
    
    description = models.TextField(
        help_text="Detailed recommendation with specific actions"
    )
    
    # Context filters
    is_global = models.BooleanField(
        default=False,
        help_text="Show to all users regardless of location",
        db_index=True
    )
    
    applicable_locations = models.TextField(
        blank=True,
        help_text="Comma-separated locations (e.g., 'Maharashtra, Karnataka, Punjab'). Leave empty if global."
    )
    
    applicable_soil_types = models.CharField(
        max_length=200,
        default='any',
        help_text="Comma-separated soil types (e.g., 'loamy,clay') or 'any' for all"
    )
    
    applicable_seasons = models.CharField(
        max_length=200,
        default='all',
        help_text="Comma-separated seasons (e.g., 'monsoon,winter') or 'all' for all seasons"
    )
    
    # Metadata
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive suggestions are hidden from users"
    )
    
    publish_date = models.DateTimeField(
        default=timezone.now,
        help_text="When this suggestion becomes visible"
    )
    
    expiry_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional: Auto-hide after this date"
    )
    
    # Analytics
    view_count = models.IntegerField(default=0)
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)
    
    # Admin
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-priority', '-publish_date']
        indexes = [
            models.Index(fields=['is_active', 'publish_date']),
            models.Index(fields=['category', 'priority']),
            models.Index(fields=['is_global']),
        ]
        verbose_name = "Agriculture Suggestion"
        verbose_name_plural = "Agriculture Suggestions"
    
    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"
    
    @property
    def is_expired(self):
        """Check if suggestion has expired"""
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False
    
    @property
    def is_currently_active(self):
        """Check if suggestion should be shown"""
        now = timezone.now()
        return (
            self.is_active and
            self.publish_date <= now and
            not self.is_expired
        )
    
    def get_applicable_locations_list(self):
        """Parse comma-separated locations into list"""
        if not self.applicable_locations or self.is_global:
            return []
        return [loc.strip() for loc in self.applicable_locations.split(',') if loc.strip()]
    
    def get_applicable_soil_types_list(self):
        """Parse comma-separated soil types into list"""
        if self.applicable_soil_types == 'any':
            return ['any']
        return [soil.strip().lower() for soil in self.applicable_soil_types.split(',') if soil.strip()]
    
    def get_applicable_seasons_list(self):
        """Parse comma-separated seasons into list"""
        if self.applicable_seasons == 'all':
            return ['all']
        return [season.strip().lower() for season in self.applicable_seasons.split(',') if season.strip()]
    
    def matches_context(self, location, soil_type, season):
        """
        Check if this suggestion matches user context.
        
        Args:
            location (str): User's location
            soil_type (str): User's soil type
            season (str): Current season
        
        Returns:
            bool: True if suggestion should be shown
        """
        # Location match
        if not self.is_global:
            locations = self.get_applicable_locations_list()
            if locations and location.lower() not in [loc.lower() for loc in locations]:
                return False
        
        # Soil type match
        soil_types = self.get_applicable_soil_types_list()
        if 'any' not in soil_types and soil_type.lower() not in soil_types:
            return False
        
        # Season match
        seasons = self.get_applicable_seasons_list()
        if 'all' not in seasons and season.lower() not in seasons:
            return False
        
        return True
    
    @classmethod
    def get_filtered_suggestions(cls, location, soil_type, season, api_key=None):
        """
        Get all active suggestions matching context.
        
        Args:
            location (str): User location
            soil_type (str): User soil type
            season (str): Current season
            api_key (str): API key for validation (optional for now)
        
        Returns:
            QuerySet: Filtered suggestions
        """
        now = timezone.now()
        
        # Base query: active and not expired
        queryset = cls.objects.filter(
            is_active=True,
            publish_date__lte=now
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        )
        
        # Filter by context
        filtered = []
        for suggestion in queryset:
            if suggestion.matches_context(location, soil_type, season):
                filtered.append(suggestion.id)
        
        # Return filtered queryset ordered by priority
        return cls.objects.filter(id__in=filtered).order_by(
            models.Case(
                models.When(priority='high', then=1),
                models.When(priority='medium', then=2),
                models.When(priority='low', then=3),
                default=4,
                output_field=models.IntegerField(),
            ),
            '-publish_date'
        )


# ======================================================
# ALERT MODEL
# ======================================================

class AgricultureAlert(models.Model):
    """
    Time-sensitive alerts for farmers.
    Higher priority than suggestions.
    """
    
    ALERT_TYPE_CHOICES = [
        ('weather', 'Weather Alert'),
        ('pest', 'Pest Outbreak'),
        ('market', 'Market Update'),
        ('disease', 'Disease Outbreak'),
        ('advisory', 'General Advisory'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    SOIL_TYPE_CHOICES = [
        ('any', 'Any Soil Type'),
        ('loamy', 'Loamy'),
        ('sandy', 'Sandy'),
        ('clay', 'Clay'),
        ('silt', 'Silt'),
        ('peaty', 'Peaty'),
        ('chalky', 'Chalky'),
        ('mixed', 'Mixed'),
    ]
    
    # Core content
    alert_type = models.CharField(
        max_length=20,
        choices=ALERT_TYPE_CHOICES,
        db_index=True
    )
    
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='info',
        db_index=True,
        help_text="Critical alerts appear first"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Alert headline (e.g., 'Heavy Rainfall Expected This Week')"
    )
    
    message = models.TextField(
        help_text="Detailed alert message with actionable advice"
    )
    
    affected_crops = models.CharField(
        max_length=300,
        blank=True,
        help_text="Comma-separated crop names (e.g., 'Rice, Wheat, Cotton')"
    )
    
    # Context filters
    is_global = models.BooleanField(
        default=False,
        help_text="Show to all users regardless of location",
        db_index=True
    )
    
    applicable_locations = models.TextField(
        blank=True,
        help_text="Comma-separated locations. Leave empty if global."
    )
    
    applicable_soil_types = models.CharField(
        max_length=200,
        default='any',
        help_text="Comma-separated soil types or 'any'"
    )
    
    # Validity period
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="When alert becomes active"
    )
    
    valid_until = models.DateTimeField(
        help_text="Alert expires after this date"
    )
    
    # Display
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )
    
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pinned alerts always appear at top"
    )
    
    # Analytics
    view_count = models.IntegerField(default=0)
    
    # Admin
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-is_pinned', '-severity', '-valid_from']
        indexes = [
            models.Index(fields=['is_active', 'valid_from', 'valid_until']),
            models.Index(fields=['severity', 'alert_type']),
            models.Index(fields=['is_global']),
            models.Index(fields=['is_pinned']),
        ]
        verbose_name = "Agriculture Alert"
        verbose_name_plural = "Agriculture Alerts"
    
    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"
    
    @property
    def is_currently_valid(self):
        """Check if alert is within valid period"""
        now = timezone.now()
        return self.valid_from <= now <= self.valid_until
    
    @property
    def is_currently_active(self):
        """Check if alert should be shown"""
        return self.is_active and self.is_currently_valid
    
    @property
    def severity_color(self):
        """Get Bootstrap color class for severity"""
        return {
            'info': 'info',
            'warning': 'warning',
            'critical': 'danger',
        }.get(self.severity, 'secondary')
    
    @property
    def severity_icon(self):
        """Get icon for severity"""
        return {
            'info': 'bi-info-circle',
            'warning': 'bi-exclamation-triangle',
            'critical': 'bi-exclamation-octagon',
        }.get(self.severity, 'bi-bell')
    
    def get_applicable_locations_list(self):
        """Parse comma-separated locations into list"""
        if not self.applicable_locations or self.is_global:
            return []
        return [loc.strip() for loc in self.applicable_locations.split(',') if loc.strip()]
    
    def get_applicable_soil_types_list(self):
        """Parse comma-separated soil types into list"""
        if self.applicable_soil_types == 'any':
            return ['any']
        return [soil.strip().lower() for soil in self.applicable_soil_types.split(',') if soil.strip()]
    
    def get_affected_crops_list(self):
        """Parse comma-separated crops into list"""
        if not self.affected_crops:
            return []
        return [crop.strip() for crop in self.affected_crops.split(',') if crop.strip()]
    
    def matches_context(self, location, soil_type, season=None):
        """
        Check if this alert matches user context.
        
        Args:
            location (str): User's location
            soil_type (str): User's soil type
            season (str): Optional season (not used for alerts currently)
        
        Returns:
            bool: True if alert should be shown
        """
        # Location match
        if not self.is_global:
            locations = self.get_applicable_locations_list()
            if locations and location.lower() not in [loc.lower() for loc in locations]:
                return False
        
        # Soil type match
        soil_types = self.get_applicable_soil_types_list()
        if 'any' not in soil_types and soil_type.lower() not in soil_types:
            return False
        
        return True
    
    @classmethod
    def get_filtered_alerts(cls, location, soil_type, season=None, api_key=None):
        """
        Get all active alerts matching context.
        
        Args:
            location (str): User location
            soil_type (str): User soil type
            season (str): Optional season
            api_key (str): API key for validation
        
        Returns:
            QuerySet: Filtered alerts
        """
        now = timezone.now()
        
        # Base query: active and within valid period
        queryset = cls.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        )
        
        # Filter by context
        filtered = []
        for alert in queryset:
            if alert.matches_context(location, soil_type, season):
                filtered.append(alert.id)
        
        # Return filtered queryset ordered by severity
        return cls.objects.filter(id__in=filtered).order_by(
            '-is_pinned',
            models.Case(
                models.When(severity='critical', then=1),
                models.When(severity='warning', then=2),
                models.When(severity='info', then=3),
                default=4,
                output_field=models.IntegerField(),
            ),
            '-valid_from'
        )


# ======================================================
# USER REACTIONS MODEL
# ======================================================

class UserReaction(models.Model):
    """
    Track user reactions to suggestions and alerts.
    Used for analytics only - users cannot comment.
    """
    
    REACTION_CHOICES = [
        ('helpful', '👍 Helpful'),
        ('not_helpful', '👎 Not Helpful'),
        ('viewed', '👁 Viewed'),
    ]
    
    # Polymorphic relationship
    suggestion = models.ForeignKey(
        AgricultureSuggestion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reactions'
    )
    
    alert = models.ForeignKey(
        AgricultureAlert,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reactions'
    )
    
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES
    )
    
    # User tracking (anonymous)
    session_id = models.CharField(max_length=100)
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Context when reaction was made
    user_location = models.CharField(max_length=100)
    user_soil_type = models.CharField(max_length=50)
    user_season = models.CharField(max_length=50)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['suggestion', 'reaction_type']),
            models.Index(fields=['alert', 'reaction_type']),
            models.Index(fields=['session_id']),
        ]
        # Prevent duplicate reactions from same session
        unique_together = [
            ['suggestion', 'session_id', 'reaction_type'],
            ['alert', 'session_id', 'reaction_type'],
        ]
    
    def __str__(self):
        content = self.suggestion or self.alert
        return f"{self.get_reaction_type_display()} on {content}"


# ======================================================
# API ACCESS LOG
# ======================================================

class APIAccessLog(models.Model):
    """
    Log all API access attempts for security monitoring.
    """
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Request details
    api_key_provided = models.CharField(max_length=100, blank=True)
    is_valid_key = models.BooleanField(default=False)
    
    # Request parameters
    location = models.CharField(max_length=100, blank=True)
    soil_type = models.CharField(max_length=50, blank=True)
    season = models.CharField(max_length=50, blank=True)
    
    # Response
    http_status = models.IntegerField()
    suggestions_count = models.IntegerField(default=0)
    alerts_count = models.IntegerField(default=0)
    
    # Client info
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Error details (if any)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['is_valid_key']),
            models.Index(fields=['http_status']),
        ]
    
    def __str__(self):
        status = "✓ Valid" if self.is_valid_key else "✗ Invalid"
        return f"{status} API call from {self.user_ip} @ {self.timestamp}"