from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.global_login, name='login'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_edit, name='profile_edit'),
    path('', views.account_dashboard, name='dashboard'),
]
