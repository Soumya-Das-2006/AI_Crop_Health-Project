"""
Management Command: seed_demo_data
------------------------------------
Creates realistic demo data so the IoT dashboard works
immediately without physical hardware.

Creates:
  - 1 demo farmer user + AgroProfile
  - 2 Fields  (North Plot, South Plot)
  - 3 SensorNodes per field (ESP32)
  - SensorThresholds (soil moisture, NPK, temperature)
  - 96 SensorReadings per field (last 8 hours @ 5-min interval)
  - Auto-runs alert engine on each reading

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --flush   # clears existing demo data first
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seed realistic demo IoT sensor data for development/demo.'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete all existing IoT demo data first.')

    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        from agrolease.models import AgroProfile
        from iot_sensor.models import (
            Field, SensorNode, SensorReading, SensorThreshold,
            IrrigationCommand, FieldZone
        )
        from iot_sensor.services.alert_engine import check_reading

        if options['flush']:
            self.stdout.write('Flushing existing IoT demo data...')
            Field.objects.filter(name__in=['North Plot', 'South Plot']).delete()
            User.objects.filter(username='demo_farmer_iot').delete()
            self.stdout.write('Flushed.')

        # ── Create demo user ─────────────────────────────────────────────────
        user, _ = User.objects.get_or_create(
            username='demo_farmer_iot',
            defaults=dict(first_name='Demo', last_name='Farmer')
        )
        # The related_name is `agroprofile`, not `agro_profile`, so this guard
        # was always True. get_or_create is idempotent, so just call it.
        # Demo data is seeded as a verified farmer with its documents marked
        # reviewed, so the hardware-registration gate lets the demo through.
        AgroProfile.objects.update_or_create(
            user=user,
            defaults=dict(
                role='farmer', roles=['farmer'], phone_number='9999999999',
                is_verified=True, verification_status='approved',
            ),
        )

        # ── Create fields ────────────────────────────────────────────────────
        field_configs = [
            dict(name='North Plot', current_crop='Rice', lifecycle_stage='vegetative',
                 size_acres=5.5, soil_type='clay',
                 latitude=20.5937, longitude=78.9629),
            dict(name='South Plot', current_crop='Wheat', lifecycle_stage='flowering',
                 size_acres=3.2, soil_type='alluvial',
                 latitude=20.5950, longitude=78.9645),
        ]

        for fc in field_configs:
            field, created = Field.objects.get_or_create(
                owner=user, name=fc['name'], defaults=fc
            )
            if not created:
                self.stdout.write(f'Field {field.name} already exists, skipping.')
                continue

            # ── Sensor Nodes ─────────────────────────────────────────────────
            nodes = []
            for i in range(3):
                lat_offset = random.uniform(-0.0003, 0.0003)
                lng_offset = random.uniform(-0.0003, 0.0003)
                node = SensorNode.objects.create(
                    field=field,
                    device_id=f"ESP32-{field.name[:1].upper()}{i+1:02d}",
                    hardware_type='esp32',
                    connectivity='gsm',
                    latitude=float(fc['latitude']) + lat_offset,
                    longitude=float(fc['longitude']) + lng_offset,
                    has_solar_power=True,
                    battery_pct=random.randint(70, 100),
                    firmware_version='v2.1.4',
                )
                nodes.append(node)
            self.stdout.write(f'  Created {len(nodes)} nodes for {field.name}')

            # ── Thresholds ───────────────────────────────────────────────────
            SensorThreshold.objects.bulk_create([
                SensorThreshold(field=field, variable='soil_moisture_pct',
                                min_value=30, max_value=80,
                                auto_irrigate_on_low_moisture=True),
                SensorThreshold(field=field, variable='temperature_c',
                                min_value=10, max_value=38),
                SensorThreshold(field=field, variable='humidity_pct',
                                min_value=40, max_value=90),
                SensorThreshold(field=field, variable='nitrogen_ppm',
                                min_value=80, max_value=300),
                SensorThreshold(field=field, variable='water_level_pct',
                                min_value=20, max_value=100),
            ])

            # ── Sensor Readings (96 = 8 hours @ 5-min intervals) ──────────────
            now = timezone.now()
            reading_count = 0
            for minutes_ago in range(96 * 5, 0, -5):
                ts = now - timedelta(minutes=minutes_ago)
                # Simulate diurnal variation
                hour = ts.hour
                temp_base = 22 + 8 * abs(hour - 14) / 14  # peaks at 14:00
                moisture_base = 55 - (minutes_ago / 200)  # dries over time
                node = random.choice(nodes)
                reading = SensorReading.objects.create(
                    node=node,
                    field=field,
                    recorded_at=ts,
                    soil_moisture_pct = max(10, min(95, moisture_base + random.uniform(-5, 5))),
                    nitrogen_ppm      = round(random.uniform(90, 250), 1),
                    phosphorus_ppm    = round(random.uniform(40, 120), 1),
                    potassium_ppm     = round(random.uniform(80, 220), 1),
                    soil_ph           = round(random.uniform(5.5, 7.5), 2),
                    temperature_c     = round(temp_base + random.uniform(-2, 2), 1),
                    humidity_pct      = round(random.uniform(50, 85), 1),
                    wind_speed_kmh    = round(random.uniform(2, 25), 1),
                    solar_lux         = max(0, round(40000 * max(0, 1 - abs(hour - 12) / 8) + random.uniform(-2000, 2000))),
                    rainfall_mm       = round(random.uniform(0, 2) if random.random() < 0.1 else 0, 1),
                    water_level_pct   = round(random.uniform(40, 90), 1),
                    packet_id         = f"PKT-{ts.strftime('%Y%m%d%H%M')}-{node.device_id}",
                    rssi_dbm          = random.randint(-95, -55),
                    is_valid          = True,
                )
                check_reading(reading)
                reading_count += 1

            self.stdout.write(f'  Created {reading_count} readings for {field.name}')

        self.stdout.write(self.style.SUCCESS(
            '\nDemo data seeded successfully!\n'
            '   Login: username=demo_farmer_iot  OTP=123456\n'
            '   Visit: /iot/fields/'
        ))
