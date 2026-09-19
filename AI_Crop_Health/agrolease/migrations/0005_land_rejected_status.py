from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agrolease', '0004_agroprofile_verification_documents'),
    ]

    operations = [
        migrations.AlterField(
            model_name='land',
            name='status',
            field=models.CharField(choices=[('available', 'Available'), ('pending_approval', 'Pending Admin Approval'), ('rejected', 'Rejected'), ('leased', 'Leased')], default='pending_approval', max_length=20),
        ),
    ]