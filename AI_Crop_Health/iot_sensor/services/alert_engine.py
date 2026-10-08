"""
Alert Engine
-----------
Called after every SensorReading is saved.
Checks all active SensorThresholds for the field,
creates SensorAlert records, and optionally issues
an IrrigationCommand (closed-loop automation).
Target latency: < 2 minutes from reading time.
"""

import logging
from django.utils import timezone
from ..models import SensorThreshold, SensorAlert, IrrigationCommand

logger = logging.getLogger(__name__)


def check_reading(reading):
    """
    Entry point — pass a freshly-saved SensorReading.
    Returns list of SensorAlert objects created.
    """
    alerts_created = []
    thresholds = SensorThreshold.objects.filter(
        field=reading.field, is_active=True
    )

    for threshold in thresholds:
        value = getattr(reading, threshold.variable, None)
        if value is None:
            continue

        breach_type = None
        if threshold.min_value is not None and value < threshold.min_value:
            breach_type = 'low'
        elif threshold.max_value is not None and value > threshold.max_value:
            breach_type = 'high'

        if breach_type:
            severity = _get_severity(threshold.variable, value, threshold, breach_type)
            message = _build_message(threshold, value, breach_type)

            alert = SensorAlert.objects.create(
                field=reading.field,
                threshold=threshold,
                reading=reading,
                severity=severity,
                variable=threshold.variable,
                actual_value=value,
                breach_type=breach_type,
                message=message,
                reading_time=reading.recorded_at,
            )
            alerts_created.append(alert)
            logger.info("Alert created: %s", alert)

            # Closed-loop: auto-irrigate on low moisture
            if (
                threshold.variable == 'soil_moisture_pct'
                and breach_type == 'low'
                and threshold.auto_irrigate_on_low_moisture
            ):
                _issue_irrigation_command(reading, alert)

    return alerts_created


def _get_severity(variable, value, threshold, breach_type):
    # Critical if more than 20% outside the bound
    if breach_type == 'low' and threshold.min_value:
        deviation = (threshold.min_value - value) / max(threshold.min_value, 1)
    elif breach_type == 'high' and threshold.max_value:
        deviation = (value - threshold.max_value) / max(threshold.max_value, 1)
    else:
        deviation = 0

    if deviation > 0.20:
        return 'critical'
    elif deviation > 0.10:
        return 'warning'
    return 'info'


def _build_message(threshold, value, breach_type):
    label = threshold.get_variable_display()
    bound = threshold.min_value if breach_type == 'low' else threshold.max_value
    direction = "below minimum" if breach_type == 'low' else "above maximum"
    return (
        f"{label} is {value:.2f} — {direction} threshold of {bound:.2f} "
        f"in field '{threshold.field.name}'. Immediate attention required."
    )


def _issue_irrigation_command(reading, alert):
    """Issue an automatic solenoid valve open command."""
    node = reading.node
    cmd = IrrigationCommand.objects.create(
        node=node,
        field=reading.field,
        issued_by=None,           # AI-issued
        source='ai_auto',
        valve_open=True,
        duration_minutes=45,
        trigger_reading=reading,
        notes=f"Auto-triggered by alert {alert.pk}: {alert.message[:100]}",
    )
    logger.info("Irrigation command issued: %s", cmd)
    return cmd
