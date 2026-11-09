from django.urls import path
from dashboard.views import IncidentLogView
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    # This used to point at views.incident_log_download, a plain Django
    # view that checked request.user.is_authenticated. That only resolves
    # via session cookies (django.contrib.auth.middleware), never via the
    # Authorization: Token <key> header the frontend actually sends (DRF
    # TokenAuthentication is a DRF-view-only concern) -- so this endpoint
    # returned 401 "Authentication credentials were not provided." on
    # every single request regardless of a valid token, and the
    # download-log button never worked. dashboard.views.IncidentLogView
    # already does this correctly (DRF TokenAuthentication +
    # IsAuthenticated), so route here to that instead of maintaining two
    # competing implementations.
    path('incidents/<int:pk>/log/', IncidentLogView.as_view(), name='incident-log-download'),
    path('telemetry/', views.telemetry_ingest, name='telemetry-ingest'),
    path('devices/', views.DeviceListCreateView.as_view(), name='device-list-create'),
    path('devices/<int:pk>/', views.DeviceDetailView.as_view(), name='device-detail'),
]
