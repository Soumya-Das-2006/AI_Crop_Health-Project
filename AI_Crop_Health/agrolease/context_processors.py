from .models import AgroProfile, Land, LeaseRequest


def admin_summary(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    return {
        'agrolease_admin_summary': {
            # Counted every unverified owner, including those who never started.
            # The review queue is specifically profiles awaiting a decision, and
            # farmers are reviewed now too, not just owners.
            'owner_verification': AgroProfile.objects.filter(
                role='owner', verification_status='pending',
            ).count(),
            'farmer_verification': AgroProfile.objects.filter(
                role='farmer', verification_status='pending',
            ).count(),
            'pending_verification': AgroProfile.objects.filter(
                verification_status='pending',
            ).count(),
            'pending_land': Land.objects.filter(status='pending_approval').count(),
            'available_land': Land.objects.filter(status='available').count(),
            'pending_requests': LeaseRequest.objects.filter(status='pending').count(),
            'total_land': Land.objects.count(),
            'total_profiles': AgroProfile.objects.count(),
        }
    }
