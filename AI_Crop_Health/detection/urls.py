from django.urls import path
from . import views

app_name = "detection"

urlpatterns = [
    path("chatbot/", views.chatbot, name="chatbot"),
    path("chatbot/api/", views.chatbot_api, name="chatbot_api"),
    path("suggestion/", views.suggestion, name="suggestion"),
    path("diagnosis/", views.diagnosis, name="diagnosis"),
    path("crop-recommendation/", views.crop_recommendation_view, name="crop_recommendation"),
    path("fertilizer-recommendation/", views.fertilizer_recommendation_view, name="fertilizer_recommendation"),
    path("diagnosis/", views.plant_disease_diagnosis, name="diagnosis"),
    path("advisory/", views.agriculture_advisory_view, name="suggestion"),
    path("suggestion/", views.agriculture_advisory_view, name="suggestion_alt"),
    path("api/advisory/", views.agriculture_advisory_api, name="advisory_api"),
    path("api/advisory/reaction/", views.record_reaction_api, name="reaction_api"),
    
    # Privacy-first history
    path("history/", views.my_detection_history, name="my_detection_history"),
    path("history/save/<int:log_id>/", views.save_detection_history, name="save_detection_history"),
    path("history/delete/<int:history_id>/", views.delete_detection_history, name="delete_detection_history"),
]