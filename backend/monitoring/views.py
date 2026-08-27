import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from rest_framework import generics
from rest_framework.authentication import TokenAuthentication

from authentication.permissions import IsNetworkAdministrator
from monitoring.models import Device, Telemetry
from monitoring.serializers import DeviceSerializer, TelemetryIngestSerializer

logger = logging.getLogger('neurosynapse.monitoring')


def health_check(request):
    """Simple health-check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'system': 'NeuroSynapse API',
        'version': '0.1.0',
    })


@csrf_exempt
def telemetry_ingest(request):
    """
    FR1: Telemetry Ingestion.
    GET  - returns recent telemetry per device (used by lightweight polling clients).
    POST - ingests one or more telemetry payloads, validated via
           TelemetryIngestSerializer (Reliability NFR: realistic value bounds).
    """
    # ---------- GET: Return telemetry data ----------
    if request.method == 'GET':
        data = []
        for device in Device.objects.all():
            records = Telemetry.objects.filter(device=device)\
                        .order_by('-timestamp')[:20]
            data.append({
                'device': device.name,
                'records': [
                    {
                        'timestamp': t.timestamp.isoformat(),
                        'cpu': t.cpu_usage,
                        'memory': t.memory_usage,
                        'packet_loss': t.packet_loss,
                    } for t in records
                ]
            })
        return JsonResponse({'telemetry': data})

    # ---------- POST: Ingest new telemetry ----------
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)

        records = body if isinstance(body, list) else [body]

        saved = 0
        errors = []
        for index, item in enumerate(records):
            serializer = TelemetryIngestSerializer(data=item)
            if not serializer.is_valid():
                errors.append({'index': index, 'errors': serializer.errors})
                logger.warning('[TELEMETRY] Rejected invalid payload #%s: %s', index, serializer.errors)
                continue

            validated = serializer.validated_data
            device_ip = validated.get('device_ip') or validated.get('ip_address')
            device = Device.objects.filter(ip_address=device_ip).first()
            if not device:
                device = Device.objects.create(
                    name=validated.get('name') or 'Unknown',
                    ip_address=device_ip,
                    status='ONLINE',
                )
                logger.info('[TELEMETRY] Auto-registered new device %s (%s)', device.name, device_ip)

            Telemetry.objects.create(
                device=device,
                cpu_usage=validated.get('cpu_usage'),
                memory_usage=validated.get('memory_usage'),
                packet_loss=validated.get('packet_loss'),
                latency_ms=validated.get('latency_ms'),
                bandwidth_util=validated.get('bandwidth_util'),
                interface_status=validated.get('interface_status'),
                raw_output=validated.get('raw_output', ''),
            )
            saved += 1

        status_code = 200 if saved else 400
        return JsonResponse(
            {'status': 'received', 'records': saved, 'errors': errors},
            status=status_code,
        )

    return JsonResponse({'error': 'Method not allowed'}, status=405)


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


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from monitoring.models import Device
from monitoring.connector import get_connector

@csrf_exempt
def inject_failure_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    body = json.loads(request.body)
    failure_type = body.get('type')
    
    device = Device.objects.filter(device_type='simulated').first()
    if not device:
        return JsonResponse({'error': 'No simulated device found'}, status=404)
    
    connector = get_connector(device)
    result = connector.inject_failure(failure_type, **{k: v for k, v in body.items() if k != 'type'})
    
    return JsonResponse({'status': 'injected', 'result': result})