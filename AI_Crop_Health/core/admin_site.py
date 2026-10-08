"""
Branded admin site.

The default admin says "Django administration", which tells an administrator
nothing about which system they are in. Titles are read from the editable
SiteSettings row, so renaming the platform renames the admin too.

This does NOT replace admin.site - swapping the global admin site would mean
re-registering every ModelAdmin across nine apps. Instead the existing site is
re-titled in place, which keeps all current registrations working.
"""

from django.contrib import admin


def apply_admin_branding():
    """Set the admin titles from SiteSettings, falling back to a sane default."""
    name = 'AI Crop Health'
    try:
        from .models import SiteSettings

        config = SiteSettings.load()
        if config and config.site_name:
            name = config.site_name
    except Exception:
        # Runs at import time, before migrations on a fresh database.
        pass

    admin.site.site_header = f'{name} — Control Center'
    admin.site.site_title = f'{name} admin'
    admin.site.index_title = 'Manage your platform'
    # Shown as the "View site" link in the admin header.
    admin.site.site_url = '/'
