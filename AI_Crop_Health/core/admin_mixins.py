"""
Reusable admin building blocks: CSV export and image thumbnails.

Exporting a queryset is the single most requested admin feature and was
previously impossible without database access.
"""

import csv
from datetime import date, datetime

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

# Refuse to stream an unbounded export: a few hundred thousand rows would hold a
# worker open and exhaust memory.
MAX_EXPORT_ROWS = 50_000

# Never let these leave the system in a spreadsheet.
SENSITIVE_FIELD_NAMES = {
    'password', 'api_key', 'secret', 'token', 'otp', 'code',
}


class ExportCsvMixin:
    """Adds an "Export selected to CSV" action to any ModelAdmin."""

    csv_export_fields = None  # defaults to all concrete fields

    def get_csv_fields(self):
        if self.csv_export_fields:
            return list(self.csv_export_fields)
        return [
            f.name for f in self.model._meta.fields
            if not any(s in f.name.lower() for s in SENSITIVE_FIELD_NAMES)
        ]

    @staticmethod
    def _clean(value):
        """
        Render a cell safely.

        A cell beginning with = + - or @ is executed as a formula by Excel and
        Google Sheets. Prefixing with a quote neutralises that (CSV injection).
        """
        if value is None:
            return ''
        if isinstance(value, (datetime, date)):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.isoformat(sep=' ', timespec='seconds') if isinstance(value, datetime) else value.isoformat()
        text = str(value)
        if text[:1] in ('=', '+', '-', '@', '\t', '\r'):
            return "'" + text
        return text

    @admin.action(description='Export selected to CSV')
    def export_as_csv(self, request, queryset):
        total = queryset.count()
        if total > MAX_EXPORT_ROWS:
            self.message_user(
                request,
                f'{total:,} rows is too many to export at once '
                f'(limit {MAX_EXPORT_ROWS:,}). Filter first, then export.',
                level=messages.ERROR,
            )
            return None

        fields = self.get_csv_fields()
        opts = self.model._meta
        stamp = timezone.localtime().strftime('%Y%m%d-%H%M')
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="{opts.model_name}-{stamp}.csv"'
        )
        # BOM so Excel opens UTF-8 correctly instead of mangling names.
        response.write('﻿')

        writer = csv.writer(response)
        writer.writerow([opts.get_field(f).verbose_name.title() for f in fields])
        for obj in queryset.iterator(chunk_size=2000):
            writer.writerow([self._clean(getattr(obj, f, '')) for f in fields])
        return response


class ThumbnailMixin:
    """Renders a small preview for an image field in list and detail views."""

    thumbnail_field = 'image'

    @admin.display(description='Preview')
    def thumbnail(self, obj):
        image = getattr(obj, self.thumbnail_field, None)
        if not image:
            return format_html('<span style="color:#999">—</span>')
        return format_html(
            '<img src="{}" style="height:48px;width:auto;border-radius:4px;'
            'object-fit:cover;border:1px solid #ddd" alt="">',
            image.url,
        )


class ReadOnlyAdminMixin:
    """
    For log and audit tables: viewable and exportable, never editable.

    Letting staff edit a diagnosis log or an audit trail would destroy its value
    as evidence.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class CompressImagesForm(forms.ModelForm):
    """
    ModelForm that compresses any image uploaded through the admin.

    Marketing images get dropped in at full camera resolution, which then loads
    on every homepage visit. Fields are compressed in place so the admin help
    text ("large uploads are compressed automatically") is actually true.
    """

    compress_fields = ()

    def clean(self):
        cleaned = super().clean()
        from .imaging import compress_image

        for name in self.compress_fields:
            value = cleaned.get(name)
            # Only touch a genuinely new upload; an unchanged field holds an
            # ImageFieldFile, which has nothing to re-compress.
            if value and hasattr(value, 'content_type'):
                cleaned[name] = compress_image(value)
        return cleaned
