from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agrolease', '0003_agroprofile_roles'),
        migrations.swappable_dependency('auth.User'),
    ]

    operations = [
        migrations.AddField(model_name='agroprofile', name='government_id_type', field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name='agroprofile', name='government_id_document', field=models.FileField(blank=True, null=True, upload_to='verification/government_id/')),
        migrations.AddField(model_name='agroprofile', name='ownership_proof', field=models.FileField(blank=True, null=True, upload_to='verification/ownership/')),
        migrations.AddField(model_name='agroprofile', name='address_proof', field=models.FileField(blank=True, null=True, upload_to='verification/address/')),
        migrations.AddField(model_name='agroprofile', name='selfie_photo', field=models.ImageField(blank=True, null=True, upload_to='verification/selfies/')),
        migrations.AddField(model_name='agroprofile', name='verification_submitted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='agroprofile', name='verified_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='agroprofile', name='verified_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_agro_profiles', to='auth.user')),
    ]