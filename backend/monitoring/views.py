from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from monitoring.models import Device, Telemetry


def health_check(request):
    """Simple health-check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'system': 'NeuroSynapse API',
        'version': '0.1.0',
    })


@csrf_exempt
def telemetry_ingest(request):
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
        body = json.loads(request.body)
        if isinstance(body, list):
            records = body
        else:
            records = [body]

        count = 0
        for item in records:
            device_ip = item.get('device_ip') or item.get('ip_address')
            device = Device.objects.filter(ip_address=device_ip).first()
            if not device:
                device = Device.objects.create(
                    name=item.get('name', 'Unknown'),
                    ip_address=device_ip,
                    status='ONLINE'
                )
            Telemetry.objects.create(
                device=device,
                cpu_usage=item.get('cpu_usage'),
                memory_usage=item.get('memory_usage'),
                packet_loss=item.get('packet_loss'),
                latency_ms=item.get('latency_ms'),
                interface_status=item.get('interface_status'),
                raw_output=item.get('raw_output', ''),
            )
            count += 1

        return JsonResponse({'status': 'received', 'records': count})

    return JsonResponse({'error': 'Method not allowed'}, status=405)