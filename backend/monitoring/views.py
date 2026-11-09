"""
Monitoring views for NeuroSynapse.

Exposes:
    - health_check            GET  /api/health/
    - telemetry_ingest        GET  /api/telemetry/   (list)
                              POST /api/telemetry/   (ingest)
    - DeviceListCreateView    GET  /api/devices/     (list)
                              POST /api/devices/     (create, admin only)
    - DeviceDetailView        GET/PUT/PATCH/DELETE /api/devices/<id>/
    - inject_failure_api      POST /api/inject-failure/  (test-only)
"""

import json
import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics
from rest_framework.authentication import TokenAuthentication

from authentication.permissions import IsNetworkAdministrator
from monitoring.models import Device, Telemetry
from monitoring.serializers import DeviceSerializer, TelemetryIngestSerializer
from monitoring.connector import get_connector

logger = logging.getLogger('neurosynapse.monitoring')


def health_check(request):
    """
    Report API, database, and dedicated-model readiness.

    Returns:
        {
            "status": "healthy",
            "system": "NeuroSynapse API",
            "version": "0.1.0",
            "models_healthy": bool,
            "db_ok": bool,
        }
    """
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False

    try:
        from ai_engine.model_loader import models_healthy
        model_status = models_healthy()
    except Exception:
        model_status = False

    return JsonResponse({
        'status': 'healthy',
        'system': 'NeuroSynapse API',
        'version': '0.1.0',
        'models_healthy': model_status,
        'db_ok': db_ok,
    })


@csrf_exempt
def telemetry_ingest(request):
    """GET: Return telemetry for dashboard. POST: Ingest telemetry."""
    if request.method == 'GET':
        data = []
        for device in Device.objects.all():
            records = Telemetry.objects.filter(device=device)\
                        .order_by('-timestamp')[:20]

            device_records = []
            for t in records:
                interface_status = t.interface_status or {}

                # Extract metrics from JSON
                ospf_neighbors = 0
                error_count = 0
                if isinstance(interface_status, dict):
                    metrics = interface_status.get('__metrics__', {})
                    ospf_neighbors = metrics.get('ospf_neighbors', 0)
                    error_count = metrics.get('error_count', 0)

                device_records.append({
                    'timestamp': t.timestamp.isoformat(),
                    'cpu': t.cpu_usage,
                    'memory': t.memory_usage,
                    'packet_loss': t.packet_loss,
                    'latency_ms': t.latency_ms,
                    'bandwidth_util': t.bandwidth_util,
                    'interface_status': interface_status,
                    'ospf_neighbors': ospf_neighbors,
                    'error_count': error_count,
                })

            data.append({
                'device': device.name,
                'records': device_records,
            })

        return JsonResponse({'telemetry': data})

    # POST: ingest a single telemetry record.
    if request.method == 'POST':
        try:
            payload = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        serializer = TelemetryIngestSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {'error': 'Invalid telemetry payload', 'details': serializer.errors},
                status=400,
            )

        telemetry = serializer.save()
        return JsonResponse({
            'status': 'ingested',
            'telemetry_id': telemetry.id,
        }, status=201)

    return JsonResponse({'error': 'GET or POST required'}, status=405)


class DeviceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/devices/  - list all managed network devices.
    POST /api/devices/  - register a new managed network device
                           (ADMIN/SUPER_ADMIN only).
    """

    queryset = Device.objects.all().order_by('name')
    serializer_class = DeviceSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsNetworkAdministrator]
    pagination_class = None

    def perform_create(self, serializer):
        device = serializer.save()
        logger.info('[DEVICE] %s registered device %s (%s)',
                     self.request.user.username, device.name, device.ip_address)


class DeviceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/devices/<id>/ - manage a single device.
    """

    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsNetworkAdministrator]


@csrf_exempt
def inject_failure_api(request):
    """
    Test-only endpoint: inject a synthetic failure into the simulated device.

    Body (JSON):
        {
            "type": "ddos" | "service_crash" | "link_failure",
            ...optional context (source_ip, destination_port, etc.)
        }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    failure_type = body.get('type')
    if not failure_type:
        return JsonResponse({'error': 'Missing required field: type'}, status=400)

    device = Device.objects.filter(device_type='simulated').first()
    if not device:
        return JsonResponse({'error': 'No simulated device found'}, status=404)

    connector = get_connector(device)
    try:
        result = connector.inject_failure(
            failure_type,
            **{k: v for k, v in body.items() if k != 'type'},
        )
    except Exception as exc:
        logger.exception('[INJECT] Failure injection failed')
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'status': 'injected', 'result': result})