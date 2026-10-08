"""
IoT Sensor Views
-----------------
1. Farmer Field Dashboard  — multi-field overview with live sensor data
2. Field Detail            — time-series readings + alerts for one field
3. Sensor Ingest API       — REST endpoint for field nodes to POST readings
4. Irrigation Control      — manual valve override
5. Alert Dashboard         — all unread alerts
6. Metrics Dashboard       — evaluation metrics (PDR, latency, accuracy...)
7. Zone Map                — K-medoids zone visualisation
"""

import json
import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    Field, SensorNode, SensorReading, IrrigationCommand,
    SensorThreshold, SensorAlert, CropPredictionLog, SystemMetricsLog, FieldZone
)
from .access import (
    get_profile, visible_fields, can_manage_field,
    hardware_registration_state,
)
from .forms import FieldForm, SensorNodeForm
from .services.alert_engine import check_reading
from .services.xgboost_predictor import predict_from_sensor, predict_crop

logger = logging.getLogger(__name__)

# Ingest hardening limits. A field node posting every 30s uses ~120/hour, so
# 240 leaves generous headroom while still capping a runaway device.
MAX_INGEST_BODY_BYTES = 16 * 1024
INGEST_WINDOW_SECONDS = 3600
MAX_READINGS_PER_WINDOW = 240


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_verified(request):
    """
    Return AgroProfile or None; flash a warning if not verified.

    The accessor was `request.user.agro_profile`, but the related_name is
    `agroprofile`. Every call raised AttributeError, hit the bare `except` and
    returned None, so this check never actually ran.
    """
    try:
        profile = get_profile(request.user)
        if profile is None:
            raise AttributeError('no agroprofile')
        if not profile.is_verified:
            messages.warning(request, 'Your account is pending verification by admin.')
        return profile
    except Exception:
        return None


# ── 1. FIELD DASHBOARD ───────────────────────────────────────────────────────

@login_required
def field_dashboard(request):
    """Multi-field overview — all fields owned by the logged-in user."""
    fields = visible_fields(request.user).select_related('land').prefetch_related(
        'nodes', 'alerts', 'sensor_readings'
    )

    # Attach latest reading to each field
    field_data = []
    for field in fields:
        latest = field.sensor_readings.first()
        unread_alerts = field.alerts.filter(is_read=False).count()
        field_data.append({
            'field': field,
            'latest': latest,
            'unread_alerts': unread_alerts,
            'node_count': field.nodes.filter(is_active=True).count(),
        })

    context = {
        'field_data': field_data,
        'total_fields': fields.count(),
        'total_active_nodes': sum(item['node_count'] for item in field_data),
        'total_alerts': SensorAlert.objects.filter(
            field__in=visible_fields(request.user), is_read=False,
        ).count(),
    }
    return render(request, 'iot_sensor/field_dashboard.html', context)


# ── 2. FIELD DETAIL ──────────────────────────────────────────────────────────

@login_required
def field_detail(request, field_id):
    field = get_object_or_404(visible_fields(request.user), pk=field_id)
    readings = field.sensor_readings.all()[:96]   # last 96 readings (~8 hrs @ 5-min interval)
    alerts   = field.alerts.all()[:20]
    nodes    = field.nodes.filter(is_active=True)
    zones    = field.zones.all()
    thresholds = field.thresholds.all()
    last_cmd = field.irrigation_commands.first()

    # Chart data for JS (last 24 readings)
    chart_labels = []
    chart_moisture = []
    chart_temp = []
    for r in reversed(list(readings[:24])):
        chart_labels.append(r.recorded_at.strftime('%H:%M'))
        chart_moisture.append(r.soil_moisture_pct)
        chart_temp.append(r.temperature_c)

    context = {
        'field': field,
        'readings': readings,
        'alerts': alerts,
        'nodes': nodes,
        'zones': zones,
        'thresholds': thresholds,
        'last_irrigation': last_cmd,
        'chart_labels': json.dumps(chart_labels),
        'chart_moisture': json.dumps(chart_moisture),
        'chart_temp': json.dumps(chart_temp),
        'latest': readings.first() if readings else None,
    }
    return render(request, 'iot_sensor/field_detail.html', context)


# ── 3. SENSOR INGEST API ─────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def sensor_ingest(request):
    """
    REST endpoint for ESP32 / Raspberry Pi to POST sensor data.
    Expected JSON body:
    {
        "device_id": "ESP32-001",
        "soil_moisture_pct": 32.4,
        "nitrogen_ppm": 140,
        "phosphorus_ppm": 58,
        "potassium_ppm": 201,
        "soil_ph": 6.8,
        "temperature_c": 28.3,
        "humidity_pct": 72.1,
        "wind_speed_kmh": 8.5,
        "solar_lux": 45000,
        "rainfall_mm": 0,
        "water_level_pct": 85,
        "packet_id": "PKT-20240115-001",
        "rssi_dbm": -72
    }
    """
    if len(request.body) > MAX_INGEST_BODY_BYTES:
        return JsonResponse({'error': 'Payload too large'}, status=413)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'error': 'Body must be a JSON object'}, status=400)

    device_id = str(data.get('device_id', '')).strip()
    if not device_id:
        return JsonResponse({'error': 'device_id required'}, status=400)

    # ---- Device authentication -------------------------------------------
    # device_id identifies, it does not authenticate. Require the per-node key.
    presented_key = (
        request.headers.get('X-Device-Key')
        or request.META.get('HTTP_X_DEVICE_KEY')
        or ''
    ).strip()
    if not presented_key:
        return JsonResponse(
            {'error': 'Missing X-Device-Key header'}, status=401,
        )

    try:
        node = SensorNode.objects.select_related('field').get(
            device_id=device_id, is_active=True,
        )
    except SensorNode.DoesNotExist:
        # Same shape and status as a bad key, so the endpoint cannot be used to
        # enumerate which device_ids exist.
        logger.warning('Ingest rejected: unknown device_id %s', device_id)
        return JsonResponse({'error': 'Authentication failed'}, status=401)

    if not node.check_api_key(presented_key):
        logger.warning('Ingest rejected: bad key for device_id %s', device_id)
        return JsonResponse({'error': 'Authentication failed'}, status=401)

    # ---- Replay / duplicate suppression ----------------------------------
    packet_id = str(data.get('packet_id', '') or '').strip()
    if packet_id and SensorReading.objects.filter(
        node=node, packet_id=packet_id,
    ).exists():
        return JsonResponse(
            {'status': 'duplicate', 'packet_id': packet_id}, status=200,
        )

    # ---- Per-device rate limit -------------------------------------------
    # A compromised or malfunctioning node cannot flood the table.
    window_start = timezone.now() - timedelta(seconds=INGEST_WINDOW_SECONDS)
    recent = SensorReading.objects.filter(
        node=node, recorded_at__gte=window_start,
    ).count()
    if recent >= MAX_READINGS_PER_WINDOW:
        logger.warning(
            'Ingest rate limit hit for device %s (%d readings in %ds)',
            device_id, recent, INGEST_WINDOW_SECONDS,
        )
        return JsonResponse({'error': 'Rate limit exceeded'}, status=429)

    # Build reading
    reading = SensorReading.objects.create(
        node=node,
        field=node.field,
        soil_moisture_pct  = data.get('soil_moisture_pct'),
        nitrogen_ppm       = data.get('nitrogen_ppm'),
        phosphorus_ppm     = data.get('phosphorus_ppm'),
        potassium_ppm      = data.get('potassium_ppm'),
        soil_ph            = data.get('soil_ph'),
        temperature_c      = data.get('temperature_c'),
        humidity_pct       = data.get('humidity_pct'),
        wind_speed_kmh     = data.get('wind_speed_kmh'),
        solar_lux          = data.get('solar_lux'),
        rainfall_mm        = data.get('rainfall_mm'),
        water_level_pct    = data.get('water_level_pct'),
        packet_id          = data.get('packet_id', ''),
        rssi_dbm           = data.get('rssi_dbm'),
        is_valid           = True,
    )

    # Update node heartbeat
    node.mark_seen()
    if 'battery_pct' in data:
        node.battery_pct = data['battery_pct']
        node.save(update_fields=['battery_pct'])

    # Run alert engine
    alerts = check_reading(reading)

    # Run crop prediction if NPK data present
    crop_result = None
    if all(v is not None for v in [reading.nitrogen_ppm, reading.phosphorus_ppm,
                                    reading.potassium_ppm, reading.temperature_c]):
        crop_result = predict_from_sensor(reading)
        CropPredictionLog.objects.create(
            field=node.field,
            reading=reading,
            nitrogen   = reading.nitrogen_ppm or 0,
            phosphorus = reading.phosphorus_ppm or 0,
            potassium  = reading.potassium_ppm or 0,
            temperature= reading.temperature_c or 25,
            humidity   = reading.humidity_pct or 60,
            ph         = reading.soil_ph or 6.5,
            rainfall   = reading.rainfall_mm or 0,
            recommended_crop = crop_result['crop'],
            confidence_pct   = crop_result['confidence'],
            top3_crops       = crop_result.get('top3', []),
            model_version    = crop_result.get('model', 'unknown'),
        )

    # Check for pending irrigation commands to return
    pending_cmd = IrrigationCommand.objects.filter(
        node=node, status='pending'
    ).first()

    response = {
        'reading_id': reading.pk,
        'alerts_triggered': len(alerts),
        'crop_recommendation': crop_result['crop'] if crop_result else None,
    }
    if pending_cmd:
        response['command'] = {
            'id': pending_cmd.pk,
            'valve_open': pending_cmd.valve_open,
            'duration_minutes': pending_cmd.duration_minutes,
        }
        pending_cmd.status = 'sent'
        pending_cmd.save(update_fields=['status'])

    return JsonResponse(response, status=201)


# ── 4. IRRIGATION CONTROL ────────────────────────────────────────────────────

@login_required
@require_POST
def irrigation_control(request, field_id):
    """Manual valve override from farmer dashboard."""
    field = get_object_or_404(visible_fields(request.user), pk=field_id)

    # Opening a valve floods real soil, so actuation is checked explicitly and
    # separately from "can view this dashboard".
    if not can_manage_field(request.user, field):
        messages.error(
            request,
            'You can view this field but not control its irrigation. '
            'Only the land owner or the approved leaseholder can do that.',
        )
        return redirect('iot_sensor:field_detail', field_id=field.pk)
    node_id = request.POST.get('node_id')
    action  = request.POST.get('action')   # 'open' or 'close'
    duration = int(request.POST.get('duration_minutes', 30))

    node = get_object_or_404(SensorNode, pk=node_id, field=field)

    IrrigationCommand.objects.create(
        node=node,
        field=field,
        issued_by=request.user,
        source='manual',
        valve_open=(action == 'open'),
        duration_minutes=duration,
    )
    messages.success(request, f"Irrigation command ({action}) sent to {node.device_id}.")
    return redirect('iot_sensor:field_detail', field_id=field_id)


# ── 5. ALERT DASHBOARD ───────────────────────────────────────────────────────

@login_required
def alert_dashboard(request):
    alerts = SensorAlert.objects.filter(
        field__in=visible_fields(request.user)
    ).select_related('field', 'reading').order_by('-alert_created')[:50]

    if request.method == 'POST':
        alert_id = request.POST.get('alert_id')
        if alert_id:
            SensorAlert.objects.filter(
                pk=alert_id, field__in=visible_fields(request.user),
            ).update(
                is_read=True, is_resolved=True, resolved_at=timezone.now()
            )
        return redirect('iot_sensor:alert_dashboard')

    context = {'alerts': alerts}
    return render(request, 'iot_sensor/alert_dashboard.html', context)


# ── 6. METRICS DASHBOARD ─────────────────────────────────────────────────────

@login_required
def metrics_dashboard(request):
    """Shows all evaluation metrics from the proposal."""
    logs = SystemMetricsLog.objects.all()[:30]
    latest = logs.first()

    # Compute today's alert latency from DB
    today = timezone.now().date()
    today_alerts = SensorAlert.objects.filter(
        field__in=visible_fields(request.user),
        alert_created__date=today
    )
    total_alerts = today_alerts.count()
    under_2min = today_alerts.filter(
        alert_created__gte=F('reading_time'),
        alert_created__lte=F('reading_time') + timedelta(minutes=2)
    ).count()

    # Compute crop prediction accuracy from farmer feedback
    confirmed = CropPredictionLog.objects.filter(
        field__in=visible_fields(request.user),
        farmer_agreed__isnull=False
    )
    accuracy = None
    if confirmed.exists():
        accuracy = round(confirmed.filter(farmer_agreed=True).count() / confirmed.count() * 100, 1)

    # Node uptime: nodes seen in last 15 minutes
    threshold_time = timezone.now() - timedelta(minutes=15)
    active_nodes = SensorNode.objects.filter(
        field__in=visible_fields(request.user), is_active=True,
    )
    online_nodes = active_nodes.filter(last_seen__gte=threshold_time).count()
    total_nodes  = active_nodes.count()

    context = {
        'logs': logs,
        'latest': latest,
        'today_alerts': total_alerts,
        'alerts_under_2min': under_2min,
        'crop_accuracy': accuracy,
        'online_nodes': online_nodes,
        'total_nodes': total_nodes,
    }
    return render(request, 'iot_sensor/metrics_dashboard.html', context)


# ── 7. ZONE MAP (K-medoids result visualisation) ─────────────────────────────

@login_required
def zone_map(request, field_id):
    field = get_object_or_404(visible_fields(request.user), pk=field_id)
    zones = field.zones.all()
    nodes = field.nodes.filter(is_active=True).exclude(latitude=None)

    if request.method == 'POST':
        k = int(request.POST.get('k', 3))
        from .services.zone_optimizer import optimise_field_zones
        created = optimise_field_zones(field, k)
        messages.success(request, f"{len(created)} zones computed using K-medoids + Weiszfeld algorithm.")
        return redirect('iot_sensor:zone_map', field_id=field_id)

    context = {
        'field': field,
        'zones': zones,
        'nodes': nodes,
        'nodes_json': json.dumps([
            {'id': n.pk, 'lat': float(n.latitude), 'lng': float(n.longitude),
             'label': n.device_id, 'zone': n.placement_zone}
            for n in nodes
        ]),
        'zones_json': json.dumps([
            {'label': z.zone_label,
             'centroid_lat': float(z.centroid_lat) if z.centroid_lat else None,
             'centroid_lng': float(z.centroid_lng) if z.centroid_lng else None,
             'valve_lat': float(z.valve_lat) if z.valve_lat else None,
             'valve_lng': float(z.valve_lng) if z.valve_lng else None}
            for z in zones
        ]),
    }
    return render(request, 'iot_sensor/zone_map.html', context)


# ── 8. LIVE READINGS API (for JS polling) ────────────────────────────────────

@login_required
def readings_api(request, field_id):
    """Returns latest 24 readings as JSON for chart refresh."""
    field = get_object_or_404(visible_fields(request.user), pk=field_id)
    readings = list(field.sensor_readings.all()[:24])
    data = [
        {
            'time': r.recorded_at.strftime('%H:%M'),
            'soil_moisture': r.soil_moisture_pct,
            'temperature':   r.temperature_c,
            'humidity':      r.humidity_pct,
            'nitrogen':      r.nitrogen_ppm,
            'phosphorus':    r.phosphorus_ppm,
            'potassium':     r.potassium_ppm,
            'wind_speed':    r.wind_speed_kmh,
            'solar_lux':     r.solar_lux,
            'water_level':   r.water_level_pct,
        }
        for r in reversed(readings)
    ]
    return JsonResponse({'readings': data})


# ── 8. FARMER SELF-SERVICE HARDWARE REGISTRATION ─────────────────────────────
#
# "Farmer adds the hardware part on phone or laptop, then check the farmer,
#  otherwise this system does not work."
#
# Gate: the account must be verified (owner OR farmer document set) or hold an
# approved lease. hardware_registration_state() decides and returns a reason
# the farmer can act on.

@login_required
def hardware_home(request):
    """Landing page: shows eligibility, existing fields and devices."""
    allowed, reason = hardware_registration_state(request.user)
    profile = get_profile(request.user)
    fields = visible_fields(request.user).select_related('land').prefetch_related('nodes')
    return render(request, 'iot_sensor/hardware_home.html', {
        'can_register': allowed,
        'blocked_reason': reason,
        'profile': profile,
        'fields': fields,
        'missing_documents': profile.missing_documents() if profile else [],
        'required_documents': profile.required_documents() if profile else (),
    })


@login_required
def field_create(request):
    """Farmer/owner creates a monitored field by hand."""
    allowed, reason = hardware_registration_state(request.user)
    if not allowed:
        messages.error(request, reason)
        return redirect('iot_sensor:hardware_home')

    if request.method == 'POST':
        form = FieldForm(request.POST, user=request.user)
        if form.is_valid():
            field = form.save(commit=False)
            field.owner = request.user
            field.save()
            messages.success(
                request,
                f'Field "{field.name}" created. Now register the device that '
                f'will send its readings.',
            )
            return redirect('iot_sensor:node_create', field_id=field.pk)
    else:
        form = FieldForm(user=request.user)

    return render(request, 'iot_sensor/field_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def node_create(request, field_id):
    """
    Register a device against a field and show its API key exactly once.

    The key is displayed here because it is needed to flash the firmware. It is
    not shown again on later page loads - rotate it from the admin if lost.
    """
    allowed, reason = hardware_registration_state(request.user)
    if not allowed:
        messages.error(request, reason)
        return redirect('iot_sensor:hardware_home')

    field = get_object_or_404(visible_fields(request.user), pk=field_id)
    if not can_manage_field(request.user, field):
        messages.error(request, 'You cannot add hardware to this field.')
        return redirect('iot_sensor:hardware_home')

    issued_key = None
    node = None
    if request.method == 'POST':
        form = SensorNodeForm(request.POST)
        if form.is_valid():
            node = form.save(commit=False)
            node.field = field
            node.save()  # save() generates api_key
            issued_key = node.api_key
            messages.success(
                request,
                f'Device {node.device_id} registered to {field.name}.',
            )
            logger.info(
                'Device %s registered to field %s by user %s',
                node.device_id, field.pk, request.user.pk,
            )
            form = SensorNodeForm()  # blank form for adding another
    else:
        form = SensorNodeForm()

    return render(request, 'iot_sensor/node_form.html', {
        'form': form,
        'field': field,
        'issued_key': issued_key,
        'node': node,
        'ingest_url': request.build_absolute_uri(
            reverse('iot_sensor:sensor_ingest')
        ),
    })
