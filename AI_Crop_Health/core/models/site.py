"""
Editable site configuration and homepage content.

Everything here used to live in settings.py / .env, which meant changing a phone
number or a social link required a code change and a redeploy. Real secrets
(SECRET_KEY, database credentials, API keys) deliberately stay in the
environment - they do not belong in a database that staff can read.

SiteSettings is a singleton: exactly one row, enforced in save(), and cached so
reading it costs nothing per request.
"""

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

SETTINGS_CACHE_KEY = 'core.site_settings'
SETTINGS_CACHE_TTL = 300


class SiteSettings(models.Model):
    """Singleton holding everything an administrator can change without a deploy."""

    # ---------------- identity ----------------
    site_name = models.CharField(
        max_length=100, default='AI Crop Health',
        help_text='Shown in the browser tab, link previews and the admin header.',
    )
    tagline = models.CharField(
        max_length=255,
        default='AI crop disease diagnosis, land leasing and IoT field monitoring for farmers',
        help_text='Used as the default meta description and link-preview text.',
    )
    logo = models.ImageField(
        upload_to='site/', blank=True, null=True,
        help_text='Header logo. Leave blank to use the bundled default.',
    )
    social_preview_image = models.ImageField(
        upload_to='site/', blank=True, null=True,
        help_text='Shown when a link is shared on WhatsApp/Facebook/X. 1200x630 works best.',
    )

    # ---------------- contact ----------------
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    whatsapp_number = models.CharField(
        max_length=30, blank=True,
        help_text='Digits with country code, no +. Example: 919876543210',
    )
    address = models.TextField(blank=True)

    # ---------------- social ----------------
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)

    # ---------------- analytics ----------------
    analytics_script_url = models.URLField(
        blank=True,
        help_text='Cookieless analytics script, e.g. https://plausible.io/js/script.js. '
                  'Blank disables analytics. Only loaded after the visitor consents.',
    )
    analytics_site_id = models.CharField(max_length=120, blank=True)

    # ---------------- feature toggles ----------------
    enable_marketplace = models.BooleanField(default=True)
    enable_iot = models.BooleanField(default=True, verbose_name='Enable IoT sensors')
    enable_chatbot = models.BooleanField(default=True)
    enable_agrolease = models.BooleanField(default=True, verbose_name='Enable land leasing')
    enable_registration = models.BooleanField(
        default=True, help_text='Uncheck to stop new sign-ups without taking the site down.',
    )

    # ---------------- diagnosis tuning ----------------
    diagnosis_confidence_threshold = models.FloatField(
        default=97.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='A prediction below this confidence is flagged to the farmer as '
                  'unreliable. This is NOT a measure of model accuracy.',
    )
    diagnosis_disclaimer = models.TextField(
        default='This diagnosis is advisory and can be wrong. Confirm with a '
                'qualified agronomist before treating or destroying a crop.',
        help_text='Shown with every diagnosis result.',
    )

    # ---------------- maintenance ----------------
    maintenance_mode = models.BooleanField(
        default=False,
        help_text='Shows a maintenance notice to visitors. Staff can still browse.',
    )
    maintenance_message = models.TextField(
        blank=True, default='We are carrying out scheduled maintenance. Please check back shortly.',
    )
    announcement = models.CharField(
        max_length=300, blank=True,
        help_text='Optional banner shown at the top of every page. Blank hides it.',
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='site_settings_updates',
    )

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return self.site_name

    def clean(self):
        if self.maintenance_mode and not self.maintenance_message.strip():
            raise ValidationError({
                'maintenance_message': 'Write a message visitors will see during maintenance.',
            })

    def save(self, *args, **kwargs):
        # Singleton: always row 1, so a second instance cannot be created.
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SETTINGS_CACHE_KEY)

    def delete(self, *args, **kwargs):
        """Deleting site configuration is never what someone meant to do."""
        raise ValidationError('Site settings cannot be deleted, only edited.')

    @classmethod
    def load(cls):
        """
        Return the settings row, creating it on first use.

        Cached: this is read on every page render through the context processor.
        Falls back to an unsaved instance if the table does not exist yet, so a
        fresh clone can run `migrate` without the context processor exploding.
        """
        cached = cache.get(SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached
        try:
            obj, _ = cls.objects.get_or_create(pk=1)
        except Exception:
            return cls()
        cache.set(SETTINGS_CACHE_KEY, obj, SETTINGS_CACHE_TTL)
        return obj

    @property
    def social_links(self):
        """Only the profiles that are actually set, so no dead icons render."""
        pairs = (
            ('facebook', self.facebook_url),
            ('twitter', self.twitter_url),
            ('instagram', self.instagram_url),
            ('linkedin', self.linkedin_url),
            ('youtube', self.youtube_url),
            ('telegram', self.telegram_url),
            ('github', self.github_url),
        )
        links = {name: url for name, url in pairs if url}
        if self.whatsapp_number:
            digits = ''.join(c for c in self.whatsapp_number if c.isdigit())
            if digits:
                links['whatsapp'] = f'https://wa.me/{digits}'
        return links


class OrderedActiveQuerySet(models.QuerySet):
    def live(self):
        return self.filter(is_active=True)


class HeroSlide(models.Model):
    """One slide in the homepage carousel, editable without touching templates."""

    heading = models.CharField(max_length=160)
    body = models.TextField(
        blank=True, help_text='One or two short sentences. Keep it readable on a phone.',
    )
    image = models.ImageField(
        upload_to='site/hero/', blank=True, null=True,
        help_text='Wide image, around 1920x1080. Large uploads are compressed automatically.',
    )
    image_alt = models.CharField(
        max_length=160, blank=True,
        help_text='Describes the image for screen readers and when images fail to load.',
    )
    cta_label = models.CharField(
        max_length=60, blank=True, default='Scan your crop free',
        help_text='Button text. Blank hides the button.',
    )
    cta_url = models.CharField(
        max_length=300, blank=True, default='/detection/diagnosis/',
        help_text='Where the button goes. A path like /detection/diagnosis/ or a full URL.',
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = OrderedActiveQuerySet.as_manager()

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Homepage hero slide'

    def __str__(self):
        return self.heading


class FeatureCard(models.Model):
    """A feature tile on the homepage."""

    title = models.CharField(max_length=120)
    description = models.TextField()
    icon = models.CharField(
        max_length=60, blank=True, default='bi-leaf',
        help_text='A Bootstrap Icons class, e.g. bi-leaf, bi-cpu, bi-droplet.',
    )
    link_label = models.CharField(max_length=60, blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    objects = OrderedActiveQuerySet.as_manager()

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Homepage feature card'

    def __str__(self):
        return self.title
