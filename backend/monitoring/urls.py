from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    path('telemetry/', views.telemetry_ingest, name='telemetry-ingest'),
    path('devices/', views.DeviceListCreateView.as_view(), name='device-list-create'),
    path('devices/<int:pk>/', views.DeviceDetailView.as_view(), name='device-detail'),
]
