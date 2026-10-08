"""
Validated, spam-resistant public forms.

The contact view previously read request.POST directly and passed the values
straight to Contact.objects.create(). That meant:

* no email validation - any string was stored in an EmailField;
* no length checks - Model.objects.create() does not run validators, so a 5000
  character "name" is accepted. SQLite silently truncates nothing and stores it,
  but PostgreSQL raises DataError and the user gets a 500;
* no spam defence at all - a bot could POST the form in a loop.
"""

import re
import time

from django import forms
from django.core.validators import validate_email

from .models import Contact

# Minimum seconds between the form being rendered and submitted. A human cannot
# read, fill and submit this form in under three seconds; a bot posts instantly.
MIN_SUBMIT_SECONDS = 3

# Crude but effective link-spam signal: real enquiries rarely contain several
# URLs or BBCode.
_URL_RE = re.compile(r'https?://|www\.', re.I)
_BBCODE_RE = re.compile(r'\[/?(?:url|link|img)\b', re.I)


class HoneypotMixin(forms.Form):
    """
    Adds two invisible anti-bot checks.

    `website` is a honeypot: hidden from humans by CSS, so anything that fills
    it is an automated form-filler. `form_rendered_at` records when the page was
    served, catching bots that submit instantly.

    Both fail "silently" from the bot's point of view - we raise a generic
    validation error rather than saying "honeypot triggered", so a spammer
    cannot tune around it.
    """

    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
            'class': 'hp-field',
        }),
        label='Leave this field empty',
    )
    form_rendered_at = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Your submission could not be processed.')
        return ''

    def clean_form_rendered_at(self):
        raw = self.cleaned_data.get('form_rendered_at') or ''
        if not raw:
            # Missing timestamp is tolerated: the form may be cached, or JS off.
            return ''
        try:
            elapsed = time.time() - float(raw)
        except (TypeError, ValueError):
            return ''
        if elapsed < MIN_SUBMIT_SECONDS:
            raise forms.ValidationError(
                'That was submitted very quickly. Please try again.'
            )
        return raw

    @staticmethod
    def initial_timestamp():
        return str(int(time.time()))


class ContactForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = ('name', 'email', 'phone', 'location', 'related_work',
                  'subject', 'message')
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].required = False
        for name, field in self.fields.items():
            if name in ('website', 'form_rendered_at'):
                continue
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < 2:
            raise forms.ValidationError('Please enter your name.')
        if _URL_RE.search(name):
            raise forms.ValidationError('Please enter a real name.')
        return name

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        validate_email(email)
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            return ''
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 7 or len(digits) > 15:
            raise forms.ValidationError(
                'Please enter a valid phone number, or leave it blank.'
            )
        return phone

    def clean_message(self):
        message = (self.cleaned_data.get('message') or '').strip()
        if len(message) < 10:
            raise forms.ValidationError(
                'Please tell us a little more (at least 10 characters).'
            )
        if len(message) > 5000:
            raise forms.ValidationError(
                'That message is too long. Please keep it under 5000 characters.'
            )
        if len(_URL_RE.findall(message)) > 3 or _BBCODE_RE.search(message):
            raise forms.ValidationError(
                'Your message looks like spam because of the number of links. '
                'Please remove some and try again.'
            )
        return message


class NewsletterForm(HoneypotMixin, forms.Form):
    """
    Plain Form, deliberately not a ModelForm.

    NewsletterSubscriber.email is unique, so a ModelForm would reject an
    already-subscribed address as a validation error. Re-subscribing is not a
    user mistake - the view answers "you are already subscribed" via
    get_or_create - so uniqueness is not enforced here.
    """

    email = forms.EmailField(max_length=254)

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        validate_email(email)
        if len(email) > 254:
            raise forms.ValidationError('That email address is too long.')
        return email
