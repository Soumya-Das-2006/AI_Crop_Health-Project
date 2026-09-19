from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import Contact, NewsletterSubscriber, Service, Testimonial, BiodegradableCompany, WasteSubmission

def contact_form(request):
    """Contact us page with form submission"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        location = request.POST.get('location', '')
        related_work = request.POST.get('related_work')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        if name and email and related_work and subject and message:
            contact = Contact.objects.create(
                name=name,
                email=email,
                phone=phone,
                location=location,
                related_work=related_work,
                subject=subject,
                message=message
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Thank you for contacting us! We will get back to you soon.'})
            messages.success(request, 'Thank you for contacting us! We will get back to you soon.')
            return redirect('contact:form')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Please fill in all required fields.'})
            messages.error(request, 'Please fill in all required fields.')

    return render(request, 'contact/contact.html')

def subscribe(request):
    """Newsletter subscription"""
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                validate_email(email)
                subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email)
                if created:
                    message = 'Thank you for subscribing to our newsletter!'
                else:
                    message = 'You are already subscribed to our newsletter.'
                return JsonResponse({'message': message})
            except ValidationError:
                return JsonResponse({'message': 'Please enter a valid email address.'})
        else:
            return JsonResponse({'message': 'Email is required.'})
    return JsonResponse({'message': 'Invalid request method.'})

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
