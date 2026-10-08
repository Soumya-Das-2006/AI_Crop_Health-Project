from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import SITEMAPS

app_name = 'core'

urlpatterns = [
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    # django.contrib.sitemaps internally reverses
    # 'django.contrib.sitemaps.views.sitemap' when paginating, so that exact
    # name must exist. 'core:sitemap' is our own readable alias, used by
    # robots.txt to emit an absolute Sitemap: line for whatever host is serving.
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('sitemap-<section>.xml', sitemap, {'sitemaps': SITEMAPS},
         name='django.contrib.sitemaps.views.sitemap'),
]
