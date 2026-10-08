"""
IoT Sensor & Field Management Models
-------------------------------------
Covers every new feature from the PPT proposal:
  - Multi-field / multi-crop management
  - Real sensor data ingestion (NPK, moisture, temp, humidity, wind, solar)
  - Solenoid valve / irrigation actuation commands
  - GPS-based field nodes
  - Alert engine (threshold breach → notification)
  - Evaluation / metrics logging
  - Crop lifecycle stage tracking
"""

import hmac
import secrets

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ──────────────────────────────────────────────────────────────────────────────
# 1. FIELD  (multi-field management)
# ──────────────────────────────────────────────────────────────────────────────

class Field(models.Model):
    """A physical agricultural field owned / managed by a user."""

    CROP_LIFECYCLE_CHOICES = [
        ('pre_sowing',  'Pre-Sowing'),
        ('sowing',      'Sowing'),
        ('vegetative',  'Vegetative Growth'),
        ('flowering',   'Flowering'),
        ('fruiting',    'Fruiting / Grain Fill'),
        ('maturity',    'Maturity'),
        ('harvest',     'Harvest'),
        ('fallow',      'Fallow'),
    ]

    owner        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fields')

    # Optional link to the agrolease Land this field physically is. Set when a
    # farmer registers a field for land they lease, or when an owner links their
    # own listing. Without it, agrolease.Land and iot_sensor.Field are two
    # unrelated records describing the same soil, and a leaseholding farmer has
    # no way to be granted sensor access.
    land         = models.ForeignKey(
        'agrolease.Land',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sensor_fields',
        help_text="The leased/owned land parcel this monitored field corresponds to.",
    )
    name         = models.CharField(max_length=100, help_text="e.g. North Plot, Field-3")
    location     = models.CharField(max_length=200)
    size_acres   = models.DecimalField(max_digits=8, decimal_places=2)
    soil_type    = models.CharField(max_length=50, blank=True)
    current_crop = models.CharField(max_length=100, blank=True)
    lifecycle_stage = models.CharField(
        max_length=20, choices=CROP_LIFECYCLE_CHOICES, default='fallow'
    )
    # GPS coordinates of field centre
    latitude     = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude    = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['owner', 'name']

    def __str__(self):
        return f"{self.name} ({self.owner.get_full_name() or self.owner.username})"


# ──────────────────────────────────────────────────────────────────────────────
# 2. SENSOR NODE  (Raspberry Pi / Arduino / ESP32 field unit)
# ──────────────────────────────────────────────────────────────────────────────

class SensorNode(models.Model):
    """
    Represents one physical field management unit
    (Raspberry Pi + sensors + GSM module + solenoid valve).
    """

    HARDWARE_CHOICES = [
        ('raspberry_pi', 'Raspberry Pi'),
        ('arduino_uno',  'Arduino Uno'),
        ('arduino_micro','Arduino Micro'),
        ('esp32',        'ESP32'),
        ('custom',       'Custom'),
    ]

    CONNECTIVITY_CHOICES = [
        ('gsm',       'GSM / 4G'),
        ('wifi',      'Wi-Fi'),
        ('ethernet',  'Ethernet'),
        ('bluetooth', 'Bluetooth'),
        ('mqtt',      'MQTT over Wi-Fi'),
    ]

    field          = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='nodes')
    device_id      = models.CharField(max_length=64, unique=True,
                                      help_text="Unique hardware ID burned into firmware")

    # Shared secret the device sends as the X-Device-Key header on every POST to
    # /iot/api/ingest/. device_id alone is only an identifier, not a credential:
    # anyone who learns it could otherwise inject readings, raise false alerts
    # and trigger irrigation on a real field.
    api_key        = models.CharField(
        max_length=64, unique=True, db_index=True, blank=True,
        help_text="Auto-generated. Flash this into the device firmware; "
                  "it is sent as the X-Device-Key header.",
    )
    hardware_type  = models.CharField(max_length=20, choices=HARDWARE_CHOICES, default='esp32')
    connectivity   = models.CharField(max_length=10, choices=CONNECTIVITY_CHOICES, default='gsm')

    # GPS placement (from K-medoids / Weiszfeld placement optimisation)
    latitude       = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude      = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    placement_zone = models.CharField(max_length=20, blank=True,
                                      help_text="Zone label from K-medoids clustering, e.g. Z1")

    # Status
    is_active      = models.BooleanField(default=True)
    is_tampered    = models.BooleanField(default=False)
    last_seen      = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=30, blank=True)

    # Power
    has_solar_power = models.BooleanField(default=False,
                                          help_text="Solar-based power storage unit present")
    battery_pct    = models.SmallIntegerField(null=True, blank=True,
                                              validators=[MinValueValidator(0), MaxValueValidator(100)])

    registered_at  = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_api_key():
        """Return a fresh URL-safe device key (43 chars, 256 bits of entropy)."""
        return secrets.token_urlsafe(32)

    def rotate_api_key(self, save=True):
        """Issue a new key, invalidating the old one. Reflash the device after."""
        self.api_key = self.generate_api_key()
        if save:
            self.save(update_fields=['api_key'])
        return self.api_key

    def check_api_key(self, candidate):
        """
        Constant-time comparison, so response timing cannot be used to recover
        the key byte by byte. An unset key never validates.
        """
        if not self.api_key or not candidate:
            return False
        return hmac.compare_digest(str(self.api_key), str(candidate))

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
            if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
                kwargs['update_fields'] = list(kwargs['update_fields']) + ['api_key']
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['field', 'device_id']

    def __str__(self):
        return f"{self.device_id} [{self.get_hardware_type_display()}] — {self.field.name}"

    def mark_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])


# ──────────────────────────────────────────────────────────────────────────────
# 3. SENSOR READING  (time-series environmental data)
# ──────────────────────────────────────────────────────────────────────────────

class SensorReading(models.Model):
    """
    One complete sensor snapshot from a field node.
    Covers all 6 environment variables from the proposal:
      Soil Moisture, Temperature, Humidity, Wind Speed,
      Solar Luminous Intensity, NPK + pH.
    """

    node        = models.ForeignKey(SensorNode, on_delete=models.CASCADE,
                                    related_name='readings')
    field       = models.ForeignKey(Field, on_delete=models.CASCADE,
                                    related_name='sensor_readings')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    # ── Soil sensors ─────────────────────────────────────────────────────────
    soil_moisture_pct  = models.FloatField(null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)],
                                           help_text="Soil moisture %")
    nitrogen_ppm       = models.FloatField(null=True, blank=True, help_text="N — ppm")
    phosphorus_ppm     = models.FloatField(null=True, blank=True, help_text="P — ppm")
    potassium_ppm      = models.FloatField(null=True, blank=True, help_text="K — ppm")
    soil_ph            = models.FloatField(null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(14)])

    # ── Atmospheric sensors ───────────────────────────────────────────────────
    temperature_c      = models.FloatField(null=True, blank=True, help_text="°C")
    humidity_pct       = models.FloatField(null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)])
    wind_speed_kmh     = models.FloatField(null=True, blank=True, help_text="km/h")
    solar_lux          = models.FloatField(null=True, blank=True,
                                           help_text="Solar luminous intensity (lux)")
    rainfall_mm        = models.FloatField(null=True, blank=True, help_text="mm in last interval")

    # ── Water / tank level ────────────────────────────────────────────────────
    water_level_pct    = models.FloatField(null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)],
                                           help_text="Tank/reservoir water level %")

    # ── Transmission metadata ─────────────────────────────────────────────────
    packet_id          = models.CharField(max_length=64, blank=True)
    rssi_dbm           = models.SmallIntegerField(null=True, blank=True,
                                                  help_text="GSM/Wi-Fi signal strength dBm")
    is_valid           = models.BooleanField(default=True,
                                             help_text="False if sensor payload failed signature check")

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['field', '-recorded_at']),
            models.Index(fields=['node', '-recorded_at']),
        ]

    def __str__(self):
        return f"Reading @ {self.recorded_at:%Y-%m-%d %H:%M} — {self.field.name}"


# ──────────────────────────────────────────────────────────────────────────────
# 4. IRRIGATION COMMAND  (closed-loop actuation)
# ──────────────────────────────────────────────────────────────────────────────

class IrrigationCommand(models.Model):
    """
    Command sent to a field node to open/close the solenoid valve.
    Represents the closed-loop actuation output of the AI engine.
    """

    SOURCE_CHOICES = [
        ('ai_auto',  'AI Automatic (threshold breach)'),
        ('manual',   'Manual (farmer override)'),
        ('schedule', 'Scheduled irrigation'),
    ]
    STATUS_CHOICES = [
        ('pending',     'Pending'),
        ('sent',        'Sent to device'),
        ('acknowledged','Acknowledged by device'),
        ('executed',    'Executed'),
        ('failed',      'Failed'),
    ]

    node            = models.ForeignKey(SensorNode, on_delete=models.CASCADE,
                                        related_name='irrigation_commands')
    field           = models.ForeignKey(Field, on_delete=models.CASCADE,
                                        related_name='irrigation_commands')
    issued_by       = models.ForeignKey(User, null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        help_text="Null = AI-issued")
    source          = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='ai_auto')

    valve_open      = models.BooleanField(help_text="True = open valve (irrigate)")
    duration_minutes= models.PositiveSmallIntegerField(default=30,
                                                       help_text="How long to keep valve open")
    water_volume_l  = models.FloatField(null=True, blank=True,
                                        help_text="Estimated litres to dispense")
    trigger_reading = models.ForeignKey(SensorReading, null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        help_text="Reading that triggered this command")

    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    issued_at       = models.DateTimeField(auto_now_add=True)
    executed_at     = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        action = "OPEN" if self.valve_open else "CLOSE"
        return f"Valve {action} — {self.field.name} [{self.status}]"


# ──────────────────────────────────────────────────────────────────────────────
# 5. SENSOR THRESHOLD  (per-field alert configuration)
# ──────────────────────────────────────────────────────────────────────────────

class SensorThreshold(models.Model):
    """
    Min/max thresholds for each sensor variable per field.
    Breach → SensorAlert is created (target latency < 2 min).
    """

    VARIABLE_CHOICES = [
        ('soil_moisture_pct', 'Soil Moisture (%)'),
        ('nitrogen_ppm',      'Nitrogen (ppm)'),
        ('phosphorus_ppm',    'Phosphorus (ppm)'),
        ('potassium_ppm',     'Potassium (ppm)'),
        ('soil_ph',           'Soil pH'),
        ('temperature_c',     'Temperature (°C)'),
        ('humidity_pct',      'Humidity (%)'),
        ('wind_speed_kmh',    'Wind Speed (km/h)'),
        ('solar_lux',         'Solar Luminous Intensity (lux)'),
        ('water_level_pct',   'Water Level (%)'),
    ]

    field        = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='thresholds')
    variable     = models.CharField(max_length=30, choices=VARIABLE_CHOICES)
    min_value    = models.FloatField(null=True, blank=True, help_text="Alert if reading drops below")
    max_value    = models.FloatField(null=True, blank=True, help_text="Alert if reading exceeds")
    auto_irrigate_on_low_moisture = models.BooleanField(
        default=False,
        help_text="Automatically issue irrigation command when soil moisture drops below min"
    )
    is_active    = models.BooleanField(default=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('field', 'variable')]
        ordering = ['field', 'variable']

    def __str__(self):
        return f"{self.field.name} — {self.get_variable_display()} [{self.min_value}–{self.max_value}]"


# ──────────────────────────────────────────────────────────────────────────────
# 6. SENSOR ALERT  (breach notification, target <2 min latency)
# ──────────────────────────────────────────────────────────────────────────────

class SensorAlert(models.Model):
    """
    Generated when a SensorReading breaches a SensorThreshold.
    Delivered to farmer dashboard; latency tracked for evaluation metrics.
    """

    SEVERITY_CHOICES = [
        ('info',     'Info'),
        ('warning',  'Warning'),
        ('critical', 'Critical'),
    ]

    field       = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='alerts')
    threshold   = models.ForeignKey(SensorThreshold, on_delete=models.CASCADE)
    reading     = models.ForeignKey(SensorReading, on_delete=models.CASCADE)
    severity    = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')

    variable    = models.CharField(max_length=30)
    actual_value= models.FloatField()
    breach_type = models.CharField(max_length=5, choices=[('low','Low'),('high','High')])

    message     = models.TextField()
    is_read     = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Latency tracking (for evaluation metric: target < 2 min)
    reading_time  = models.DateTimeField(help_text="When sensor took the reading")
    alert_created = models.DateTimeField(auto_now_add=True, help_text="When alert was created in DB")

    @property
    def latency_seconds(self):
        return (self.alert_created - self.reading_time).total_seconds()

    class Meta:
        ordering = ['-alert_created']
        indexes = [
            models.Index(fields=['field', 'is_read']),
            models.Index(fields=['-alert_created']),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.field.name} — {self.variable}: {self.actual_value}"


# ──────────────────────────────────────────────────────────────────────────────
# 7. CROP PREDICTION LOG  (XGBoost output, with k-fold CV tracking)
# ──────────────────────────────────────────────────────────────────────────────

class CropPredictionLog(models.Model):
    """
    Records every AI crop recommendation made from live sensor data.
    Tracks model version and confidence for evaluation metric:
    target ≥85% top-1 accuracy via k-fold cross-validation.
    """

    field           = models.ForeignKey(Field, on_delete=models.CASCADE,
                                        related_name='crop_predictions', null=True, blank=True)
    reading         = models.ForeignKey(SensorReading, null=True, blank=True,
                                        on_delete=models.SET_NULL,
                                        help_text="Sensor reading used as input")
    user            = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    # Input features (mirrors FEATURE_NAMES in crop/predictor.py)
    nitrogen        = models.FloatField()
    phosphorus      = models.FloatField()
    potassium       = models.FloatField()
    temperature     = models.FloatField()
    humidity        = models.FloatField()
    ph              = models.FloatField()
    rainfall        = models.FloatField()

    # Prediction output
    recommended_crop  = models.CharField(max_length=100)
    confidence_pct    = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    top3_crops        = models.JSONField(default=list, help_text="Top-3 [{crop, confidence}]")
    model_version     = models.CharField(max_length=30, default='sklearn_v1')

    # Farmer feedback for continuous learning
    farmer_agreed     = models.BooleanField(null=True, blank=True)
    actual_crop_grown = models.CharField(max_length=100, blank=True)

    predicted_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-predicted_at']

    def __str__(self):
        return f"{self.recommended_crop} ({self.confidence_pct:.1f}%) — {self.predicted_at:%Y-%m-%d}"


# ──────────────────────────────────────────────────────────────────────────────
# 8. SYSTEM METRICS  (evaluation — uptime, PDR, water reduction, SUS)
# ──────────────────────────────────────────────────────────────────────────────

class SystemMetricsLog(models.Model):
    """
    Daily snapshot of platform evaluation metrics from the proposal:
      - Packet Delivery Ratio (PDR)
      - Alert Latency
      - Water Usage Reduction
      - System Uptime
      - Crop Prediction Accuracy
      - SUS Score
    """

    date                    = models.DateField(unique=True, default=timezone.now)
    total_packets_sent      = models.PositiveIntegerField(default=0)
    total_packets_received  = models.PositiveIntegerField(default=0)

    avg_alert_latency_sec   = models.FloatField(null=True, blank=True)
    alerts_under_2min_pct   = models.FloatField(null=True, blank=True,
                                                help_text="% of alerts delivered within 2 minutes")

    water_usage_manual_l    = models.FloatField(null=True, blank=True,
                                                help_text="Baseline manual irrigation litres")
    water_usage_ai_l        = models.FloatField(null=True, blank=True,
                                                help_text="AI-controlled irrigation litres")

    server_uptime_pct       = models.FloatField(null=True, blank=True,
                                                validators=[MinValueValidator(0), MaxValueValidator(100)])

    crop_pred_accuracy_pct  = models.FloatField(null=True, blank=True,
                                                help_text="k-fold validated accuracy for the day")

    sus_score               = models.FloatField(null=True, blank=True,
                                                validators=[MinValueValidator(0), MaxValueValidator(100)],
                                                help_text="System Usability Scale 0-100")
    sus_respondents         = models.PositiveSmallIntegerField(default=0)

    notes                   = models.TextField(blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)

    @property
    def packet_delivery_ratio(self):
        if self.total_packets_sent:
            return round(self.total_packets_received / self.total_packets_sent * 100, 2)
        return None

    @property
    def water_reduction_pct(self):
        if self.water_usage_manual_l and self.water_usage_ai_l:
            return round((1 - self.water_usage_ai_l / self.water_usage_manual_l) * 100, 2)
        return None

    class Meta:
        ordering = ['-date']
        verbose_name = "System Metrics Log"

    def __str__(self):
        return f"Metrics {self.date} | PDR={self.packet_delivery_ratio}%"


# ──────────────────────────────────────────────────────────────────────────────
# 9. ZONE  (K-medoids clustering output)
# ──────────────────────────────────────────────────────────────────────────────

class FieldZone(models.Model):
    """
    Represents one cluster/zone produced by K-medoids algorithm
    for optimal sensor and valve placement within a field.
    """

    field       = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='zones')
    zone_label  = models.CharField(max_length=20, help_text="e.g. Z1, Z2, Z3")
    centroid_lat= models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True,
                                      help_text="K-medoid centroid latitude")
    centroid_lng= models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    valve_lat   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True,
                                      help_text="Optimal valve placement (Weiszfeld's algorithm)")
    valve_lng   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    area_acres  = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('field', 'zone_label')]
        ordering = ['field', 'zone_label']

    def __str__(self):
        return f"{self.field.name} — {self.zone_label}"
