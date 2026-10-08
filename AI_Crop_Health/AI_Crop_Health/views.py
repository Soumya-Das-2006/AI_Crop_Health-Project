import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core import translation
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


# ======================================================
# PAGE TRANSLATION API
# ======================================================

@require_POST
def translate(request):
    """
    Translate a batch of page strings.

    The DOM walker in static/assets/js/translator.js posts here with the text
    it found and the language the farmer picked. Provider selection, caching
    and graceful degradation all live in core.translation.

    Always returns 200 with usable strings unless the request itself is
    malformed: when every provider fails the original English comes back with
    fallback=true, because a page in English beats a page of blanks.
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    target_lang = (body.get("target_lang") or "en").strip().lower()
    if target_lang not in translation.SUPPORTED_LANGUAGES:
        return JsonResponse({"error": "Unsupported language."}, status=400)

    texts = body.get("texts")
    single = body.get("text")
    if isinstance(texts, list):
        incoming = [str(item) for item in texts]
    elif isinstance(single, str):
        incoming = [single]
    else:
        return JsonResponse({"error": "Provide text or texts."}, status=400)

    if len(incoming) > translation.MAX_TEXTS_PER_REQUEST:
        return JsonResponse(
            {"error": "Too many strings in one request (max {0}).".format(
                translation.MAX_TEXTS_PER_REQUEST)},
            status=400,
        )

    if not any(text.strip() for text in incoming):
        return JsonResponse({"error": "No translatable text provided."}, status=400)

    # English is the source language, so there is nothing to do and no reason
    # to spend a provider call or a cache entry on it.
    if target_lang == "en":
        return JsonResponse({
            "target_lang": target_lang,
            "translations": incoming,
            "from_cache": True,
            "fallback": False,
        })

    translations, from_cache, fallback = translation.translate_with_cache(
        incoming, target_lang
    )

    return JsonResponse({
        "target_lang": target_lang,
        "translations": translations,
        "from_cache": from_cache,
        "fallback": fallback,
    })
