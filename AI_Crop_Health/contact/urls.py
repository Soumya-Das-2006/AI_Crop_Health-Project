from django.urls import path
from . import views

app_name = 'contact'

urlpatterns = [
    path('', views.contact_form, name='form'),
    path('services/', views.services, name='services'),
    path('testimonials/', views.testimonials, name='testimonials'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('biodegradable/', views.biodegradable, name='biodegradable'),
    path('submit-waste/', views.submit_waste, name='submit_waste'),
    path('api/send-company-email/', views.send_company_email, name='send_company_email'),
]
