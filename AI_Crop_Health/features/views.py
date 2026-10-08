# Django core
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings

# Python standard library
import json
import math
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Third-party
from detection.groq_client import GroqClient, GroqError

# Local models
from .models import (
    MarketPrice,
    CropInfo,
    SchemeCategory,
    GovernmentScheme,
    Suggestion,
    SupportMessage,
)

# Local services
from .services.weather_service import WeatherService
from .services.farming_advisory import FarmingAdvisory

# ======================================================
# LOGGING
# ======================================================
logger = logging.getLogger(__name__)

# ======================================================
# CONSTANTS & VALIDATION HELPERS
# ======================================================
INDIA_BOUNDS = {
    'lat_min': 8.4,    # Kanyakumari
    'lat_max': 37.6,   # Northern Kashmir
    'lon_min': 68.1,   # Western Gujarat
    'lon_max': 97.4,   # Eastern Arunachal
}

# Regional Agricultural Zones (for zone-based AI guidance)
AGRO_CLIMATIC_ZONES = {
    'Northern_Plains': {
        'lat_range': (28, 32), 'lon_range': (74, 80),
        'states': ['Punjab', 'Haryana', 'Western UP'],
        'typical_crops': ['Wheat', 'Rice', 'Sugarcane', 'Cotton', 'Mustard'],
        'soil': 'Alluvial', 'rainfall': 'Medium'
    },
    'Eastern_Plains': {
        'lat_range': (22, 28), 'lon_range': (84, 90),
        'states': ['Bihar', 'West Bengal', 'Eastern UP'],
        'typical_crops': ['Rice', 'Jute', 'Wheat', 'Maize', 'Vegetables'],
        'soil': 'Alluvial', 'rainfall': 'High'
    },
    'Deccan_Plateau': {
        'lat_range': (15, 20), 'lon_range': (74, 80),
        'states': ['Maharashtra', 'Karnataka', 'Telangana'],
        'typical_crops': ['Cotton', 'Sorghum (Jowar)', 'Groundnut', 'Pigeon Pea (Tur)', 'Soybean'],
        'soil': 'Black', 'rainfall': 'Medium'
    },
    'Western_Arid': {
        'lat_range': (24, 30), 'lon_range': (70, 75),
        'states': ['Rajasthan', 'Gujarat'],
        'typical_crops': ['Pearl Millet (Bajra)', 'Sorghum (Jowar)', 'Mustard', 'Cotton', 'Gram'],
        'soil': 'Sandy', 'rainfall': 'Low'
    },
    'Southern_Peninsula': {
        'lat_range': (8, 16), 'lon_range': (75, 80),
        'states': ['Tamil Nadu', 'Kerala', 'Southern Karnataka'],
        'typical_crops': ['Rice', 'Coconut', 'Banana', 'Spices', 'Groundnut'],
        'soil': 'Red/Laterite', 'rainfall': 'High'
    },
    'Coastal_East': {
        'lat_range': (13, 20), 'lon_range': (80, 86),
        'states': ['Andhra Pradesh', 'Odisha'],
        'typical_crops': ['Rice', 'Groundnut', 'Cashew', 'Pulses', 'Coconut'],
        'soil': 'Alluvial/Red', 'rainfall': 'High'
    },
    'North_East': {
        'lat_range': (24, 28), 'lon_range': (89, 95),
        'states': ['Assam', 'Meghalaya', 'Tripura'],
        'typical_crops': ['Rice', 'Tea', 'Maize', 'Jute', 'Pineapple'],
        'soil': 'Alluvial/Laterite', 'rainfall': 'Very High'
    },
    'Central_Highlands': {
        'lat_range': (21, 26), 'lon_range': (75, 82),
        'states': ['Madhya Pradesh', 'Chhattisgarh'],
        'typical_crops': ['Soybean', 'Wheat', 'Rice', 'Gram', 'Sorghum'],
        'soil': 'Black/Red', 'rainfall': 'Medium'
    }
}

# ======================================================
# HELPER FUNCTIONS
# ======================================================
def validate_indian_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """Validate if coordinates are within India boundaries"""
    if not (INDIA_BOUNDS['lat_min'] <= lat <= INDIA_BOUNDS['lat_max']):
        return False, "Location outside Indian territory (latitude)"
    
    if not (INDIA_BOUNDS['lon_min'] <= lon <= INDIA_BOUNDS['lon_max']):
        return False, "Location outside Indian territory (longitude)"
    
    return True, None

def get_season(month: int) -> str:
    """Determine Indian agricultural season from month"""
    if month in [6, 7, 8, 9]:
        return 'Kharif'  # Monsoon season (June-September)
    elif month in [10, 11, 12, 1, 2, 3]:
        return 'Rabi'    # Winter season (October-March)
    else:
        return 'Zaid'    # Summer season (April-May)

def get_agro_climatic_zone(lat: float, lon: float) -> Dict:
    """Determine agro-climatic zone from coordinates"""
    for zone_name, zone_data in AGRO_CLIMATIC_ZONES.items():
        lat_range = zone_data['lat_range']
        lon_range = zone_data['lon_range']
        
        if (lat_range[0] <= lat <= lat_range[1] and 
            lon_range[0] <= lon <= lon_range[1]):
            return {
                'name': zone_name.replace('_', ' '),
                'soil': zone_data['soil'],
                'rainfall': zone_data['rainfall'],
                'crops': ', '.join(zone_data['typical_crops']),
                'states': ', '.join(zone_data['states'])
            }
    
    # Default fallback zone for areas not in defined zones
    return {
        'name': 'Central India',
        'soil': 'Mixed',
        'rainfall': 'Medium',
        'crops': 'Wheat, Rice, Pulses, Oilseeds',
        'states': 'Central India'
    }

def build_crop_map_prompt(lat: float, lon: float, season: str) -> str:
    """Build a grounded Crop Map prompt for Groq."""
    zone = get_agro_climatic_zone(lat, lon)
    
    return f"""You are an agricultural advisory assistant for India.
This request belongs to a FIXED agro-climatic zone.
These zone facts are authoritative and MUST be followed.

AGRO-CLIMATIC CONTEXT:
- Zone Name: {zone['name']}
- Dominant Soil Type: {zone['soil']}
- Rainfall Pattern: {zone['rainfall']}
- Common Crops in this Zone: {zone['crops']}
- Regional States: {zone['states']}

LOCATION:
- Latitude: {lat}
- Longitude: {lon}
- Current Season: {season}
- Country: India

CRITICAL RULES (DO NOT VIOLATE):
- Recommend crops ONLY using names from the given agro-climatic zone list
- Do NOT repeat crop sets from other zones
- Soil values are estimates, not verified soil-test results.
- Provide practical guidance, and advise field observation or soil testing where
  measurements are needed.
- Respond ONLY with valid JSON
- No markdown
- No explanations
- No text before or after JSON

TASKS:
1. Estimate likely soil properties consistent with this zone's dominant soil
   type, clearly treating them as estimates.
2. Recommend 3–4 crops commonly grown in this zone (from the list above)
3. Suitability must be between 55 and 95
4. Provide short, practical, farmer-usable tips
5. Give organic_matter and moisture as numeric percentages without a % sign,
   pH as a numeric value or range, and each NPK value as Low, Medium, or High.

JSON FORMAT (STRICT):
{{
  "soil": {{
    "texture": "",
    "organic_matter": "",
    "moisture": "",
    "ph": "",
    "npk": {{
      "nitrogen": "",
      "phosphorus": "",
      "potassium": ""
    }},
    "recommendations": []
  }},
  "crops": [
    {{
      "name": "",
      "suitability": 0,
      "tips": []
    }}
  ]
}}

RESPOND WITH JSON ONLY."""


def parse_crop_map_response(response_text: str, allowed_crops: List[str]) -> Dict:
    """Parse and validate the JSON structure returned by the Crop Map model."""
    cleaned_text = response_text.strip()
    cleaned_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', cleaned_text, flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if not json_match:
            raise ValueError("Groq response did not contain JSON")
        data = json.loads(json_match.group())

    if not isinstance(data, dict):
        raise ValueError("Groq response must be a JSON object")

    soil = data.get('soil')
    crops = data.get('crops')
    if not isinstance(soil, dict):
        raise ValueError("Groq response is missing soil data")
    if not isinstance(crops, list) or not 3 <= len(crops) <= 4:
        raise ValueError("Groq response must include 3 to 4 crop recommendations")
    allowed_crop_names = {
        crop.strip().casefold(): crop.strip()
        for crop in allowed_crops
        if crop.strip()
    }
    if not allowed_crop_names:
        raise ValueError("No crops are configured for the detected zone")

    for key in ('texture', 'organic_matter', 'moisture', 'ph'):
        value = soil.get(key)
        if key == 'texture':
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Groq response has incomplete soil estimates")
            soil[key] = value.strip()[:100]
        elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("Groq response has incomplete soil estimates")
        elif isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError("Groq response has invalid soil estimates")
            soil[key] = str(value)
        elif not value.strip():
            raise ValueError("Groq response has incomplete soil estimates")
        else:
            soil[key] = value.strip()[:100]
    for key, maximum in (('organic_matter', 20), ('moisture', 100)):
        estimate = soil[key]
        if not re.fullmatch(r'\d{1,3}(?:\.\d{1,2})?', estimate):
            raise ValueError("Groq response has invalid soil percentage estimates")
        if not 0 <= float(estimate) <= maximum:
            raise ValueError("Groq response has out-of-range soil percentage estimates")
    ph_values = re.fullmatch(
        r'(\d{1,2}(?:\.\d)?)\s*(?:[-–]\s*(\d{1,2}(?:\.\d)?))?',
        soil['ph'],
    )
    if not ph_values or any(float(value) > 14 for value in ph_values.groups() if value):
        raise ValueError("Groq response has invalid soil pH estimate")
    npk = soil.get('npk')
    if not isinstance(npk, dict) or any(
        not isinstance(npk.get(key), str)
        or npk[key].strip() not in ('Low', 'Medium', 'High')
        for key in ('nitrogen', 'phosphorus', 'potassium')
    ):
        raise ValueError("Groq response has invalid NPK estimates")
    soil['npk'] = {
        key: npk[key].strip()
        for key in ('nitrogen', 'phosphorus', 'potassium')
    }
    soil['recommendations'] = _validated_text_list(
        soil.get('recommendations'), 'soil recommendations', 1, 5
    )

    validated_crops = []
    for crop in crops:
        if not isinstance(crop, dict):
            raise ValueError("Groq response has an invalid crop recommendation")
        name = crop.get('name')
        suitability = crop.get('suitability')
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Groq response has a crop without a name")
        canonical_name = allowed_crop_names.get(name.strip().casefold())
        if canonical_name is None:
            raise ValueError("Groq response recommended a crop outside the zone list")
        if (
            isinstance(suitability, bool)
            or not isinstance(suitability, (int, float))
            or not math.isfinite(suitability)
        ):
            raise ValueError("Groq response has invalid crop suitability")
        if not 55 <= suitability <= 95:
            raise ValueError("Groq response has out-of-range crop suitability")
        validated_crops.append({
            'name': canonical_name,
            'suitability': round(suitability),
            'tips': _validated_text_list(crop.get('tips'), 'crop tips', 1, 5),
        })
    data['crops'] = validated_crops
    data['soil'] = soil
    return data


def build_crop_map_weather(current: Dict) -> Dict:
    """Format observed current conditions returned by OpenWeatherMap."""
    try:
        current_conditions = current['main']
        wind = current['wind']
        condition = current['weather'][0]
        temperature = current_conditions['temp']
        humidity = current_conditions['humidity']
        wind_speed = wind['speed']
        description = condition['description']
        condition_main = condition['main']
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("OpenWeatherMap returned incomplete current weather") from exc

    numeric_values = (temperature, humidity, wind_speed)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in numeric_values
    ):
        raise ValueError("OpenWeatherMap returned invalid current weather values")
    if not -100 <= temperature <= 70 or not 0 <= humidity <= 100 or wind_speed < 0:
        raise ValueError("OpenWeatherMap returned out-of-range current weather values")
    if (
        not isinstance(description, str)
        or not description.strip()
        or not isinstance(condition_main, str)
    ):
        raise ValueError("OpenWeatherMap returned no weather description")

    recommendations = []
    if temperature >= 35:
        recommendations.append("Schedule field work and irrigation during cooler hours.")
    if humidity >= 85:
        recommendations.append("Check crops for signs of moisture-related fungal disease.")
    if wind_speed >= 8:
        recommendations.append("Avoid spraying during strong winds to reduce spray drift.")
    if condition_main.casefold() in ('rain', 'drizzle', 'thunderstorm'):
        recommendations.append("Check fields for waterlogging and postpone irrigation.")
    if not recommendations:
        recommendations.append("Check field soil moisture before deciding whether to irrigate.")

    return {
        'temperature': round(temperature, 1),
        'humidity': humidity,
        'wind_speed': round(wind_speed * 3.6, 1),
        'description': description.strip().capitalize(),
        'recommendations': recommendations,
        'source': 'OpenWeatherMap',
    }


def _validated_text_list(value, label: str, minimum: int, maximum: int) -> List[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError("Groq response has invalid {0}".format(label))
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("Groq response has invalid {0}".format(label))
    return [item.strip()[:300] for item in value]

# ======================================================
# HOME PAGE
# ======================================================
def home(request):
    govt_schemes = (
        GovernmentScheme.objects
        .filter(is_active=True)
        .order_by('-last_updated')[:3]
    )
    return render(request, 'index.html', {'govt_schemes': govt_schemes})

# ======================================================
# MARKET PRICE
# ======================================================
def market_price_list(request):
    category = request.GET.get('category', '')
    prices = MarketPrice.objects.filter(is_active=True).order_by('-last_updated')
    if category:
        prices = prices.filter(category=category)
    categories = (
        MarketPrice.objects
        .filter(is_active=True)
        .values_list('category', flat=True)
        .distinct()
    )
    return render(request, 'features/marketprice.html', {
        'prices': prices,
        'categories': categories,
        'selected_category': category,
    })

# ======================================================
# CROP INFO
# ======================================================
def crop_list(request):
    category = request.GET.get('category', '')
    season = request.GET.get('season', '')
    crops = CropInfo.objects.filter(is_active=True)
    if category:
        crops = crops.filter(category=category)
    if season:
        crops = crops.filter(season=season)
    categories = CropInfo.objects.filter(is_active=True).values_list('category', flat=True).distinct()
    seasons = CropInfo.objects.filter(is_active=True).values_list('season', flat=True).distinct()
    return render(request, 'features/cropinfo.html', {
        'crops': crops,
        'categories': categories,
        'seasons': seasons,
        'selected_category': category,
        'selected_season': season,
    })

def crop_detail(request, id):
    crop = get_object_or_404(CropInfo, id=id, is_active=True)
    return render(request, 'features/crop_detail.html', {'crop': crop})

# ======================================================
# CROP MAP WITH ZONE-BASED GROQ AI
# ======================================================
def crop_map(request):
    """Render the crop map page"""
    return render(request, 'features/crop_map.html')

@require_http_methods(["GET"])
def crop_map_analyze(request):
    """
    Analyze location using zone-based Groq AI
    Returns weather, soil, and crop recommendations
    """
    logger.debug("crop_map_analyze called")
    
    try:
        # Parse coordinates
        lat_str = request.GET.get('lat', '28.6139')
        lon_str = request.GET.get('lon', '77.2090')
        
        logger.debug(f"Raw parameters: lat={lat_str}, lon={lon_str}")
        
        try:
            lat = float(lat_str)
            lon = float(lon_str)
            logger.debug(f"Parsed coordinates: lat={lat}, lon={lon}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid lat/lon parameters: {lat_str}, {lon_str} - {e}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid coordinates. Please provide valid numbers.'
            }, status=400)
        
        # Validate Indian coordinates
        is_valid, error_msg = validate_indian_coordinates(lat, lon)
        if not is_valid:
            logger.warning(f"Invalid coordinates: {lat}, {lon} - {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=400)
        
        # Get current season
        current_month = datetime.now().month
        season = get_season(current_month)
        logger.debug(f"Current month: {current_month}, Season: {season}")
        
        # Determine agro-climatic zone
        zone = get_agro_climatic_zone(lat, lon)
        logger.info(f"Detected zone: {zone['name']} (Soil: {zone['soil']}, Rainfall: {zone['rainfall']})")

        current_weather = WeatherService().get_current_weather(lat, lon)
        if current_weather is None:
            logger.error("OpenWeatherMap returned no current weather for lat=%s, lon=%s", lat, lon)
            return JsonResponse({
                'success': False,
                'error': 'Live weather is unavailable. Check the weather API configuration and try again.',
            }, status=503)
        try:
            weather_data = build_crop_map_weather(current_weather)
        except ValueError as e:
            logger.warning("OpenWeatherMap returned invalid current weather: %s", e)
            return JsonResponse({
                'success': False,
                'error': 'The weather service returned invalid data. Please try again.',
            }, status=502)
        
        if not settings.GROQ_API_KEY:
            logger.error("Crop Map analysis requested but GROQ_API_KEY is not configured")
            return JsonResponse({
                'success': False,
                'error': 'Crop Map AI is not configured. Please contact the site administrator.',
            }, status=503)

        prompt = build_crop_map_prompt(lat, lon, season)
        groq = GroqClient(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
            timeout=settings.GROQ_TIMEOUT,
            text_model=settings.GROQ_TEXT_MODEL,
        )
        logger.info(
            "Requesting Crop Map analysis from Groq for zone=%s", zone['name']
        )
        system_prompt = (
            "You are a careful agricultural advisor. Follow the supplied "
            "regional facts, distinguish soil estimates from measurements, and "
            "return only valid JSON matching the requested schema."
        )
        for attempt in range(2):
            response_text, model_used, _ = groq.complete(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=1800,
                json_mode=True,
            )
            try:
                ai_data = parse_crop_map_response(
                    response_text, zone['crops'].split(',')
                )
                break
            except ValueError as e:
                if attempt == 1:
                    logger.warning("Groq returned invalid Crop Map data: %s", e)
                    return JsonResponse({
                        'success': False,
                        'error': 'Crop Map AI returned an invalid result. Please try again.',
                    }, status=502)
                logger.warning(
                    "Groq returned invalid Crop Map data; retrying once: %s", e
                )
        
        # Return successful response with zone info
        response_data = {
            'success': True,
            'location': {
                'lat': lat,
                'lon': lon,
                'season': season,
                'zone': zone['name'],
                'zone_details': {
                    'soil_type': zone['soil'],
                    'rainfall': zone['rainfall'],
                    'states': zone['states']
                }
            },
            'weather': weather_data,
            'soil': ai_data.get('soil', {}),
            'crops': ai_data.get('crops', []),
            'provider': 'Groq',
            'model': model_used,
        }
        
        logger.info(f"Successfully returned AI analysis for lat={lat}, lon={lon}, zone={zone['name']}")
        return JsonResponse(response_data)
        
    except GroqError:
        logger.exception("Groq Crop Map analysis failed")
        return JsonResponse({
            'success': False,
            'error': 'Crop Map AI is temporarily unavailable. Please try again shortly.',
        }, status=503)
    except Exception:
        logger.exception("Unhandled error in crop_map_analyze")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error. Please try again later.'
        }, status=500)

# ======================================================
# WEATHER
# ======================================================
def weather_dashboard(request):
    city = request.GET.get('city')
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    view_type = request.GET.get('type', 'dashboard')

    weather_service = WeatherService()
    advisory_service = FarmingAdvisory()

    if lat and lon:
        weather_data = weather_service.get_weather_data(city=city, lat=lat, lon=lon)
        city = city or "Your Location"
    else:
        city = city or "India"
        weather_data = weather_service.get_weather_data(city=city)

    advisories = advisory_service.get_advisory(weather_data, city)

    return render(request, 'features/weather_dashboard.html', {
        'city': city,
        'weather': weather_data,
        'advisories': advisories,
        'view_type': view_type,
    })

def weather_api(request):
    city = request.GET.get('city', 'India')
    weather_service = WeatherService()
    advisory_service = FarmingAdvisory()
    weather_data = weather_service.get_weather_data(city)
    advisories = advisory_service.get_advisory(weather_data, city)

    response_data = {
        'city': city,
        'weather': {
            'current': weather_data['current'],
            'hourly': weather_data['hourly'],
            'daily': weather_data['daily'],
            'uv_index': weather_data['uv_index'],
            'sunrise': weather_data['sunrise'].strftime('%H:%M')
            if isinstance(weather_data['sunrise'], datetime) else str(weather_data['sunrise']),
            'sunset': weather_data['sunset'].strftime('%H:%M')
            if isinstance(weather_data['sunset'], datetime) else str(weather_data['sunset']),
        },
        'advisories': advisories
    }

    if weather_data.get('alerts'):
        response_data['weather']['alerts'] = [
            {
                'event': alert['event'],
                'description': alert['description'],
                'start': alert['start'].isoformat() if isinstance(alert.get('start'), datetime) else alert.get('start'),
                'end': alert['end'].isoformat() if isinstance(alert.get('end'), datetime) else alert.get('end'),
            }
            for alert in weather_data['alerts']
        ]

    return JsonResponse(response_data)

def city_suggestions(request):
    query = request.GET.get('q', '').lower()
    popular_cities = [
        'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai',
        'Kolkata', 'Pune', 'Ahmedabad', 'Jaipur', 'Lucknow',
        'Kanpur', 'Nagpur', 'Indore', 'Thane', 'Bhopal',
        'Visakhapatnam', 'Patna', 'Vadodara', 'Ghaziabad', 'Ludhiana'
    ]
    suggestions = [
        {'name': city, 'full_name': f"{city}, IN", 'country': 'IN'}
        for city in popular_cities if query in city.lower()
    ]
    return JsonResponse({'suggestions': suggestions[:10]})

# ======================================================
# SCHEMES
# ======================================================
def schemes_home(request):
    schemes = (
        GovernmentScheme.objects
        .filter(is_active=True)
        .select_related('category')
        .order_by('-last_updated')
    )
    initial_schemes = [
        {
            'id': s.id,
            'name': s.name,
            'slug': s.slug,
            'ministry': s.ministry,
            'budget': str(s.budget),
            'category_name': s.category.name if s.category else '',
            'icon': s.icon,
        }
        for s in schemes
    ]
    return render(request, 'features/schemes_home.html', {'initial_schemes': initial_schemes})

def scheme_detail(request, slug):
    scheme = get_object_or_404(GovernmentScheme, slug=slug, is_active=True)
    return render(request, 'features/scheme_detail.html', {'scheme': scheme})

def get_schemes(request):
    category_slug = request.GET.get('category', '')
    search_query = request.GET.get('search', '')
    schemes = GovernmentScheme.objects.filter(is_active=True).select_related('category')
    
    if category_slug:
        schemes = schemes.filter(category__slug=category_slug)
    if search_query:
        schemes = schemes.filter(
            Q(name__icontains=search_query) |
            Q(ministry__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    return JsonResponse({
        'schemes': [
           {
                'id': s.id,
                'name': s.name,
                'slug': s.slug,
                'ministry': s.ministry,
                'budget': str(s.budget),
                'budget_display': s.get_budget_display(),
                'category_name': s.category.name if s.category else '',
                'category_slug': s.category.slug if s.category else '',
                'icon': s.icon,
            }
            for s in schemes
        ]
    })

def get_scheme_details(request, scheme_id):
    scheme = get_object_or_404(GovernmentScheme, id=scheme_id, is_active=True)
    return JsonResponse({
        'success': True,
        'scheme': {
            'id': scheme.id,
            'name': scheme.name,
            'ministry': scheme.ministry,
            'budget_display': scheme.get_budget_display(),
            'description': scheme.description,
            'benefits': scheme.benefits,
            'eligibility': scheme.eligibility,
            'application_process': scheme.application_process,
            'contact_info': scheme.contact_info,
            'documents_required': scheme.documents_required,
            'website_url': scheme.website_url,
        }
    })

# ======================================================
# SUPPORT
# ======================================================
def support(request):
    suggestions = Suggestion.objects.filter(is_active=True).order_by('-created_at')
    messages = []
    if request.user.is_authenticated:
        messages = SupportMessage.objects.filter(user=request.user).order_by('created_at')
    return render(request, "features/support.html", {
        "suggestions": suggestions,
        "messages": messages,
    })

@require_http_methods(["POST"])
@login_required
def send_support_message(request):
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()

        if not message:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty'})

        msg = SupportMessage.objects.create(
            user=request.user,
            message=message,
            is_from_admin=False
        )

        return JsonResponse({
            'success': True,
            'message': {
                'id': msg.id,
                'message': msg.message,
                'created_at': msg.created_at.isoformat(),
                'is_from_admin': False
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})