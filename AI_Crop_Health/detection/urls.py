from django.urls import path
from . import views

app_name = "detection"

urlpatterns = [
    path("chatbot/", views.chatbot, name="chatbot"),
    path("chatbot/api/", views.chatbot_api, name="chatbot_api"),
    path("chatbot/history/", views.chatbot_history, name="chatbot_history"),
    path("chatbot/new/", views.chatbot_new, name="chatbot_new"),
    path("chatbot/reset/", views.chatbot_reset, name="chatbot_reset"),

    # "diagnosis/" and "suggestion/" were each registered twice. Django serves
    # the first match but reverses to the last, so `detection:suggestion`
    # resolved to /advisory/ while /suggestion/ was served by a stub that
    # rendered the template with no context at all - a visibly broken page.
    # One path per URL now, both names pointing at the working view.
    path("diagnosis/", views.plant_disease_diagnosis, name="diagnosis"),
    path("crop-recommendation/", views.crop_recommendation_view, name="crop_recommendation"),
    path("fertilizer-recommendation/", views.fertilizer_recommendation_view, name="fertilizer_recommendation"),
    path("advisory/", views.agriculture_advisory_view, name="suggestion"),
    path("suggestion/", views.agriculture_advisory_view, name="suggestion_alt"),
    path("api/advisory/", views.agriculture_advisory_api, name="advisory_api"),
    path("api/advisory/reaction/", views.record_reaction_api, name="reaction_api"),
    
    # Insect identification
    path("insect/", views.insect_identification, name="insect"),

    # Ask AI - follow-up questions about a diagnosed photo
    path("api/ask-ai/", views.ask_ai_api, name="ask_ai_api"),
    path("api/ask-ai/<int:log_id>/history/", views.ask_ai_history, name="ask_ai_history"),
    path(
        "api/ask-ai/insect/<int:log_id>/history/",
        views.ask_ai_history,
        {"kind": "insect"},
        name="ask_ai_insect_history",
    ),

    # Privacy-first history
    path("history/", views.my_detection_history, name="my_detection_history"),
    path("history/save/<int:log_id>/", views.save_detection_history, name="save_detection_history"),
    path("history/delete/<int:history_id>/", views.delete_detection_history, name="delete_detection_history"),
]