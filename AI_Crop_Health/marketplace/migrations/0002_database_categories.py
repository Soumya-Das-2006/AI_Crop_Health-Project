from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


CATEGORY_DATA = [
    ('Seeds', 'seeds'),
    ('Plants', 'plants'),
    ('Medicine', 'medicine'),
    ('Fertilizer', 'fertilizer'),
    ('Equipment', 'equipment'),
    ('Bio Products', 'bio-products'),
]


def create_categories(apps, schema_editor):
    Category = apps.get_model('marketplace', 'Category')
    Product = apps.get_model('marketplace', 'Product')
    categories = {}
    for order, (name, slug) in enumerate(CATEGORY_DATA):
        categories[slug] = Category.objects.create(name=name, slug=slug, display_order=order)
    for product in Product.objects.all():
        category = categories.get(product.category)
        if category:
            product.category_ref_id = category.pk
            product.save(update_fields=['category_ref'])


class Migration(migrations.Migration):
    dependencies = [('marketplace', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(unique=True)),
                ('description', models.CharField(blank=True, max_length=240)),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
            ],
            options={'ordering': ('display_order', 'name')},
        ),
        migrations.AddField(
            model_name='product',
            name='category_ref',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='legacy_products', to='marketplace.category'),
        ),
        migrations.RunPython(create_categories, migrations.RunPython.noop),
        migrations.RemoveField(model_name='product', name='category'),
        migrations.RenameField(model_name='product', old_name='category_ref', new_name='category'),
        migrations.AlterField(
            model_name='product',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='products', to='marketplace.category'),
        ),
    ]
