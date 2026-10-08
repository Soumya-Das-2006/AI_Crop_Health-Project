"""
Sitemaps for search engines.

Only genuinely public, indexable pages belong here. Anything behind a login,
anything that triggers model inference, and the cart/checkout flow are excluded
(and also disallowed in robots.txt).
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Public pages that are not driven by a database row."""

    protocol = 'https'
    changefreq = 'monthly'

    # (url name, priority)
    pages = [
        ('index', 1.0),
        ('about', 0.7),
        ('contact:form', 0.6),
        ('contact:services', 0.6),
        ('contact:testimonials', 0.4),
        ('contact:biodegradable', 0.5),
        ('blog:list', 0.7),
        ('blog:faq', 0.5),
        ('features:marketprice', 0.7),
        ('features:cropinfo', 0.7),
        ('features:schemes_home', 0.7),
        ('features:weather_dashboard', 0.6),
        ('detection:diagnosis', 0.9),
        ('detection:crop_recommendation', 0.8),
        ('detection:fertilizer_recommendation', 0.8),
        ('marketplace:catalog', 0.6),
        ('core:privacy_policy', 0.3),
        ('core:terms_and_conditions', 0.3),
    ]

    def items(self):
        # Skip any entry whose URL cannot be reversed, so one renamed route
        # cannot take the whole sitemap down with a NoReverseMatch.
        resolved = []
        for name, priority in self.pages:
            try:
                reverse(name)
            except Exception:
                continue
            resolved.append((name, priority))
        return resolved

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class BlogPostSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        from blog.models import BlogPost

        return BlogPost.objects.filter(is_published=True).order_by('-updated_date')

    def lastmod(self, obj):
        return obj.updated_date

    def location(self, obj):
        return reverse('blog:detail', args=[obj.pk])


class CropInfoSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        from features.models import CropInfo

        return CropInfo.objects.all()

    def location(self, obj):
        return reverse('features:crop_detail', args=[obj.pk])


class SchemeSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        from features.models import GovernmentScheme

        return GovernmentScheme.objects.all()

    def location(self, obj):
        return reverse('features:scheme_detail', args=[obj.slug])


class ProductSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        from marketplace.models import Product

        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return getattr(obj, 'updated_at', None)

    def location(self, obj):
        return reverse('marketplace:product_detail', args=[obj.slug])


SITEMAPS = {
    'static': StaticViewSitemap,
    'blog': BlogPostSitemap,
    'crops': CropInfoSitemap,
    'schemes': SchemeSitemap,
    'products': ProductSitemap,
}
