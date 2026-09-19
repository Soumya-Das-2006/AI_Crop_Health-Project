# Django core
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings

# Python standard library
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import traceback

# Third-party
from google import genai

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
# GEMINI CLIENT INITIALIZATION
# ======================================================
_client = None
_AI_ENABLED = False

def get_gemini_client():
    """Lazy initialization of Gemini client"""
    global _client, _AI_ENABLED
    
    if _client is None:
        try:
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY not set - AI features disabled")
                _AI_ENABLED = False
                return None
                
            # Initialize client
            _client = genai.Client(api_key=settings.GEMINI_API_KEY)
            _AI_ENABLED = True
            logger.info("Gemini client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            _AI_ENABLED = False
            _client = None
    
    return _client

def is_ai_enabled():
    """Check if AI features are available"""
    global _AI_ENABLED
    get_gemini_client()  # Ensure client is initialized
    return _AI_ENABLED

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

def build_gemini_prompt(lat: float, lon: float, season: str) -> str:
    """Build zone-based prompt for Gemini AI with authoritative context"""
    zone = get_agro_climatic_zone(lat, lon)
    
    return f"""You are an expert agricultural advisory AI for India.
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
- Recommend crops ONLY from the given agro-climatic zone
- Do NOT repeat crop sets from other zones
- Output MUST change for different zones
- All values are AI-estimated
- Do NOT mention AI, APIs, satellites, or uncertainty disclaimers
- Respond ONLY with valid JSON
- No markdown
- No explanations
- No text before or after JSON

TASKS:
1. Estimate realistic farming weather for this zone
2. Estimate soil properties consistent with this zone's dominant soil type
3. Recommend 4–5 crops commonly grown in this zone (from the list above)
4. Suitability must be between 55 and 95
5. Provide short, practical, farmer-usable tips

JSON FORMAT (STRICT):
{{
  "weather": {{
    "temperature": 0,
    "humidity": 0,
    "wind_speed": 0,
    "air_quality": "Good",
    "recommendations": []
  }},
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
# CROP MAP WITH ZONE-BASED AI
# ======================================================
def crop_map(request):
    """Render the crop map page"""
    return render(request, 'features/crop_map.html')

@require_http_methods(["GET"])
def crop_map_analyze(request):
    """
    Analyze location using zone-based Gemini AI
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
        
        # Check if AI is available
        if not is_ai_enabled():
            logger.warning("AI service not available - returning demo data")
            return JsonResponse({
                'success': True,
                'demo_mode': True,
                'message': 'Running in demo mode. Set GEMINI_API_KEY in .env for AI analysis.',
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
                'weather': {
                    'temperature': 28,
                    'humidity': 65,
                    'wind_speed': 12,
                    'air_quality': 'Good',
                    'recommendations': [
                        'DEMO MODE: Set GEMINI_API_KEY for real AI weather analysis.',
                        'Current data is sample data for demonstration.'
                    ]
                },
                'soil': {
                    'texture': zone['soil'],
                    'organic_matter': '2.5',
                    'moisture': '50',
                    'ph': '6.8-7.2',
                    'npk': {'nitrogen': 'Medium', 'phosphorus': 'Medium', 'potassium': 'Medium'},
                    'recommendations': [
                        'DEMO MODE: Soil analysis requires GEMINI_API_KEY.',
                        'Conduct actual soil test for accurate results.'
                    ]
                },
                'crops': [
                    {
                        'name': zone['crops'].split(',')[0].strip(),
                        'suitability': 75,
                        'tips': [
                            'DEMO DATA: Real recommendations need GEMINI_API_KEY.',
                            f'Common in {zone["name"]} region.'
                        ]
                    },
                    {
                        'name': zone['crops'].split(',')[1].strip() if len(zone['crops'].split(',')) > 1 else 'Rice',
                        'suitability': 70,
                        'tips': [
                            'DEMO DATA: Real recommendations need GEMINI_API_KEY.',
                            'Suitable for local conditions.'
                        ]
                    },
                    {
                        'name': zone['crops'].split(',')[2].strip() if len(zone['crops'].split(',')) > 2 else 'Maize',
                        'suitability': 80,
                        'tips': [
                            'DEMO DATA: Real recommendations need GEMINI_API_KEY.',
                            'Well adapted to this zone.'
                        ]
                    }
                ]
            })
        
        # Build Gemini prompt with zone context
        prompt = build_gemini_prompt(lat, lon, season)
        logger.debug(f"Prompt built (length: {len(prompt)})")
        
        try:
            # Get Gemini client
            client = get_gemini_client()
            if not client:
                raise ValueError("Gemini client not available")
            
            # Call Gemini API
            logger.info(f"Calling Gemini API for lat={lat}, lon={lon}, zone={zone['name']}")
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            
            if not response or not response.text:
                raise ValueError("Empty response from AI service")
                
            response_text = response.text
            logger.debug(f"Got Gemini response (length: {len(response_text)})")
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return fallback data with zone info
            return JsonResponse({
                'success': True,
                'ai_fallback': True,
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
                'weather': {
                    'temperature': 28,
                    'humidity': 65,
                    'wind_speed': 12,
                    'air_quality': 'Good',
                    'recommendations': [
                        'AI service temporarily unavailable. Using sample data.',
                        'Monitor local weather forecasts for accurate updates.'
                    ]
                },
                'soil': {
                    'texture': zone['soil'],
                    'organic_matter': '2.5',
                    'moisture': '50',
                    'ph': '6.8-7.2',
                    'npk': {'nitrogen': 'Medium', 'phosphorus': 'Medium', 'potassium': 'Medium'},
                    'recommendations': [
                        'AI analysis unavailable. Conduct soil test for accurate results.',
                        f'Typical soil type for {zone["name"]}: {zone["soil"]}'
                    ]
                },
                'crops': [
                    {
                        'name': zone['crops'].split(',')[0].strip(),
                        'suitability': 75,
                        'tips': [
                            'Sample data only - AI service unavailable.',
                            f'Common crop in {zone["name"]} region.',
                        ]
                    },
                    {
                        'name': zone['crops'].split(',')[1].strip() if len(zone['crops'].split(',')) > 1 else 'Rice',
                        'suitability': 70,
                        'tips': [
                            'Sample data only - AI service unavailable.',
                            'Suitable for local agro-climatic conditions.',
                        ]
                    },
                    {
                        'name': zone['crops'].split(',')[2].strip() if len(zone['crops'].split(',')) > 2 else 'Maize',
                        'suitability': 80,
                        'tips': [
                            'Sample data only - AI service unavailable.',
                            'Well adapted to this zone.',
                        ]
                    }
                ]
            })
        
        # Parse JSON response
        try:
            ai_data = None
            
            # Try direct JSON parsing first
            try:
                ai_data = json.loads(response_text)
                logger.debug("Successfully parsed JSON directly")
            except json.JSONDecodeError as e:
                logger.debug(f"Direct JSON parse failed, trying cleanup: {e}")
                
                # Clean the response text
                cleaned_text = response_text.strip()
                cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
                cleaned_text = re.sub(r'\s*```', '', cleaned_text)
                
                # Try to find JSON object
                json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    logger.debug("Found JSON in text")
                    ai_data = json.loads(json_str)
                else:
                    logger.error("No JSON found in response")
                    raise ValueError("No valid JSON found in AI response")
            
            # Validate AI response
            if not ai_data:
                logger.error("ai_data is None after parsing")
                raise ValueError("Failed to parse AI response")
                
            # Ensure required fields exist
            if 'weather' not in ai_data:
                ai_data['weather'] = {}
            if 'soil' not in ai_data:
                ai_data['soil'] = {}
            if 'crops' not in ai_data:
                ai_data['crops'] = []
            
            logger.debug("AI data parsed successfully")
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
            
            # Return fallback data
            return JsonResponse({
                'success': True,
                'parse_fallback': True,
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
                'weather': {
                    'temperature': 25,
                    'humidity': 60,
                    'wind_speed': 10,
                    'air_quality': 'Moderate',
                    'recommendations': ['AI response parsing failed.']
                },
                'soil': {
                    'texture': zone['soil'],
                    'organic_matter': '2.0',
                    'moisture': '45',
                    'ph': '6.5-7.5',
                    'npk': {'nitrogen': 'Medium', 'phosphorus': 'Medium', 'potassium': 'Medium'},
                    'recommendations': ['Soil analysis data unavailable.']
                },
                'crops': [
                    {
                        'name': 'General Farming',
                        'suitability': 50,
                        'tips': ['AI crop recommendations temporarily unavailable.']
                    }
                ]
            })
        
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
            'weather': ai_data.get('weather', {}),
            'soil': ai_data.get('soil', {}),
            'crops': ai_data.get('crops', [])
        }
        
        logger.info(f"Successfully returned AI analysis for lat={lat}, lon={lon}, zone={zone['name']}")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Unhandled error in crop_map_analyze: {str(e)}")
        logger.error(traceback.format_exc())
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