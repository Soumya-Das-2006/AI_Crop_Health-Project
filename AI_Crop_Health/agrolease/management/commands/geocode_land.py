import time

from django.core.management.base import BaseCommand

from agrolease.geocoding import geocode_location
from agrolease.models import Land


class Command(BaseCommand):
    help = 'Geocode land listings that do not have coordinates.'

    def handle(self, *args, **options):
        listings = Land.objects.filter(latitude__isnull=True, longitude__isnull=True)
        updated = 0
        skipped = 0

        for land in listings:
            coordinates = geocode_location(land.location)
            if not coordinates:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'Skipped: {land.location}'))
                continue

            land.latitude, land.longitude = coordinates
            land.save(update_fields=['latitude', 'longitude'])
            updated += 1
            self.stdout.write(self.style.SUCCESS(f'Geocoded: {land.location}'))
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f'Updated {updated} listing(s); skipped {skipped}.'))
