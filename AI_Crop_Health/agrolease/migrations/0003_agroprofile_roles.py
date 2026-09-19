from django.db import migrations, models


def copy_current_role_to_roles(apps, schema_editor):
    AgroProfile = apps.get_model('agrolease', 'AgroProfile')
    for profile in AgroProfile.objects.all():
        profile.roles = [profile.role]
        profile.save(update_fields=['roles'])


class Migration(migrations.Migration):

    dependencies = [
        ('agrolease', '0002_land_coordinates'),
    ]

    operations = [
        migrations.AddField(
            model_name='agroprofile',
            name='roles',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(copy_current_role_to_roles, migrations.RunPython.noop),
    ]