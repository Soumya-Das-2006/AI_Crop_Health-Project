from .models import AgroProfile, Land, LeaseRequest


def admin_summary(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    return {
        'agrolease_admin_summary': {
            'owner_verification': AgroProfile.objects.filter(role='owner', is_verified=False).count(),
            'pending_land': Land.objects.filter(status='pending_approval').count(),
            'available_land': Land.objects.filter(status='available').count(),
            'pending_requests': LeaseRequest.objects.filter(status='pending').count(),
            'total_land': Land.objects.count(),
            'total_profiles': AgroProfile.objects.count(),
        }
    }
