from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import AgroProfile, Land, LeaseRequest, LeaseAgreement

def role_selection(request):
    # Point #2: If authenticated, redirect to dashboard. Else, redirect to login.
    if request.user.is_authenticated:
        profile = getattr(request.user, 'agroprofile', None)
        if profile:
            if profile.role == 'owner':
                return redirect('agrolease:owner_dashboard')
            elif profile.role == 'farmer':
                return redirect('agrolease:farmer_dashboard')
            elif profile.role == 'admin':
                return redirect('agrolease:admin_dashboard')
    return redirect('agrolease:login')

def logout_view(request):
    logout(request)
    return redirect('agrolease:login')

def login_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        try:
            profile = AgroProfile.objects.get(phone_number=phone)
            user = profile.user
            # In a real app we'd verify OTP. For now, just log them in to test.
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('agrolease:role_selection')
        except AgroProfile.DoesNotExist:
            messages.error(request, 'Phone number not registered. Please register first.')
            return redirect('agrolease:login')
    return render(request, 'agrolease/login.html')

def otp_view(request):
    # Deprecated for now, logic handled in login_view directly for simplicity in testing
    return redirect('agrolease:login')

def register_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        phone = request.POST.get('phone')
        role = request.POST.get('role', 'farmer')
        
        if User.objects.filter(username=phone).exists():
            messages.error(request, 'Phone number already registered.')
            return redirect('agrolease:register')
            
        user = User.objects.create_user(username=phone, first_name=name)
        AgroProfile.objects.create(user=user, phone_number=phone, role=role)
        
        messages.success(request, 'Registration successful! Please login.')
        return redirect('agrolease:login')
    return render(request, 'agrolease/register.html')

@login_required
def owner_dashboard(request):
    profile = request.user.agroprofile
    if profile.role != 'owner':
        return redirect('agrolease:role_selection')

    lands = Land.objects.filter(owner=request.user)
    # Point #3: Monthly Revenue sum
    leased_lands = lands.filter(status='leased')
    monthly_revenue = leased_lands.aggregate(Sum('rent_amount'))['rent_amount__sum'] or 0

    requests = LeaseRequest.objects.filter(land__owner=request.user)
    pending_requests = requests.filter(status='pending').count()

    context = {
        'lands': lands,
        'requests': requests,
        'total_lands': lands.count(),
        'monthly_revenue': monthly_revenue,
        'pending_requests': pending_requests
    }
    return render(request, 'agrolease/owner_dashboard.html', context)

@login_required
def add_land(request):
    if request.method == 'POST':
        Land.objects.create(
            owner=request.user,
            location=request.POST.get('location'),
            size_acres=request.POST.get('size'),
            soil_type=request.POST.get('soil_type'),
            water_source=request.POST.get('water_source'),
            suitable_crops=request.POST.get('suitable_crops'),
            rent_amount=request.POST.get('rent'),
            duration_months=request.POST.get('duration', 12)
        )
        # Point #5: Flash message
        messages.success(request, 'Land submitted for approval successfully!')
        return redirect('agrolease:owner_dashboard')
    return render(request, 'agrolease/add_land.html')

@login_required
def owner_requests(request):
    requests = LeaseRequest.objects.filter(land__owner=request.user)
    return render(request, 'agrolease/owner_requests.html', {'requests': requests})

@login_required
def farmer_dashboard(request):
    profile = getattr(request.user, 'agroprofile', None)
    if not profile or profile.role != 'farmer':
        return redirect('agrolease:role_selection')

    farmer_requests = LeaseRequest.objects.filter(farmer=request.user)
    active_leases = farmer_requests.filter(status='approved')

    context = {
        'farmer_requests': farmer_requests, # Point #4: Renamed from 'requests' to avoid shadowing
        'active_leases': active_leases,
        'total_requests': farmer_requests.count(),
        'active_count': active_leases.count()
    }
    return render(request, 'agrolease/farmer_dashboard.html', context)

@login_required
def search_land(request):
    lands = Land.objects.filter(status='available')
    
    location = request.GET.get('location', '')
    soil_type = request.GET.get('soil_type', '')
    
    if location:
        lands = lands.filter(location__icontains=location)
    if soil_type:
        lands = lands.filter(soil_type__icontains=soil_type)

    context = {
        'lands': lands,
        'filters': {'location': location, 'soil_type': soil_type}
    }
    return render(request, 'agrolease/search_land.html', context)

@login_required
def request_lease(request, land_id):
    land = get_object_or_404(Land, id=land_id)
    if request.method == 'POST':
        # Point #8: create or update instead of crash, or just create since we removed unique_together
        LeaseRequest.objects.create(
            land=land,
            farmer=request.user,
            message=request.POST.get('message', '')
        )
        messages.success(request, 'Lease request sent successfully!')
        return redirect('agrolease:farmer_dashboard')
    return render(request, 'agrolease/request_lease.html', {'land': land})

@login_required
def admin_dashboard(request):
    profile = getattr(request.user, 'agroprofile', None)
    if not profile or profile.role != 'admin':
        return redirect('agrolease:role_selection')

    context = {
        'pending_verifications': AgroProfile.objects.filter(is_verified=False).count(),
        'pending_approvals': Land.objects.filter(status='pending_approval').count(),
        'total_users': User.objects.count(),
        'active_leases': Land.objects.filter(status='leased').count()
    }
    return render(request, 'agrolease/admin_dashboard.html', context)

@login_required
def admin_verifications(request):
    verifications = AgroProfile.objects.filter(is_verified=False)
    return render(request, 'agrolease/admin_verifications.html', {'verifications': verifications})

@login_required
def admin_approvals(request):
    approvals = Land.objects.filter(status='pending_approval')
    return render(request, 'agrolease/admin_approvals.html', {'approvals': approvals})

@login_required
def agreement_preview(request, request_id):
    lease_req = get_object_or_404(LeaseRequest, id=request_id)
    return render(request, 'agrolease/agreement_preview.html', {'req': lease_req, 'land': lease_req.land})
