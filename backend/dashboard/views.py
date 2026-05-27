"""Dashboard views for NeuroSynapse."""

from django.shortcuts import render
from django.http import JsonResponse
from monitoring.models import Device, Telemetry, Incident, HealingAction


def dashboard(request):
    """Main dashboard page."""
    return render(request, 'dashboard.html')


def api_status(request):
    """API endpoint returning current system status."""
    devices = Device.objects.all()
    latest_incidents = Incident.objects.order_by('-detected_at')[:10]
    recent_healings = HealingAction.objects.order_by('-created_at')[:10]
    
    device_data = []
    for device in devices:
        latest_telemetry = Telemetry.objects.filter(
            device=device
        ).order_by('-timestamp').first()
        
        # Determine health status
        if latest_telemetry:
            cpu = latest_telemetry.cpu_usage or 0
            packet_loss = latest_telemetry.packet_loss or 0
            
            if cpu > 80 or packet_loss > 50:
                health = 'CRITICAL'
            elif cpu > 60 or packet_loss > 10:
                health = 'WARNING'
            else:
                health = 'HEALTHY'
        else:
            health = 'UNKNOWN'
        
        device_data.append({
            'id': device.id,
            'name': device.name,
            'ip': device.ip_address,
            'status': health,
            'cpu': latest_telemetry.cpu_usage if latest_telemetry else None,
            'memory': latest_telemetry.memory_usage if latest_telemetry else None,
            'packet_loss': latest_telemetry.packet_loss if latest_telemetry else None,
            'last_seen': latest_telemetry.timestamp.isoformat() if latest_telemetry else None,
        })
    
    return JsonResponse({
        'devices': device_data,
        'incident_count': Incident.objects.count(),
        'open_incidents': Incident.objects.filter(
            status__in=['DETECTED', 'DIAGNOSING', 'READY_FOR_ACTION', 'HEALING', 'MANUAL_REVIEW']
        ).count(),
        'healed_today': Incident.objects.filter(status='HEALED').count(),
        'latest_incidents': [
            {
                'id': inc.id,
                'device': inc.device.name,
                'type': inc.get_failure_type_display(),
                'confidence': inc.confidence_score,
                'status': inc.get_status_display(),
                'detected_at': inc.detected_at.isoformat(),
            } for inc in latest_incidents
        ],
        'recent_healings': [
            {
                'id': h.id,
                'incident_id': h.incident_id,
                'action': h.get_action_type_display(),
                'status': h.get_status_display(),
                'created_at': h.created_at.isoformat(),
            } for h in recent_healings
        ],
    })


def api_telemetry(request):
    """API endpoint returning latest telemetry for all devices."""
    data = []
    for device in Device.objects.all():
        telemetry = Telemetry.objects.filter(
            device=device
        ).order_by('-timestamp')[:20]
        data.append({
            'device': device.name,
            'records': [
                {
                    'timestamp': t.timestamp.isoformat(),
                    'cpu': t.cpu_usage,
                    'memory': t.memory_usage,
                    'packet_loss': t.packet_loss,
                } for t in telemetry
            ]
        })
    return JsonResponse({'telemetry': data})


def api_incidents(request):
    """API endpoint returning all incidents."""
    incidents = Incident.objects.order_by('-detected_at')[:50]
    return JsonResponse({
        'incidents': [
            {
                'id': inc.id,
                'device': inc.device.name if inc.device else 'Unknown',
                'type': inc.get_failure_type_display(),
                'confidence': inc.confidence_score,
                'status': inc.get_status_display(),
                'detected_at': inc.detected_at.isoformat(),
                'resolved_at': inc.resolved_at.isoformat() if inc.resolved_at else None,
            } for inc in incidents
        ]
    })

def api_rl_stats(request):
    """API endpoint returning RL agent statistics."""
    from ai_engine.rl_agent import rl_agent
    stats = rl_agent.get_stats()
    return JsonResponse(stats)

def api_xai_diagnosis(request, incident_id):
    """API endpoint returning XAI explanation for a diagnosis."""
    from monitoring.models import Incident
    from ai_engine.xai import xai_engine
    
    try:
        incident = Incident.objects.get(id=incident_id)
        telemetry = incident.telemetry_snapshot
        
        if telemetry:
            explanation = xai_engine.explain_diagnosis(
                telemetry,
                incident.failure_type,
                incident.confidence_score
            )
        else:
            explanation = {
                'summary': 'No telemetry snapshot available for this incident.',
                'failure_type': incident.failure_type,
                'confidence': incident.confidence_score,
            }
        
        # Add incident metadata
        explanation['incident_id'] = incident.id
        explanation['device'] = incident.device.name if incident.device else 'Unknown'
        explanation['detected_at'] = incident.detected_at.isoformat()
        explanation['status'] = incident.get_status_display()
        
        return JsonResponse(explanation)
    except Incident.DoesNotExist:
        return JsonResponse({'error': 'Incident not found'}, status=404)


def api_xai_healing(request, healing_id):
    """API endpoint returning XAI explanation for a healing action."""
    from monitoring.models import HealingAction
    from ai_engine.xai import xai_engine
    
    try:
        healing = HealingAction.objects.get(id=healing_id)
        incident = healing.incident
        success = healing.status == 'EXECUTED'
        
        explanation = xai_engine.explain_healing_action(incident, healing, success)
        explanation['healing_id'] = healing.id
        explanation['incident_id'] = incident.id
        
        return JsonResponse(explanation)
    except HealingAction.DoesNotExist:
        return JsonResponse({'error': 'Healing action not found'}, status=404)


def api_analytics(request):
    """API endpoint returning analytics metrics."""
    from django.db.models import Avg, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Calculate MTTR (Mean Time To Resolution)
    healed_incidents = Incident.objects.filter(
        status='HEALED', 
        resolved_at__isnull=False
    ).exclude(detected_at__isnull=True)
    
    mttr_minutes = 0
    if healed_incidents.exists():
        time_diffs = [(i.resolved_at - i.detected_at).total_seconds() / 60 for i in healed_incidents]
        mttr_minutes = sum(time_diffs) / len(time_diffs)
    
    # Healing success rate
    total_incidents = Incident.objects.count()
    healed_count = Incident.objects.filter(status='HEALED').count()
    healing_success_rate = (healed_count / total_incidents) if total_incidents > 0 else 0
    
    # Average detection time (arbitrary mock - ideally computed from AI engine)
    avg_detection_time = 2.5  # seconds
    
    return JsonResponse({
        'mttr': mttr_minutes,
        'healing_success_rate': healing_success_rate,
        'avg_detection_time': avg_detection_time,
    })
