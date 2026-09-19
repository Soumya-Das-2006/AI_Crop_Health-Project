from django.test import TestCase
from django.urls import reverse
from .models import Category, Product, Order, OrderItem
from django.contrib.auth import get_user_model

User = get_user_model()

class MarketplaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpassword')
        cls.category, _ = Category.objects.get_or_create(name='Seeds', slug='seeds')
        cls.product = Product.objects.create(
            category=cls.category,
            name='Tomato Seeds',
            description='High yield tomato seeds.',
            price=100.00,
            mrp=150.00,
            stock=10
        )
        
    def test_catalog_view(self):
        response = self.client.get(reverse('marketplace:catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tomato Seeds')
        
    def test_product_detail_view(self):
        response = self.client.get(reverse('marketplace:product_detail', args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tomato Seeds')
        
    def test_add_to_cart(self):
        response = self.client.post(reverse('marketplace:add_to_cart', args=[self.product.slug]), {'quantity': 2})
        self.assertRedirects(response, reverse('marketplace:cart'))
        self.assertEqual(self.client.session.get('marketplace_cart'), {self.product.slug: 2})
        
    def test_checkout_requires_login(self):
        response = self.client.get(reverse('marketplace:checkout'))
        self.assertRedirects(response, '/agrolease/login/?next=' + reverse('marketplace:checkout'))
        
    def test_checkout_post(self):
        self.client.login(username='testuser', password='testpassword')
        session = self.client.session
        session['marketplace_cart'] = {self.product.slug: 2}
        session.save()
        
        data = {
            'full_name': 'John Doe',
            'phone': '1234567890',
            'address': '123 Farm Lane',
            'city': 'Farmville',
            'state': 'AgriState',
            'pincode': '123456',
            'payment_method': 'COD'
        }
        response = self.client.post(reverse('marketplace:checkout'), data)
        
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.customer_name, 'John Doe')
        self.assertRedirects(response, reverse('marketplace:order_detail', args=[order.pk]))
        
        # Check stock deduction
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        
        # Check cart cleared
        self.assertEqual(self.client.session.get('marketplace_cart'), {})
