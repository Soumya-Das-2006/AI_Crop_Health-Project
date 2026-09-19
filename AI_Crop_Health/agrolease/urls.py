from django.urls import path
from . import views

app_name = 'agrolease'

urlpatterns = [
    # Role selection
    path('', views.role_selection, name='role_selection'),

    # Auth (UI only)
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('otp/', views.otp_view, name='otp'),
    path('register/', views.register_view, name='register'),

    # Owner dashboard
    path('owner/dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/profile/', views.owner_profile, name='owner_profile'),
    path('owner/add-land/', views.add_land, name='add_land'),
    path('owner/requests/', views.owner_requests, name='owner_requests'),
    path('owner/requests/<int:request_id>/', views.owner_request_detail, name='owner_request_detail'),
    path('owner/requests/<int:request_id>/approve/', views.approve_lease_request, name='approve_lease_request'),
    path('owner/requests/<int:request_id>/reject/', views.reject_lease_request, name='reject_lease_request'),
    path('lease/<int:request_id>/chat/', views.lease_chat, name='lease_chat'),

    # Farmer dashboard
    path('farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),
    path('farmer/search/', views.search_land, name='search_land'),
    path('farmer/request/<int:land_id>/', views.request_lease, name='request_lease'),

    # Admin dashboard
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/verifications/', views.admin_verifications, name='admin_verifications'),
    path('admin/approvals/', views.admin_approvals, name='admin_approvals'),

    # Agreement preview
    path('agreement/<int:request_id>/', views.agreement_preview, name='agreement_preview'),
    path('agreement/<int:request_id>/<str:action>/', views.agreement_action, name='agreement_action'),
]
