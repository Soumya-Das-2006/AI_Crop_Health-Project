from django.core.management.base import BaseCommand
from marketplace.models import Category, Product


PRODUCTS = [
    ('High-yield Paddy Seeds', 'seeds', 'Certified rice seeds selected for reliable germination and strong field performance.', 480, '5 kg pack', 40, True),
    ('Vegetable Starter Plants', 'plants', 'Healthy seasonal vegetable seedlings ready for transplanting into prepared beds.', 35, 'plant', 200, True),
    ('Neem-based Crop Protectant', 'medicine', 'A botanical crop-care solution for integrated pest management.', 320, '1 litre', 60, False),
    ('Organic Growth Fertilizer', 'fertilizer', 'Balanced organic nutrition to support soil health and steady crop growth.', 650, '25 kg bag', 35, True),
    ('Manual Seed Planter', 'equipment', 'A durable hand-operated planter for accurate small-farm sowing.', 1850, 'piece', 18, False),
    ('Trichoderma Bio Culture', 'bio-products', 'Beneficial microbial culture for healthier soil and stronger root development.', 210, '1 kg pack', 75, False),
]


class Command(BaseCommand):
    help = 'Create the starter marketplace catalogue without duplicating existing products.'

    def handle(self, *args, **options):
        categories = {}
        for order, (name, slug) in enumerate((
            ('Seeds', 'seeds'), ('Plants', 'plants'), ('Medicine', 'medicine'),
            ('Fertilizer', 'fertilizer'), ('Equipment', 'equipment'), ('Bio Products', 'bio-products'),
        )):
            categories[slug], _ = Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'display_order': order}
            )
        created = 0
        for name, category, description, price, unit, stock, featured in PRODUCTS:
            product, was_created = Product.objects.get_or_create(
                name=name,
                defaults={
                    'category': categories[category],
                    'description': description,
                    'price': price,
                    'unit': unit,
                    'stock': stock,
                    'is_featured': featured,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Marketplace ready with {created} new starter products.'))
