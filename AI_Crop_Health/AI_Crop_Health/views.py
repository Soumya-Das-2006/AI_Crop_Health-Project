from django.shortcuts import render
from contact.models import Service, Testimonial
from blog.models import BlogPost
from features.models import GovernmentScheme

def home(request):
    """Render the home page"""
    services = Service.objects.filter(is_active=True)
    testimonials = Testimonial.objects.filter(is_active=True)
    latest_posts = BlogPost.objects.filter(is_published=True).order_by('-publish_date')[:3]
    schemes = GovernmentScheme.objects.filter(is_active=True) \
        .order_by('-last_updated')[:3]

    context = {
        'services': services,
        'govt_schemes': schemes,
        'testimonials': testimonials,
        'latest_posts': latest_posts,
    }
    return render(request, 'ai_crop_health/index.html', context)

def about(request):
    """Render the about page"""
    return render(request, 'ai_crop_health/about.html')
