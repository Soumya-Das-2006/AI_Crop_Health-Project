from django.urls import path
from . import views

app_name = "features"

urlpatterns = [
    # Home
    path("", views.home, name="home"),
    
    # Market Prices
    path("market-prices/", views.market_price_list, name="marketprice"),

    # Crop Info
    path("crop-info/", views.crop_list, name="cropinfo"),
    path("crop-info/<int:id>/", views.crop_detail, name="crop_detail"),

    # Crop Map
    path("crop-map/", views.crop_map, name="crop_map"),
    path("crop-map/analyze/", views.crop_map_analyze, name="crop_map_analyze"),

    # Weather
    path("weather/", views.weather_dashboard, name="weather_dashboard"),
    path("weather/api/", views.weather_api, name="weather_api"),
    path("weather/city-suggestions/", views.city_suggestions, name="city_suggestions"),

    # Government Schemes
    path("schemes/", views.schemes_home, name="schemes_home"),
    path("schemes/<slug:slug>/", views.scheme_detail, name="scheme_detail"),

    # APIs
    path("schemes/api/schemes/", views.get_schemes, name="get_schemes"),
    path("schemes/api/scheme/<int:scheme_id>/", views.get_scheme_details, name="get_scheme_details"),
    
    # Support
    path("support/", views.support, name="support"),
    path("support/send-message/", views.send_support_message, name="send_support_message"),
]