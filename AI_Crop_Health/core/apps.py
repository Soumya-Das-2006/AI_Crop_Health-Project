from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals
        import core.admin_extensions

        # Re-title the admin from SiteSettings. Wrapped because ready() also runs
        # during `migrate` on an empty database, before the table exists.
        try:
            from core.admin_site import apply_admin_branding
            apply_admin_branding()
        except Exception:
            pass
