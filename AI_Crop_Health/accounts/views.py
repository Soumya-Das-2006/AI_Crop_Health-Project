import re
import secrets
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from .models import UserProfile

logger = logging.getLogger(__name__)

OTP_SESSION_KEY = 'global_auth_otp'
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5

def normalize_phone(phone):
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in '6789':
        return None
    return digits

def is_valid_email(email):
    return '@' in email and '.' in email.split('@')[-1]

def send_otp_email(email, otp_code):
    try:
        send_mail(
            'Your Login OTP - AI Crop Health Platform',
            f'Your One Time Password (OTP) is: {otp_code}\n\nIt expires in 5 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {e}")
        return False

def global_login(request):
    next_url = request.GET.get('next', '') or request.POST.get('next', '')
    
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        if not identifier:
            messages.error(request, 'Please enter your mobile number or email.')
            return render(request, 'accounts/login.html', {'next': next_url})
        
        user = None
        method = 'email' if '@' in identifier else 'mobile'
        
        if method == 'email':
            if not is_valid_email(identifier):
                messages.error(request, 'Please enter a valid email address.')
                return render(request, 'accounts/login.html', {'next': next_url})
            user = User.objects.filter(email=identifier).first()
        else:
            normalized_phone = normalize_phone(identifier)
            if not normalized_phone:
                messages.error(request, 'Please enter a valid 10-digit mobile number.')
                return render(request, 'accounts/login.html', {'next': next_url})
            user = User.objects.filter(global_profile__phone_number=normalized_phone).first()
            identifier = normalized_phone

        if not user:
            messages.error(request, 'Account not found. Please register first.')
            return redirect('accounts:register')
            
        otp_code = f'{secrets.randbelow(900000) + 100000}'
        expires_at = timezone.now().timestamp() + OTP_TTL_SECONDS
        
        request.session[OTP_SESSION_KEY] = {
            'identifier': identifier,
            'method': method,
            'code': otp_code,
            'expires_at': expires_at,
            'attempts': 0,
            'next': next_url,
        }
        request.session.modified = True
        
        context = {
            'otp_sent': True,
            'identifier': identifier,
            'method': method,
            'next': next_url,
        }
        
        if method == 'email':
            success = send_otp_email(user.email, otp_code)
            if success:
                messages.success(request, f'OTP sent to {user.email}')
            else:
                messages.error(request, 'Failed to send email. Please contact support or use mobile login.')
                if settings.DEBUG:
                    context['development_otp'] = otp_code
        else:
            # Mobile OTP (Simulated/Console)
            logger.info(f'Mobile OTP generated for {identifier}: {otp_code}')
            if settings.DEBUG:
                context['development_otp'] = otp_code
                messages.info(request, 'Development mode: use the OTP shown below.')
            else:
                messages.info(request, 'SMS delivery is not configured. Contact the administrator.')
                
        return render(request, 'accounts/login.html', context)
        
    return render(request, 'accounts/login.html', {'next': next_url})

def verify_otp(request):
    payload = request.session.get(OTP_SESSION_KEY)
    if request.method != 'POST' or not payload:
        return redirect('accounts:login')

    context = {
        'otp_sent': True,
        'identifier': payload.get('identifier'),
        'method': payload.get('method'),
        'next': payload.get('next', ''),
    }
    if settings.DEBUG:
        context['development_otp'] = payload.get('code')

    if payload.get('attempts', 0) >= OTP_MAX_ATTEMPTS:
        request.session.pop(OTP_SESSION_KEY, None)
        messages.error(request, 'Too many incorrect OTP attempts. Request a new OTP.')
        return redirect('accounts:login')

    entered_otp = re.sub(r'\D', '', request.POST.get('otp', ''))
    if timezone.now().timestamp() > payload.get('expires_at', 0):
        request.session.pop(OTP_SESSION_KEY, None)
        messages.error(request, 'OTP expired. Request a new OTP.')
        return redirect('accounts:login')

    if entered_otp != payload.get('code'):
        payload['attempts'] = payload.get('attempts', 0) + 1
        request.session[OTP_SESSION_KEY] = payload
        request.session.modified = True
        messages.error(request, 'Incorrect OTP. Please try again.')
        return render(request, 'accounts/login.html', context)

    # Success
    identifier = payload['identifier']
    method = payload['method']
    
    if method == 'email':
        user = User.objects.filter(email=identifier).first()
    else:
        user = User.objects.filter(global_profile__phone_number=identifier).first()
        
    if not user:
        request.session.pop(OTP_SESSION_KEY, None)
        messages.error(request, 'Account not found.')
        return redirect('accounts:login')

    login(request, user)
    request.session.pop(OTP_SESSION_KEY, None)
    
    # Mark as verified
    profile = user.global_profile
    if method == 'email' and not profile.is_email_verified:
        profile.is_email_verified = True
        profile.save()
    elif method == 'mobile' and not profile.is_phone_verified:
        profile.is_phone_verified = True
        profile.save()
        
    messages.success(request, 'Login successful!')
    next_url = payload.get('next', '')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('accounts:dashboard')

def register(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = normalize_phone(request.POST.get('phone'))
        
        if not name or not email or not phone:
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/register.html')
            
        if not is_valid_email(email):
            messages.error(request, 'Enter a valid email address.')
            return render(request, 'accounts/register.html')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, 'This email is already registered.')
            return render(request, 'accounts/register.html')
            
        if UserProfile.objects.filter(phone_number=phone).exists():
            messages.error(request, 'This mobile number is already registered.')
            return render(request, 'accounts/register.html')
            
        # Create user
        user = User.objects.create_user(
            username=phone, # using phone as username
            email=email,
            first_name=name
        )
        
        profile = user.global_profile
        profile.phone_number = phone
        profile.save()
        
        messages.success(request, 'Registration successful! Please login.')
        return redirect('accounts:login')
        
    return render(request, 'accounts/register.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')

def account_dashboard(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next=/account/")
    return render(request, 'accounts/dashboard.html', {'user': request.user})

def profile_edit(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next=/account/profile/")
    profile = request.user.global_profile
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = normalize_phone(request.POST.get('phone'))
        if not name or not is_valid_email(email) or not phone:
            messages.error(request, 'Enter a name, valid email, and 10-digit mobile number.')
        elif User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
            messages.error(request, 'That email address is already in use.')
        elif UserProfile.objects.filter(phone_number=phone).exclude(pk=profile.pk).exists():
            messages.error(request, 'That mobile number is already in use.')
        else:
            email_changed = request.user.email != email
            phone_changed = profile.phone_number != phone
            request.user.first_name = name
            request.user.email = email
            request.user.save(update_fields=('first_name', 'email'))
            if phone_changed:
                profile.is_phone_verified = False
            if email_changed:
                profile.is_email_verified = False
            profile.phone_number = phone
            profile.save()
            messages.success(request, 'Your profile was updated successfully.')
            return redirect('accounts:dashboard')
    return render(request, 'accounts/profile_edit.html', {'profile': profile})
