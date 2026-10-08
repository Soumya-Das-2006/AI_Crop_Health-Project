from django.urls import path
from . import views

app_name = 'iot_sensor'

urlpatterns = [
    # Farmer field management
    path('fields/',                              views.field_dashboard,   name='field_dashboard'),
    path('fields/<int:field_id>/',               views.field_detail,      name='field_detail'),
    path('fields/<int:field_id>/irrigate/',      views.irrigation_control,name='irrigation_control'),
    path('fields/<int:field_id>/zones/',         views.zone_map,          name='zone_map'),

    # Alerts
    path('alerts/',                              views.alert_dashboard,   name='alert_dashboard'),

    # Evaluation metrics
    path('metrics/',                             views.metrics_dashboard, name='metrics_dashboard'),

    # Farmer self-service hardware registration
    path('hardware/',                            views.hardware_home,     name='hardware_home'),
    path('hardware/field/new/',                  views.field_create,      name='field_create'),
    path('hardware/field/<int:field_id>/device/new/', views.node_create,  name='node_create'),

    # APIs
    path('api/ingest/',                          views.sensor_ingest,     name='sensor_ingest'),
    path('api/fields/<int:field_id>/readings/',  views.readings_api,      name='readings_api'),
]
