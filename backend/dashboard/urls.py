from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/status/', views.api_status, name='api-status'),
    path('api/telemetry/', views.api_telemetry, name='api-telemetry'),
    path('api/incidents/', views.api_incidents, name='api-incidents'),
    path('api/rl-stats/', views.api_rl_stats, name='api-rl-stats'),
    path('api/xai/diagnosis/<int:incident_id>/', views.api_xai_diagnosis, name='api-xai-diagnosis'),
    path('api/xai/healing/<int:healing_id>/', views.api_xai_healing, name='api-xai-healing'),
    path('api/incidents/<int:incident_id>/approve/', views.api_approve_incident, name='api-approve-incident'),
    path('api/incidents/<int:incident_id>/reject/', views.api_reject_incident, name='api-reject-incident'),
    path('api/auth/login/', views.api_login, name='api-login'),
    path('api/auth/logout/', views.api_logout, name='api-logout'),
    path('api/auth/status/', views.api_auth_status, name='api-auth-status'),
]