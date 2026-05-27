from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


def health_check(request):
    """Simple endpoint to verify the API is running"""
    return JsonResponse({
        'status': 'healthy',
        'system': 'NeuroSynapse API',
        'version': '0.1.0',
    })


@csrf_exempt
def telemetry_ingest(request):
    """Endpoint to receive telemetry data"""
    if request.method == 'POST':
        data = json.loads(request.body)
        return JsonResponse({
            'status': 'received',
            'records': len(data) if isinstance(data, list) else 1,
        })
    return JsonResponse({'error': 'POST required'}, status=405)