"""
Create scoped staff roles.

Without this, every staff member is effectively an administrator. That matters
here because the admin exposes farmers' government ID documents, address proofs
and selfies: a content editor who updates blog posts has no business opening
them. Each group below gets only the models its job needs.

Idempotent - safe to re-run after adding models or changing a role.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

# role -> {'app.model': 'rwad'}
#   r = view, w = add, a = change, d = delete
ROLES = {
    'Verification Reviewer': {
        'description': 'Approves farmer and land-owner KYC. The only role that '
                       'can open identity documents.',
        'perms': {
            'agrolease.agroprofile': 'ra',
            'agrolease.land': 'ra',
            'agrolease.leaserequest': 'ra',
            'agrolease.leaseagreement': 'r',
            'agrolease.leasemessage': 'r',
            'core.auditlog': 'r',
        },
    },
    'Content Editor': {
        'description': 'Blog, schemes, crop info, products, homepage content. '
                       'Deliberately no access to any personal data.',
        'perms': {
            'blog.blogpost': 'rwad',
            'blog.category': 'rwad',
            'blog.comment': 'rad',
            'features.cropinfo': 'rwad',
            'features.governmentscheme': 'rwad',
            'features.schemecategory': 'rwad',
            'features.marketprice': 'rwad',
            'contact.service': 'rwad',
            'contact.testimonial': 'rwad',
            'marketplace.product': 'rwad',
            'marketplace.category': 'rwad',
            'marketplace.productimage': 'rwad',
            'core.heroslide': 'rwad',
            'core.featurecard': 'rwad',
        },
    },
    'Support Agent': {
        'description': 'Answers enquiries and farmer feedback. Can read '
                       'diagnoses to help, but cannot alter them.',
        'perms': {
            'contact.contact': 'ra',
            'contact.newslettersubscriber': 'rd',
            'contact.wastesubmission': 'ra',
            'features.supportmessage': 'ra',
            'detection.farmerfeedback': 'ra',
            'detection.diagnosislog': 'r',
            'detection.detectionhistory': 'r',
            'detection.qualityrejectionlog': 'r',
            'accounts.userprofile': 'r',
        },
    },
    'Field Operations': {
        'description': 'Manages IoT hardware, thresholds and irrigation.',
        'perms': {
            'iot_sensor.field': 'rwad',
            'iot_sensor.sensornode': 'rwad',
            'iot_sensor.sensorthreshold': 'rwad',
            'iot_sensor.sensoralert': 'ra',
            'iot_sensor.irrigationcommand': 'rwa',
            'iot_sensor.sensorreading': 'r',
            'iot_sensor.fieldzone': 'rwad',
            'iot_sensor.systemmetricslog': 'r',
            'iot_sensor.croppredictionlog': 'r',
        },
    },
    'Marketplace Manager': {
        'description': 'Products and orders.',
        'perms': {
            'marketplace.product': 'rwad',
            'marketplace.productimage': 'rwad',
            'marketplace.category': 'rwad',
            'marketplace.order': 'ra',
            'marketplace.orderitem': 'ra',
            'marketplace.orderevent': 'rwa',
        },
    },
}

ACTION_FOR_FLAG = {'r': 'view', 'w': 'add', 'a': 'change', 'd': 'delete'}


class Command(BaseCommand):
    help = 'Create or update scoped admin roles (groups) for staff users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Clear each role\'s existing permissions before applying. Use '
                 'after removing a model from a role.',
        )
        parser.add_argument(
            '--list', action='store_true',
            help='Show the roles and what each can do, without changing anything.',
        )

    def handle(self, *args, **options):
        if options['list']:
            for role, spec in ROLES.items():
                self.stdout.write(self.style.MIGRATE_HEADING(f'\n{role}'))
                self.stdout.write(f'  {spec["description"]}')
                for target, flags in sorted(spec['perms'].items()):
                    actions = ', '.join(ACTION_FOR_FLAG[f] for f in flags)
                    self.stdout.write(f'    {target:<36} {actions}')
            return

        created_total = 0
        with transaction.atomic():
            for role, spec in ROLES.items():
                group, created = Group.objects.get_or_create(name=role)
                created_total += created
                if options['reset']:
                    group.permissions.clear()

                granted, skipped = 0, []
                for target, flags in spec['perms'].items():
                    app_label, model = target.split('.')
                    try:
                        ct = ContentType.objects.get(app_label=app_label, model=model)
                    except ContentType.DoesNotExist:
                        skipped.append(target)
                        continue
                    for flag in flags:
                        codename = f'{ACTION_FOR_FLAG[flag]}_{model}'
                        perm = Permission.objects.filter(
                            content_type=ct, codename=codename).first()
                        if perm is None:
                            skipped.append(f'{target}:{codename}')
                            continue
                        group.permissions.add(perm)
                        granted += 1

                label = 'created' if created else 'updated'
                self.stdout.write(self.style.SUCCESS(
                    f'{role}: {label}, {granted} permissions'))
                if skipped:
                    self.stdout.write(self.style.WARNING(
                        f'  skipped (model not found): {", ".join(skipped[:6])}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{len(ROLES)} roles ready ({created_total} new).'))
        self.stdout.write(
            'Assign one in admin: Users -> pick a user -> tick "Staff status", '
            'then add them to a group. Do NOT also tick "Superuser", which '
            'overrides every restriction above.'
        )
