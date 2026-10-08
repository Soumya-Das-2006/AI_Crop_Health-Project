"""
Populate SiteSettings from the current environment, once.

Settings moved from .env into the database so they can be changed without a
deploy. This copies whatever is already configured into that row, so an existing
deployment keeps its exact branding instead of silently reverting to defaults.

Only fills blanks by default - it will not overwrite something an administrator
has already edited in the admin.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import FeatureCard, HeroSlide, SiteSettings

DEFAULT_SLIDES = [
    {
        'heading': 'AI-Powered Crop Health Detection & Nutrient Analysis',
        'body': 'Detect crop diseases instantly with advanced machine learning and get '
                'nutrient recommendations to improve your harvest.',
        'image_alt': 'A drone flying over a green crop field at sunrise',
        'sort_order': 1,
    },
    {
        'heading': 'Spot Crop Disease From a Single Photo',
        'body': 'Upload a leaf image and get an instant assessment across 38 crop '
                'conditions, with treatment guidance. Always confirm with an agronomist.',
        'image_alt': 'A farmer photographing a crop leaf with a phone',
        'sort_order': 2,
    },
    {
        'heading': 'Monitor Your Fields With Real Sensors',
        'body': 'Soil moisture, N-P-K and pH from your own hardware, with alerts when '
                'a field needs attention.',
        'image_alt': 'A soil sensor installed between rows of crops',
        'sort_order': 3,
    },
]

DEFAULT_CARDS = [
    {'title': 'Disease Diagnosis', 'icon': 'bi-leaf', 'sort_order': 1,
     'description': 'Photograph a leaf and get an assessment across 38 crop conditions '
                    'in seconds, with treatment guidance.',
     'link_label': 'Scan a crop', 'link_url': '/detection/diagnosis/'},
    {'title': 'Crop & Fertilizer Advice', 'icon': 'bi-seedling', 'sort_order': 2,
     'description': 'Recommendations based on your soil readings, filled in '
                    'automatically from your sensors where available.',
     'link_label': 'Get advice', 'link_url': '/detection/crop-recommendation/'},
    {'title': 'Field Monitoring', 'icon': 'bi-broadcast', 'sort_order': 3,
     'description': 'Live soil moisture, nutrients and pH from your own devices, '
                    'with alerts and irrigation control.',
     'link_label': 'My fields', 'link_url': '/iot/fields/'},
    {'title': 'Land Leasing', 'icon': 'bi-file-earmark-text', 'sort_order': 4,
     'description': 'Land owners list, farmers lease. Both sides verified, with a '
                    'digital agreement at the end.',
     'link_label': 'Find land', 'link_url': '/agrolease/'},
]


class Command(BaseCommand):
    help = 'Copy branding/social/analytics from .env into the editable SiteSettings row.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Overwrite values already set in the admin. Off by default so '
                 'this cannot undo someone\'s edits.',
        )
        parser.add_argument(
            '--with-content', action='store_true',
            help='Also create starter hero slides and feature cards, if none exist.',
        )

    def handle(self, *args, **options):
        config = SiteSettings.load()
        force = options['force']
        changed = []

        def fill(field, value):
            if not value:
                return
            if force or not getattr(config, field):
                if getattr(config, field) != value:
                    setattr(config, field, value)
                    changed.append(field)

        fill('site_name', getattr(settings, 'SITE_NAME', ''))
        fill('tagline', getattr(settings, 'SITE_TAGLINE', ''))
        fill('analytics_script_url', getattr(settings, 'ANALYTICS_SCRIPT_URL', ''))
        fill('analytics_site_id', getattr(settings, 'ANALYTICS_SITE_ID', ''))

        env_social = getattr(settings, 'SOCIAL_LINKS', {}) or {}
        for key, field in (('facebook', 'facebook_url'), ('twitter', 'twitter_url'),
                           ('instagram', 'instagram_url'), ('linkedin', 'linkedin_url'),
                           ('youtube', 'youtube_url')):
            fill(field, env_social.get(key, ''))

        fill('contact_email', getattr(settings, 'DEFAULT_FROM_EMAIL', '') or
             getattr(settings, 'EMAIL_HOST_USER', ''))

        if changed:
            config.save()
            self.stdout.write(self.style.SUCCESS(
                f'Site settings updated from environment: {", ".join(sorted(set(changed)))}'))
        else:
            self.stdout.write('Site settings already populated; nothing to copy.')

        if options['with_content']:
            if HeroSlide.objects.exists():
                self.stdout.write('Hero slides already exist; left alone.')
            else:
                HeroSlide.objects.bulk_create([HeroSlide(**s) for s in DEFAULT_SLIDES])
                self.stdout.write(self.style.SUCCESS(
                    f'Created {len(DEFAULT_SLIDES)} starter hero slides '
                    '(add images in admin: Core > Homepage hero slides).'))

            if FeatureCard.objects.exists():
                self.stdout.write('Feature cards already exist; left alone.')
            else:
                FeatureCard.objects.bulk_create([FeatureCard(**c) for c in DEFAULT_CARDS])
                self.stdout.write(self.style.SUCCESS(
                    f'Created {len(DEFAULT_CARDS)} starter feature cards.'))

        self.stdout.write('')
        self.stdout.write('Edit everything at: /admin/core/sitesettings/')
