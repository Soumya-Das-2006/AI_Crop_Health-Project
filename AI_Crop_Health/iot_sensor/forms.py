"""
Forms for farmer/owner self-service hardware registration.

The farmer does this from a phone in a field, so the forms stay short, use
numeric input types where possible, and explain every field in plain language.
"""

from django import forms

from .models import Field, SensorNode
from .access import leased_land_ids


class FieldForm(forms.ModelForm):
    """Create or edit a monitored field."""

    class Meta:
        model = Field
        fields = (
            'name', 'land', 'location', 'size_acres',
            'soil_type', 'current_crop', 'lifecycle_stage',
            'latitude', 'longitude',
        )
        labels = {
            'name': 'Field name',
            'land': 'Which land is this? (optional)',
            'location': 'Village / area',
            'size_acres': 'Size in acres',
            'soil_type': 'Soil type',
            'current_crop': 'Crop growing now',
            'lifecycle_stage': 'Crop stage',
            'latitude': 'Latitude (optional)',
            'longitude': 'Longitude (optional)',
        }
        help_texts = {
            'name': 'Any name you will recognise, e.g. "North Plot".',
            'land': 'Pick the leased or owned land this field belongs to. '
                    'Linking it lets the land owner see the same sensor data.',
            'latitude': 'Leave blank if you do not know. Tap "Use my location" instead.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'North Plot', 'autocomplete': 'off'}),
            'location': forms.TextInput(attrs={'placeholder': 'Village, District'}),
            'size_acres': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
            'current_crop': forms.TextInput(attrs={'placeholder': 'Rice, Potato, ...'}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'inputmode': 'decimal'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Only offer land the user actually owns or holds an approved lease on,
        # so a field cannot be attached to someone else's parcel.
        from agrolease.models import Land
        if user is not None:
            allowed = Land.objects.filter(pk__in=leased_land_ids(user)) | \
                      Land.objects.filter(owner=user)
            self.fields['land'].queryset = allowed.distinct()
        else:
            self.fields['land'].queryset = Land.objects.none()
        self.fields['land'].required = False
        self.fields['land'].empty_label = 'Not linked to a land listing'

        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            if not isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_size_acres(self):
        size = self.cleaned_data.get('size_acres')
        if size is not None and size <= 0:
            raise forms.ValidationError('Size must be greater than zero.')
        return size


class SensorNodeForm(forms.ModelForm):
    """Register one physical device against a field."""

    class Meta:
        model = SensorNode
        fields = (
            'device_id', 'hardware_type', 'connectivity',
            'placement_zone', 'latitude', 'longitude',
            'has_solar_power', 'firmware_version',
        )
        labels = {
            'device_id': 'Device ID',
            'hardware_type': 'Board type',
            'connectivity': 'How does it connect?',
            'placement_zone': 'Where in the field?',
            'has_solar_power': 'Solar powered',
            'firmware_version': 'Firmware version (optional)',
        }
        help_texts = {
            'device_id': 'The ID printed on the device or flashed into its '
                         'firmware, e.g. ESP32-001. Must be unique.',
        }
        widgets = {
            'device_id': forms.TextInput(attrs={
                'placeholder': 'ESP32-001', 'autocapitalize': 'characters',
                'autocomplete': 'off',
            }),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'inputmode': 'decimal'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                css = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_device_id(self):
        device_id = (self.cleaned_data.get('device_id') or '').strip()
        if not device_id:
            raise forms.ValidationError('Device ID is required.')
        qs = SensorNode.objects.filter(device_id__iexact=device_id)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                'That Device ID is already registered. Each device needs a '
                'unique ID - check the label on the board.'
            )
        return device_id
