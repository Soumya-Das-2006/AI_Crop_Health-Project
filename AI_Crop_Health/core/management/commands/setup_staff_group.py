from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Sets up the default Staff group with restricted permissions'

    def handle(self, *args, **options):
        staff_group, created = Group.objects.get_or_create(name='Staff')
        
        # Define matrix of (app_label, model_name, permissions_to_grant)
        matrix = [
            # Authentication
            ('auth', 'user', ['view_user', 'change_user', 'add_user']),
            # Core
            ('core', 'auditlog', ['view_auditlog']),
            ('core', 'notificationrecord', ['view_notificationrecord', 'change_notificationrecord']),
            ('core', 'notificationtemplate', ['view_notificationtemplate', 'change_notificationtemplate', 'add_notificationtemplate']),
            # Agrolease
            ('agrolease', 'agroprofile', ['view_agroprofile', 'change_agroprofile']),
            ('agrolease', 'land', ['view_land', 'change_land', 'add_land']),
            ('agrolease', 'leaserequest', ['view_leaserequest', 'change_leaserequest']),
            ('agrolease', 'leaseagreement', ['view_leaseagreement', 'change_leaseagreement']),
            # Blog
            ('blog', 'blogpost', ['view_blogpost', 'change_blogpost', 'add_blogpost', 'delete_blogpost']),
            ('blog', 'category', ['view_category', 'change_category', 'add_category']),
            ('blog', 'comment', ['view_comment', 'change_comment', 'delete_comment']),
            # Contact
            ('contact', 'contact', ['view_contact', 'change_contact']),
            ('contact', 'wastesubmission', ['view_wastesubmission', 'change_wastesubmission']),
            # Detection
            ('detection', 'diagnosislog', ['view_diagnosislog', 'change_diagnosislog']),
            ('detection', 'farmerfeedback', ['view_farmerfeedback']),
            ('detection', 'agriculturesuggestion', ['view_agriculturesuggestion', 'change_agriculturesuggestion', 'add_agriculturesuggestion']),
            ('detection', 'agriculturealert', ['view_agriculturealert', 'change_agriculturealert', 'add_agriculturealert']),
            # Features
            ('features', 'cropinfo', ['view_cropinfo', 'change_cropinfo', 'add_cropinfo']),
            ('features', 'marketprice', ['view_marketprice', 'change_marketprice', 'add_marketprice']),
            ('features', 'governmentscheme', ['view_governmentscheme', 'change_governmentscheme', 'add_governmentscheme']),
            ('features', 'supportmessage', ['view_supportmessage', 'change_supportmessage']),
            # Marketplace
            ('marketplace', 'category', ['view_category']),
            ('marketplace', 'product', ['view_product', 'add_product', 'change_product']),
            ('marketplace', 'order', ['view_order', 'change_order']),
        ]

        permissions_added = 0
        staff_permissions = []
        for app_label, model_name, codenames in matrix:
            try:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
                for codename in codenames:
                    try:
                        perm = Permission.objects.get(content_type=ct, codename=codename)
                        staff_permissions.append(perm)
                        permissions_added += 1
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Permission {codename} does not exist"))
            except ContentType.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Model {app_label}.{model_name} does not exist in ContentType yet"))

        staff_group.permissions.set(staff_permissions)
        self.stdout.write(self.style.SUCCESS(f'Successfully configured Staff group with {permissions_added} permissions'))
