from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum
from django.utils import timezone
import re
import logging
import secrets
from math import asin, cos, radians, sin, sqrt
from difflib import SequenceMatcher
from .models import AgroProfile, Land, LeaseRequest, LeaseAgreement, LeaseMessage
from .geocoding import geocode_location

logger = logging.getLogger(__name__)
OTP_SESSION_KEY = 'agrolease_otp'
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5

def normalize_phone(phone):
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in '6789':
        return None
    return digits

def profile_roles(profile):
    roles = list(profile.roles or [])
    if profile.role not in roles:
        roles.append(profile.role)
    return [role for role in roles if role in {'owner', 'farmer'}]

def role_selection(request):
    if request.method == 'POST' and request.user.is_authenticated:
        profile = getattr(request.user, 'agroprofile', None)
        selected_role = request.POST.get('role')
        available_roles = profile_roles(profile) if profile else []
        if profile and selected_role in available_roles:
            profile.role = selected_role
            profile.roles = available_roles
            profile.save(update_fields=['role', 'roles'])
            return redirect({
                'owner': 'agrolease:owner_dashboard',
                'farmer': 'agrolease:farmer_dashboard',
            }[selected_role])
            messages.error(request, 'Choose a role registered on this account.')
            return render(request, 'agrolease/role_selection.html', {'available_roles': available_roles})

    # Redirect authenticated users to their current workspace.
    if request.user.is_authenticated and request.GET.get('switch') != '1':
        profile = getattr(request.user, 'agroprofile', None)
        if profile:
            if profile.role == 'owner':
                return redirect('agrolease:owner_dashboard')
            elif profile.role == 'farmer':
                return redirect('agrolease:farmer_dashboard')
            elif profile.role == 'admin':
                return redirect('/admin/')
    if request.user.is_authenticated and request.GET.get('switch') == '1':
        profile = getattr(request.user, 'agroprofile', None)
        if profile and profile.role == 'admin':
            return redirect('/admin/')
        return render(request, 'agrolease/role_selection.html', {'available_roles': profile_roles(profile) if profile else []})
    return redirect('agrolease:login')

def logout_view(request):
    return redirect('accounts:logout')

def login_view(request):
    return redirect('accounts:login')

def otp_view(request):
    return redirect('accounts:login')

def register_view(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please register your global account first, then you can join AgroLease.')
        return redirect('accounts:register')
        
    if request.method == 'POST':
        role = request.POST.get('role', 'farmer')
        
        if role not in {'owner', 'farmer'}:
            messages.error(request, 'Select either Land Owner or Farmer.')
            return render(request, 'agrolease/register.html')
            
        profile, created = AgroProfile.objects.get_or_create(
            user=request.user,
            defaults={'phone_number': request.user.global_profile.phone_number, 'role': role, 'roles': [role]}
        )
        
        if not created:
            if role in profile_roles(profile):
                messages.error(request, 'You already have this role.')
                return redirect('agrolease:role_selection')
                
        if role == 'owner':
            if not all((
                request.POST.get('government_id_type'),
                request.FILES.get('government_id_document'),
                request.FILES.get('ownership_proof'),
                request.FILES.get('address_proof'),
            )):
                messages.error(request, 'Owners must submit ID type, government ID, ownership proof, and address proof.')
                return render(request, 'agrolease/register.html')
            
            if not created:
                profile.roles = profile_roles(profile) + [role]
                
            profile.government_id_type = request.POST.get('government_id_type', '')
            profile.government_id_document = request.FILES.get('government_id_document')
            profile.ownership_proof = request.FILES.get('ownership_proof')
            profile.address_proof = request.FILES.get('address_proof')
            profile.selfie_photo = request.FILES.get('selfie_photo')
            profile.verification_submitted_at = timezone.now()
            profile.is_verified = False
            profile.save()
            messages.success(request, 'Role added to your account. Your owner profile is waiting for verification.')
        else:
            if not created:
                profile.roles = profile_roles(profile) + [role]
                profile.save(update_fields=['roles'])
            messages.success(request, 'Farmer role added successfully.')
            
        return redirect('agrolease:role_selection')
        
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
    active_leases = leased_lands.count()

    context = {
        'lands': lands,
        'requests': requests,
        'total_lands': lands.count(),
        'active_leases': active_leases,
        'monthly_revenue': monthly_revenue,
        'pending_requests': pending_requests
    }
    return render(request, 'agrolease/owner_dashboard.html', context)

@login_required
def owner_profile(request):
    profile = getattr(request.user, 'agroprofile', None)
    if not profile or profile.role != 'owner':
        return redirect('agrolease:role_selection')
    return render(request, 'agrolease/owner_profile.html', {'profile': profile})

@login_required
def add_land(request):
    profile = getattr(request.user, 'agroprofile', None)
    if not profile or profile.role != 'owner':
        return redirect('agrolease:role_selection')
    if not profile.is_verified:
        messages.warning(request, 'Your owner profile must be verified by an administrator before adding land.')
        return redirect('agrolease:owner_profile')
    if request.method == 'POST':
        Land.objects.create(
            owner=request.user,
            location=request.POST.get('location'),
            size_acres=request.POST.get('size'),
            soil_type=request.POST.get('soil_type'),
            water_source=request.POST.get('water_source'),
            suitable_crops=request.POST.get('suitable_crops'),
            rent_amount=request.POST.get('rent_amount'),
            rent_frequency=f"per {request.POST.get('rent_period', 'season')}",
            duration_months=request.POST.get('duration', 12),
            image=request.FILES.get('images'),
            **dict(zip(('latitude', 'longitude'), geocode_location(request.POST.get('location')) or (None, None)))
        )
        # Point #5: Flash message
        messages.success(request, 'Land submitted for approval successfully!')
        return redirect('agrolease:owner_dashboard')
    return render(request, 'agrolease/add_land.html')

@login_required
def owner_requests(request):
    requests = LeaseRequest.objects.filter(land__owner=request.user).select_related('land', 'farmer', 'farmer__agroprofile')
    return render(request, 'agrolease/owner_requests.html', {'requests': requests})

@login_required
def owner_request_detail(request, request_id):
    lease_request = get_object_or_404(
        LeaseRequest.objects.select_related('land', 'farmer', 'farmer__agroprofile'),
        id=request_id,
        land__owner=request.user,
    )
    return render(request, 'agrolease/owner_request_detail.html', {
        'lease_request': lease_request,
        'chat_messages': lease_request.messages.select_related('sender'),
    })

@login_required
def lease_chat(request, request_id):
    lease_request = get_object_or_404(
        LeaseRequest.objects.select_related('land', 'land__owner', 'farmer'),
        id=request_id,
    )
    if request.user not in (lease_request.farmer, lease_request.land.owner):
        return redirect('agrolease:role_selection')
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            LeaseMessage.objects.create(lease_request=lease_request, sender=request.user, body=body)
        return redirect('agrolease:lease_chat', request_id=request_id)
    return render(request, 'agrolease/lease_chat.html', {
        'lease_request': lease_request,
        'chat_messages': lease_request.messages.select_related('sender'),
        'is_owner': request.user == lease_request.land.owner,
        'counterparty': lease_request.farmer if request.user == lease_request.land.owner else lease_request.land.owner,
    })

@login_required
def approve_lease_request(request, request_id):
    if request.method != 'POST':
        return redirect('agrolease:owner_request_detail', request_id=request_id)

    lease_request = get_object_or_404(
        LeaseRequest.objects.select_related('land'),
        id=request_id,
        land__owner=request.user,
    )
    if lease_request.status != 'pending':
        messages.info(request, 'This lease request has already been reviewed.')
    elif lease_request.land.status != 'available':
        messages.error(request, 'This land is no longer available for lease.')
    else:
        lease_request.status = 'owner_approved'
        lease_request.save(update_fields=('status',))
        LeaseRequest.objects.filter(
            land=lease_request.land,
            status='pending',
        ).exclude(id=lease_request.id).update(status='rejected')
        messages.success(request, 'Request approved by you and sent to AgroLease admin for final review.')
    return redirect('agrolease:owner_request_detail', request_id=request_id)

@login_required
def reject_lease_request(request, request_id):
    if request.method != 'POST':
        return redirect('agrolease:owner_request_detail', request_id=request_id)

    lease_request = get_object_or_404(
        LeaseRequest,
        id=request_id,
        land__owner=request.user,
    )
    if lease_request.status == 'pending':
        lease_request.status = 'rejected'
        lease_request.save(update_fields=('status',))
        messages.success(request, 'Farmer request rejected.')
    else:
        messages.info(request, 'This lease request has already been reviewed.')
    return redirect('agrolease:owner_request_detail', request_id=request_id)

@login_required
def farmer_dashboard(request):
    profile = getattr(request.user, 'agroprofile', None)
    if not profile or profile.role != 'farmer':
        return redirect('agrolease:role_selection')

    farmer_requests = LeaseRequest.objects.filter(farmer=request.user)
    active_leases = farmer_requests.filter(status='approved')
    pending_requests = farmer_requests.filter(status='pending')

    context = {
        'farmer_requests': farmer_requests, # Point #4: Renamed from 'requests' to avoid shadowing
        'active_leases': active_leases,
        'total_requests': farmer_requests.count(),
        'active_count': active_leases.count(),
        'pending_count': pending_requests.count()
    }
    return render(request, 'agrolease/farmer_dashboard.html', context)

@login_required
def search_land(request):
    lands_query = Land.objects.filter(status='available')
    location = request.GET.get('location', '').strip()
    soil_type = request.GET.get('soil_type', '').strip()
    rent_range = request.GET.get('rent_range', '').strip()

    if soil_type:
        lands_query = lands_query.filter(soil_type__icontains=soil_type)
    if rent_range == 'under_20000':
        lands_query = lands_query.filter(rent_amount__lt=20000)
    elif rent_range == '20000_40000':
        lands_query = lands_query.filter(rent_amount__gte=20000, rent_amount__lte=40000)
    elif rent_range == 'above_40000':
        lands_query = lands_query.filter(rent_amount__gt=40000)

    def location_score(value):
        query_text = re.sub(r'[^a-z0-9 ]', ' ', location.lower()).strip()
        value_text = re.sub(r'[^a-z0-9 ]', ' ', value.lower()).strip()
        if not query_text:
            return 1
        if query_text == value_text:
            return 1
        if query_text in value_text:
            return .95
        query_tokens = query_text.split()
        value_tokens = value_text.split()
        token_score = max((SequenceMatcher(None, token, candidate).ratio()
                           for token in query_tokens for candidate in value_tokens), default=0)
        return max(SequenceMatcher(None, query_text, value_text).ratio(), token_score)

    search_coordinates = geocode_location(location) if location else None
    lands = []

    def distance_km(latitude, longitude):
        if not search_coordinates or latitude is None or longitude is None:
            return None
        earth_radius_km = 6371
        search_lat, search_lon = map(radians, search_coordinates)
        land_lat, land_lon = radians(float(latitude)), radians(float(longitude))
        delta_lat = land_lat - search_lat
        delta_lon = land_lon - search_lon
        haversine = sin(delta_lat / 2) ** 2 + cos(search_lat) * cos(land_lat) * sin(delta_lon / 2) ** 2
        return earth_radius_km * 2 * asin(sqrt(haversine))

    for land in lands_query:
        score = location_score(land.location)
        if not location or score >= .55:
            land.location_match_score = score
            land.distance_km = distance_km(land.latitude, land.longitude)
            lands.append(land)
    if search_coordinates:
        lands.sort(key=lambda land: (land.distance_km is None, land.distance_km or float('inf'), -land.location_match_score))
    else:
        lands.sort(key=lambda land: (-land.location_match_score, land.location.lower()))

    search_note = ''
    if location and lands:
        exact_match = any(land.location_match_score >= .95 for land in lands)
        if search_coordinates:
            search_note = f'Showing available land nearest to “{location}”, with text matches used as a fallback.'
        elif not exact_match:
            search_note = f'Showing the closest location matches for “{location}”.'
    elif location:
        search_note = f'No available land matched “{location}”. Try a nearby city, district, or state.'

    context = {
        'lands': lands,
        'filters': {'location': location, 'soil_type': soil_type, 'rent_range': rent_range},
        'search_note': search_note
    }
    return render(request, 'agrolease/search_land.html', context)

@login_required
def request_lease(request, land_id):
    land = get_object_or_404(Land, id=land_id)
    if request.method == 'POST':
        form_data = request.POST
        phone = normalize_phone(form_data.get('contact_number'))
        errors = []
        if land.status != 'available':
            errors.append('This land is not currently available for lease requests.')
        if not form_data.get('terms_agreed'):
            errors.append('You must agree to the AgroLease terms and conditions.')
        if not form_data.get('farmer_name', '').strip():
            errors.append('Enter your full name.')
        if not phone:
            errors.append('Enter a valid 10-digit contact number.')
        if not form_data.get('farming_experience'):
            errors.append('Select your farming experience.')
        if not form_data.get('intended_crops', '').strip():
            errors.append('Enter the crops you intend to grow.')
        if not form_data.get('message', '').strip():
            errors.append('Add a message for the land owner.')
        if LeaseRequest.objects.filter(land=land, farmer=request.user, status='pending').exists():
            errors.append('You already have a pending request for this land.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'agrolease/request_lease.html', {'land': land, 'form_data': form_data})

        request_message = '\n'.join([
            f"Applicant: {form_data.get('farmer_name').strip()}",
            f"Contact: +91 {phone}",
            f"Farming experience: {form_data.get('farming_experience')}",
            f"Intended crops: {form_data.get('intended_crops').strip()}",
            f"Requested duration: {form_data.get('lease_duration', 'season')}",
            f"Message: {form_data.get('message').strip()}",
        ])
        LeaseRequest.objects.create(
            land=land,
            farmer=request.user,
            message=request_message,
        )
        messages.success(request, 'Lease request sent successfully!')
        return redirect('agrolease:farmer_dashboard')
    return render(request, 'agrolease/request_lease.html', {'land': land})

@login_required
def admin_dashboard(request):
    return redirect('/admin/')

@login_required
def admin_verifications(request):
    return redirect('/admin/agrolease/agroprofile/?role__exact=owner&is_verified__exact=0')

@login_required
def admin_approvals(request):
    return redirect('/admin/agrolease/land/?status__exact=pending_approval')

@login_required
def agreement_preview(request, request_id):
    lease_req = get_object_or_404(
        LeaseRequest.objects.select_related('land', 'land__owner', 'farmer'),
        id=request_id,
        status__in=('approved', 'completed'),
    )
    if request.user not in (lease_req.farmer, lease_req.land.owner):
        return redirect('agrolease:role_selection')
    duration_label = f"{lease_req.land.duration_months} month" if lease_req.land.duration_months == 1 else f"{lease_req.land.duration_months} months"
    terms_text = (
        f'Lease of {lease_req.land.location} to '
        f'{lease_req.farmer.get_full_name() or lease_req.farmer.username} '
        f'for {duration_label} at '
        f'₹{lease_req.land.rent_amount} {lease_req.land.rent_frequency}.'
    )
    agreement, created = LeaseAgreement.objects.get_or_create(
        lease_request=lease_req,
        defaults={
            'terms_text': terms_text,
        },
    )
    if agreement.terms_text != terms_text:
        agreement.terms_text = terms_text
        agreement.save(update_fields=('terms_text',))
    return render(request, 'agrolease/agreement_preview.html', {
        'req': lease_req,
        'land': lease_req.land,
        'agreement': agreement,
    })

@login_required
def agreement_action(request, request_id, action):
    if request.method != 'POST' or action not in {'accept', 'decline'}:
        return redirect('agrolease:agreement_preview', request_id=request_id)
    lease_req = get_object_or_404(
        LeaseRequest.objects.select_related('land'),
        id=request_id,
        status__in=('approved', 'completed'),
    )
    if request.user != lease_req.farmer:
        messages.error(request, 'Only the farmer can respond to this agreement.')
        return redirect('agrolease:agreement_preview', request_id=request_id)
    agreement = get_object_or_404(LeaseAgreement, lease_request=lease_req)
    if agreement.signed_by_farmer:
        return redirect('agrolease:farmer_dashboard')
    if action == 'accept':
        agreement.signed_by_farmer = True
        agreement.save(update_fields=('signed_by_farmer',))
        messages.success(request, 'Agreement accepted successfully.')
    else:
        lease_req.status = 'rejected'
        lease_req.save(update_fields=('status',))
        lease_req.land.status = 'available'
        lease_req.land.save(update_fields=('status', 'updated_at'))
        messages.info(request, 'Agreement declined. The land is available again.')
    return redirect('agrolease:farmer_dashboard')
