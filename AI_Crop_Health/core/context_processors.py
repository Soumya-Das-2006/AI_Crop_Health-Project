"""
Site-wide template context: branding, social profiles, SEO and feature toggles.

Values come from the editable SiteSettings row so an administrator can change
them without a deploy. Each one falls back to the settings.py/.env value when
the database field is blank, so an existing deployment keeps working unchanged
until someone actually edits it in the admin.
"""

import logging

from django.conf import settings

from .models import FeatureCard, HeroSlide, SiteSettings

logger = logging.getLogger(__name__)


def _absolute(request, url):
    """og:image and twitter:image are ignored unless the URL is absolute."""
    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    return request.build_absolute_uri(url)


# Icon and label for each link the topbar can show. Order here is the order
# they render in. Adding a network is an entry here plus an env var - never a
# template edit, which is how `whatsapp` ended up configurable in settings but
# missing from the topbar: the markup hardcoded five networks and ignored the
# rest of the dictionary.
SOCIAL_ICON_META = (
    ('whatsapp', 'fab fa-whatsapp', 'WhatsApp'),
    ('facebook', 'fab fa-facebook-f', 'Facebook'),
    ('twitter', 'bi bi-twitter-x', 'X'),
    ('instagram', 'fab fa-instagram', 'Instagram'),
    ('linkedin', 'fab fa-linkedin-in', 'LinkedIn'),
    ('youtube', 'fab fa-youtube', 'YouTube'),
    ('telegram', 'fab fa-telegram', 'Telegram'),
    ('github', 'fab fa-github', 'GitHub'),
)


def _whatsapp_url(value):
    """
    Accept either a full wa.me link or a bare phone number.

    People configuring this reach for the phone number, and a bare number in an
    href produces a dead relative link. Digits are turned into a real wa.me URL.
    """
    value = (value or '').strip()
    if not value:
        return ''
    if value.startswith(('http://', 'https://')):
        return value
    digits = ''.join(ch for ch in value if ch.isdigit())
    return 'https://wa.me/{0}'.format(digits) if digits else ''


def build_social_icons(social, phone='', email=''):
    """
    Turn the configured links into a render-ready list of icons.

    Every configured link gets an icon; blank ones are skipped so the bar never
    shows a link that goes nowhere. Phone and email are included because they
    are the two a farmer is most likely to use, and they were previously buried
    as text on the other side of the bar.
    """
    icons = []

    phone = (phone or '').strip()
    if phone:
        icons.append({
            'key': 'phone',
            'url': 'tel:{0}'.format(phone.replace(' ', '')),
            'icon': 'fas fa-phone-alt',
            'label': 'Call {0}'.format(phone),
            'external': False,
        })

    email = (email or '').strip()
    if email:
        icons.append({
            'key': 'email',
            'url': 'mailto:{0}'.format(email),
            'icon': 'far fa-envelope',
            'label': 'Email {0}'.format(email),
            'external': False,
        })

    for key, icon, label in SOCIAL_ICON_META:
        raw = (social or {}).get(key, '')
        url = _whatsapp_url(raw) if key == 'whatsapp' else (raw or '').strip()
        if not url:
            continue
        icons.append({
            'key': key,
            'url': url,
            'icon': icon,
            'label': label,
            'external': True,
        })

    return icons


def site_meta(request):
    try:
        config = SiteSettings.load()
    except Exception:
        # Never let a configuration read break every page on the site.
        logger.exception('Could not load SiteSettings; falling back to settings.py')
        config = None

    if config is None or not config.pk:
        # Pre-migration or error: use the environment values as before.
        social = {k: v for k, v in getattr(settings, 'SOCIAL_LINKS', {}).items() if v}
        return {
            'SITE_NAME': getattr(settings, 'SITE_NAME', 'AI Crop Health'),
            'SITE_TAGLINE': getattr(settings, 'SITE_TAGLINE', ''),
            'SOCIAL_LINKS': social,
            'SOCIAL_ICONS': build_social_icons(
                social,
                phone=getattr(settings, 'COMPANY_PHONE', ''),
                email=getattr(settings, 'COMPANY_EMAIL', ''),
            ),
            'SOCIAL_PREVIEW_IMAGE': _absolute(
                request, getattr(settings, 'SOCIAL_PREVIEW_IMAGE', '')),
            'CANONICAL_URL': request.build_absolute_uri(request.path),
            'ANALYTICS_ENABLED': bool(getattr(settings, 'ANALYTICS_SCRIPT_URL', '')),
            'ANALYTICS_SCRIPT_URL': getattr(settings, 'ANALYTICS_SCRIPT_URL', ''),
            'ANALYTICS_SITE_ID': getattr(settings, 'ANALYTICS_SITE_ID', ''),
            'SITE_CONFIG': None,
            'FEATURES': {},
            'HERO_SLIDES': [],
            'FEATURE_CARDS': [],
            'SITE_ANNOUNCEMENT': '',
        }

    social = config.social_links
    if not social:
        social = {k: v for k, v in getattr(settings, 'SOCIAL_LINKS', {}).items() if v}

    preview = ''
    if config.social_preview_image:
        preview = config.social_preview_image.url
    else:
        preview = getattr(settings, 'SOCIAL_PREVIEW_IMAGE', '')

    analytics_url = config.analytics_script_url or getattr(
        settings, 'ANALYTICS_SCRIPT_URL', '')
    analytics_id = config.analytics_site_id or getattr(
        settings, 'ANALYTICS_SITE_ID', '')

    # Homepage content is only queried on the page that renders it.
    hero_slides = []
    feature_cards = []
    if request.path == '/':
        hero_slides = list(HeroSlide.objects.live())
        feature_cards = list(FeatureCard.objects.live())

    return {
        'SITE_NAME': config.site_name or getattr(settings, 'SITE_NAME', 'AI Crop Health'),
        'SITE_TAGLINE': config.tagline or getattr(settings, 'SITE_TAGLINE', ''),
        'SITE_LOGO': config.logo.url if config.logo else '',
        'SOCIAL_LINKS': social,
        'SOCIAL_ICONS': build_social_icons(
            social,
            phone=config.contact_phone or getattr(settings, 'COMPANY_PHONE', ''),
            email=config.contact_email or getattr(settings, 'COMPANY_EMAIL', ''),
        ),
        'SOCIAL_PREVIEW_IMAGE': _absolute(request, preview),
        'CANONICAL_URL': request.build_absolute_uri(request.path),

        'ANALYTICS_ENABLED': bool(analytics_url),
        'ANALYTICS_SCRIPT_URL': analytics_url,
        'ANALYTICS_SITE_ID': analytics_id,

        'SITE_CONFIG': config,
        'SITE_ANNOUNCEMENT': config.announcement,
        'CONTACT_EMAIL': config.contact_email,
        'CONTACT_PHONE': config.contact_phone,
        'CONTACT_ADDRESS': config.address,

        # Feature toggles, so a template can hide a section an admin switched off.
        'FEATURES': {
            'marketplace': config.enable_marketplace,
            'iot': config.enable_iot,
            'chatbot': config.enable_chatbot,
            'agrolease': config.enable_agrolease,
            'registration': config.enable_registration,
        },

        'HERO_SLIDES': hero_slides,
        'FEATURE_CARDS': feature_cards,
    }


def company(request):
    """
    Company identity for the legal pages, the contact page and the footer.

    Everything renders from settings rather than being typed into templates, so
    the published entity name, address and jurisdiction can never drift apart
    between pages - and deploying to a new host is a single environment
    variable, not a template edit.
    """
    from django.conf import settings as s

    return {
        "company": {
            "name": s.COMPANY_NAME,
            "short_name": s.COMPANY_SHORT_NAME,
            "address": s.COMPANY_ADDRESS,
            "email": s.COMPANY_EMAIL,
            "phone": s.COMPANY_PHONE,
            "jurisdiction": s.COMPANY_JURISDICTION,
            "courts_city": s.COMPANY_COURTS_CITY,
            "hosting_provider": s.COMPANY_HOSTING_PROVIDER,
            "policy_updated": s.COMPANY_POLICY_UPDATED,
        }
    }
