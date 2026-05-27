from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/status/', views.api_status, name='api-status'),
    path('api/telemetry/', views.api_telemetry, name='api-telemetry'),
    path('api/analytics/', views.api_analytics, name='api-analytics'),
    path('api/incidents/', views.api_incidents, name='api-incidents'),
    path('api/rl-stats/', views.api_rl_stats, name='api-rl-stats'),
    path('api/xai/diagnosis/<int:incident_id>/', views.api_xai_diagnosis, name='api-xai-diagnosis'),
    path('api/xai/healing/<int:healing_id>/', views.api_xai_healing, name='api-xai-healing'),
]