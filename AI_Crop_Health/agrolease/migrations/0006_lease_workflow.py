from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agrolease', '0005_land_rejected_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leaserequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('owner_approved', 'Owner Approved - Admin Review'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                    ('completed', 'Completed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='LeaseMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lease_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='agrolease.leaserequest')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lease_messages', to='auth.user')),
            ],
            options={'ordering': ('created_at',)},
        ),
    ]