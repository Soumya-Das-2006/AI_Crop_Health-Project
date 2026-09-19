import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from detection.models import DiagnosisLog, DetectionHistory

class Command(BaseCommand):
    help = 'Cleans up temporary detection images for guest users or un-saved detections.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete un-saved detections older than this number of days (default 7)'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get all diagnosis logs older than cutoff date that are NOT saved in DetectionHistory
        saved_log_ids = DetectionHistory.objects.values_list('diagnosis_log_id', flat=True)
        logs_to_delete = DiagnosisLog.objects.filter(timestamp__lt=cutoff_date).exclude(id__in=saved_log_ids)
        
        count = 0
        for log in logs_to_delete:
            if log.uploaded_image and os.path.isfile(log.uploaded_image.path):
                os.remove(log.uploaded_image.path)
            log.delete()
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully cleaned up {count} un-saved temporary detections older than {days} days.'))
