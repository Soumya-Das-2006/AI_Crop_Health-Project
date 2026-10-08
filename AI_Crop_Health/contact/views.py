import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from core.ratelimit import is_rate_limited

from .forms import ContactForm, NewsletterForm
from .models import Contact, NewsletterSubscriber, Service, Testimonial, BiodegradableCompany, WasteSubmission

logger = logging.getLogger(__name__)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def contact_form(request):
    """
    Contact page.

    Previously this read request.POST directly and called
    Contact.objects.create(), which runs no validators at all: an invalid email
    was stored, and an over-length name raised DataError (HTTP 500) on
    PostgreSQL. It also had no spam protection. Now a ModelForm validates
    everything, a honeypot plus timing check catches bots, and submissions are
    rate limited per IP.
    """
    if request.method == 'POST':
        if is_rate_limited(request, 'contact', limit=5, window_seconds=3600):
            text = ('You have sent several messages recently. '
                    'Please wait a while before sending another.')
            if _is_ajax(request):
                return JsonResponse({'status': 'error', 'message': text}, status=429)
            messages.error(request, text)
            return render(request, 'contact/contact.html', {
                'form': ContactForm(),
                'form_rendered_at': ContactForm.initial_timestamp(),
            }, status=429)

        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            logger.info('Contact message #%s received from %s',
                        contact.pk, contact.email)
            text = 'Thank you for contacting us! We will get back to you soon.'
            if _is_ajax(request):
                return JsonResponse({'status': 'success', 'message': text})
            messages.success(request, text)
            return redirect('contact:form')

        if _is_ajax(request):
            return JsonResponse(
                {'status': 'error',
                 'message': 'Please check the form and try again.',
                 'errors': form.errors},
                status=400,
            )
        messages.error(request, 'Please correct the errors below.')
        return render(request, 'contact/contact.html', {
            'form': form,
            'form_rendered_at': ContactForm.initial_timestamp(),
        })

    return render(request, 'contact/contact.html', {
        'form': ContactForm(),
        'form_rendered_at': ContactForm.initial_timestamp(),
    })


def subscribe(request):
    """Newsletter subscription (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'message': 'Invalid request method.'}, status=405)

    if is_rate_limited(request, 'subscribe', limit=5, window_seconds=3600):
        return JsonResponse(
            {'message': 'Too many attempts. Please try again later.'}, status=429,
        )

    form = NewsletterForm(request.POST)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        return JsonResponse({'message': first_error}, status=400)

    email = form.cleaned_data['email']
    _, created = NewsletterSubscriber.objects.get_or_create(email=email)
    return JsonResponse({
        'message': ('Thank you for subscribing to our newsletter!' if created
                    else 'You are already subscribed to our newsletter.'),
    })

def services(request):
    """Services page"""
    services = Service.objects.filter(is_active=True)
    testimonials = Testimonial.objects.filter(is_active=True)
    context = {
        'services': services,
        'testimonials': testimonials,
    }
    return render(request, 'contact/services.html', context)

def testimonials(request):
    """Testimonials page"""
    testimonials = Testimonial.objects.filter(is_active=True)
    context = {
        'testimonials': testimonials,
    }
    return render(request, 'contact/testimonials.html', context)

def admin_panel(request):
    """Contact admin panel"""
    total_contacts = Contact.objects.count()
    unread_contacts = Contact.objects.filter(is_read=False).count()
    total_services = Service.objects.count()
    total_testimonials = Testimonial.objects.count()
    recent_contacts = Contact.objects.order_by('-created_date')[:5]
    services = Service.objects.all()[:5]
    testimonials = Testimonial.objects.all()[:5]
    companies = BiodegradableCompany.objects.all()[:10]  # Show recent companies

    context = {
        'total_contacts': total_contacts,
        'unread_contacts': unread_contacts,
        'total_services': total_services,
        'total_testimonials': total_testimonials,
        'recent_contacts': recent_contacts,
        'services': services,
        'testimonials': testimonials,
        'companies': companies,
    }
    return render(request, 'contact/admin_panel.html', context)

def user_panel(request):
    """Contact user panel"""
    user_contacts = Contact.objects.filter(email=request.user.email).order_by('-created_date')
    user_subscribed = NewsletterSubscriber.objects.filter(email=request.user.email).exists()
    user_subscription_date = None
    if user_subscribed:
        user_subscription_date = NewsletterSubscriber.objects.get(email=request.user.email).subscribed_date

    context = {
        'user_contacts': user_contacts,
        'user_subscribed': user_subscribed,
        'user_subscription_date': user_subscription_date,
    }
    return render(request, 'contact/user_panel.html', context)

def biodegradable(request):
    """Biodegradable waste solutions page"""
    companies = BiodegradableCompany.objects.filter(is_active=True)
    context = {
        'companies': companies,
    }
    return render(request, 'contact/biodegradable.html', context)

def submit_waste(request):
    """API endpoint for waste submission"""
    if request.method == 'POST':
        try:
            farmer_name = request.POST.get('farmerName')
            mobile_number = request.POST.get('mobileNumber')
            village = request.POST.get('village')
            district = request.POST.get('district')
            state = request.POST.get('state')
            crop_type = request.POST.get('cropType')
            waste_type = request.POST.get('wasteType')
            quantity = request.POST.get('quantity')
            notes = request.POST.get('notes', '')
            image = request.FILES.get('image')

            if not all([farmer_name, mobile_number, village, district, state, crop_type, waste_type, quantity]):
                return JsonResponse({'status': 'error', 'message': 'Please fill in all required fields.'})

            waste_submission = WasteSubmission.objects.create(
                farmer_name=farmer_name,
                mobile_number=mobile_number,
                village=village,
                district=district,
                state=state,
                crop_type=crop_type,
                waste_type=waste_type,
                quantity=quantity,
                notes=notes,
                image=image
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Thank you! Your waste submission has been received. We will contact you soon.',
                'submission_id': waste_submission.id
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'An error occurred. Please try again later.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

def send_company_email(request):
    """API endpoint for sending collaboration emails to companies"""
    if request.method == 'POST':
        try:
            company_name = request.POST.get('companyName')
            company_email = request.POST.get('companyEmail')
            material_interest = request.POST.get('materialInterest')
            message = request.POST.get('message')

            if not all([company_name, company_email, material_interest, message]):
                return JsonResponse({'status': 'error', 'message': 'Please fill in all required fields.'})

            # Generate email content
            subject = "Collaboration Opportunity: Agricultural Waste to Biodegradable Solutions"
            body = f"""Subject: {subject}

Dear {company_name},

{message}

Material Interest: {material_interest}

Platform: AgriCulture - Smart Farming Solutions
Contact: info@agriculture.com
Phone: +012 345 6789

We look forward to your response and potential collaboration.

Best regards,
AgriCulture Team
AgriCulture Platform
www.agriculture.com"""

            # For now, return the email content (in production, you'd send actual email)
            # You can integrate with Django's email system or services like SendGrid

            return JsonResponse({
                'status': 'success',
                'message': 'Email prepared successfully.',
                'email_data': {
                    'to': company_email,
                    'subject': subject,
                    'body': body
                }
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'An error occurred. Please try again later.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
