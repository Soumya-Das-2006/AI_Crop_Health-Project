from django.contrib import admin, messages
from django.utils.html import format_html
from core.admin_mixins import ExportCsvMixin

from .models import (
    Field, SensorNode, SensorReading, IrrigationCommand,
    SensorThreshold, SensorAlert, CropPredictionLog,
    SystemMetricsLog, FieldZone
)


@admin.register(Field)
class FieldAdmin(ExportCsvMixin, admin.ModelAdmin):
    actions = ('export_as_csv',)
    list_display  = ('name', 'owner', 'current_crop', 'lifecycle_stage', 'size_acres', 'is_active')
    list_filter   = ('lifecycle_stage', 'is_active', 'soil_type')
    search_fields = ('name', 'owner__first_name', 'owner__last_name', 'location')
    list_editable = ('lifecycle_stage', 'is_active')


@admin.register(SensorNode)
class SensorNodeAdmin(admin.ModelAdmin):
    list_display  = ('device_id', 'field', 'hardware_type', 'connectivity',
                     'is_active', 'is_tampered', 'battery_pct', 'has_solar_power', 'last_seen')
    list_filter   = ('hardware_type', 'connectivity', 'is_active', 'has_solar_power')
    search_fields = ('device_id', 'field__name')
    list_editable = ('is_active',)
    readonly_fields = ('api_key', 'registered_at', 'last_seen')
    actions = ('rotate_api_keys',)

    @admin.display(description='Device key (X-Device-Key header)')
    def api_key(self, obj):
        return obj.api_key or '(generated on save)'

    @admin.action(description='Rotate device API key (device must be reflashed)')
    def rotate_api_keys(self, request, queryset):
        rotated = [(node.device_id, node.rotate_api_key()) for node in queryset]
        for device_id, key in rotated:
            self.message_user(
                request,
                f'{device_id}: new key {key} - reflash the device with this value.',
                level=messages.WARNING,
            )
        self.message_user(
            request,
            f'Rotated {len(rotated)} key(s). Old keys are now rejected, so any '
            f'device still using one will fail with HTTP 401 until reflashed.',
            level=messages.INFO,
        )


@admin.register(SensorReading)
class SensorReadingAdmin(ExportCsvMixin, admin.ModelAdmin):
    actions = ('export_as_csv',)
    list_display  = ('field', 'node', 'recorded_at', 'soil_moisture_pct',
                     'temperature_c', 'humidity_pct', 'nitrogen_ppm', 'is_valid')
    list_filter   = ('field', 'is_valid')
    date_hierarchy = 'recorded_at'
    readonly_fields = ('recorded_at',)


@admin.register(IrrigationCommand)
class IrrigationCommandAdmin(admin.ModelAdmin):
    list_display  = ('field', 'node', 'valve_open', 'duration_minutes',
                     'source', 'status', 'issued_at')
    list_filter   = ('status', 'source', 'valve_open')
    list_editable = ('status',)


@admin.register(SensorThreshold)
class SensorThresholdAdmin(admin.ModelAdmin):
    list_display  = ('field', 'variable', 'min_value', 'max_value',
                     'auto_irrigate_on_low_moisture', 'is_active')
    list_filter   = ('variable', 'is_active')
    list_editable = ('is_active',)


@admin.register(SensorAlert)
class SensorAlertAdmin(ExportCsvMixin, admin.ModelAdmin):
    actions = ('export_as_csv',)
    list_display  = ('field', 'severity', 'variable', 'actual_value',
                     'breach_type', 'is_read', 'is_resolved', 'alert_created')
    list_filter   = ('severity', 'breach_type', 'is_read', 'is_resolved')
    date_hierarchy = 'alert_created'
    readonly_fields = ('latency_seconds_display',)

    def latency_seconds_display(self, obj):
        return f"{obj.latency_seconds:.1f} s"
    latency_seconds_display.short_description = "Alert Latency"


@admin.register(CropPredictionLog)
class CropPredictionLogAdmin(admin.ModelAdmin):
    list_display  = ('field', 'recommended_crop', 'confidence_pct',
                     'model_version', 'farmer_agreed', 'predicted_at')
    list_filter   = ('model_version', 'farmer_agreed')
    date_hierarchy = 'predicted_at'


@admin.register(SystemMetricsLog)
class SystemMetricsLogAdmin(admin.ModelAdmin):
    list_display  = ('date', 'pdr_display', 'avg_alert_latency_sec',
                     'alerts_under_2min_pct', 'water_reduction_pct_display',
                     'server_uptime_pct', 'crop_pred_accuracy_pct', 'sus_score')
    date_hierarchy = 'date'

    def pdr_display(self, obj):
        v = obj.packet_delivery_ratio
        return f"{v}%" if v is not None else "—"
    pdr_display.short_description = "PDR"

    def water_reduction_pct_display(self, obj):
        v = obj.water_reduction_pct
        return f"{v}%" if v is not None else "—"
    water_reduction_pct_display.short_description = "Water Reduction"


@admin.register(FieldZone)
class FieldZoneAdmin(admin.ModelAdmin):
    list_display = ('field', 'zone_label', 'area_acres', 'centroid_lat', 'centroid_lng',
                    'valve_lat', 'valve_lng')
    list_filter  = ('field',)
