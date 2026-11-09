"""
Dashboard API views.
"""

import logging
from django.http import FileResponse

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from authentication.permissions import IsNetworkAdministrator, IsSuperAdministrator
from monitoring.models import Device, HealingAction, Incident, RLPolicy, Telemetry
from monitoring.serializers import (
    HealingActionSerializer,
    IncidentListSerializer,
    IncidentSerializer,
    RLPolicySerializer,
)
from dashboard.models import HealingPolicyConfig
from dashboard.serializers import HealingPolicyConfigSerializer, ManualApprovalSerializer
from healing.logging_system.healing_logger import incident_log_path, write_incident_log

logger = logging.getLogger('neurosynapse.dashboard')

TERMINAL_STATUSES = ['HEALED', 'ROLLBACK', 'MONITORING']
OPEN_INCIDENT_STATUSES = [
    'ANOMALY_DETECTED',
    'MANUAL_REVIEW',
    'READY_FOR_ACTION',
    'SANDBOXING',
    'EXECUTION',
    'VERIFICATION',
]


class IncidentPagination(PageNumberPagination):
    """Pagination for incident list."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class DashboardSummaryView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device_status_counts = dict(
            Device.objects.values_list('status').annotate(count=Count('id'))
        )
        incident_status_counts = dict(
            Incident.objects.values_list('status').annotate(count=Count('id'))
        )
        open_incidents = Incident.objects.filter(status__in=OPEN_INCIDENT_STATUSES).count()

        recent_incidents = IncidentListSerializer(
            Incident.objects.all()[:10], many=True
        ).data
        recent_healing_actions = HealingActionSerializer(
            HealingAction.objects.all()[:10], many=True
        ).data

        latest_policy = RLPolicy.objects.order_by('-updated_at').first()

        return Response({
            'devices': {
                'total': Device.objects.count(),
                'by_status': device_status_counts,
            },
            'incidents': {
                'total': Incident.objects.count(),
                'open': open_incidents,
                'by_status': incident_status_counts,
            },
            'recent_incidents': recent_incidents,
            'recent_healing_actions': recent_healing_actions,
            'rl_performance': RLPolicySerializer(latest_policy).data if latest_policy else None,
            'telemetry_points_last_hour': Telemetry.objects.count(),
        })


class AlertsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        incidents = Incident.objects.filter(
            status__in=OPEN_INCIDENT_STATUSES
        ).order_by('-detected_at')
        return Response({
            'count': incidents.count(),
            'alerts': IncidentListSerializer(incidents, many=True).data,
        })


class IncidentListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Incident.objects.all()

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        failure_type_filter = request.query_params.get('failure_type')
        if failure_type_filter:
            queryset = queryset.filter(failure_type=failure_type_filter.upper())

        device_filter = request.query_params.get('device')
        if device_filter:
            queryset = queryset.filter(device_id=device_filter)

        # Pagination
        paginator = IncidentPagination()
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = IncidentListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback: return all (capped)
        return Response(IncidentListSerializer(queryset[:200], many=True).data)


class IncidentDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)
        data = IncidentSerializer(incident).data

        from ai_engine.xai import xai_engine

        telemetry = incident.telemetry_snapshot
        if telemetry is not None:
            data['xai_explanation'] = xai_engine.explain_diagnosis(
                telemetry, incident.failure_type, incident.confidence_score, incident=incident
            )
        else:
            data['xai_explanation'] = None

        return Response(data)


class IncidentLogView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)
        # Always regenerate rather than serving a cached file if one exists.
        # Manual approve/reject/rollback (see IncidentApprovalView,
        # ManualRollbackView) change the incident's status and healing
        # actions after the automated MAPE-K cycle already wrote a log --
        # if we only wrote on cache-miss, every download after a manual
        # action would silently serve the stale pre-approval/pre-rollback
        # version. Generation is cheap (pure Python + one small file
        # write), so there's no real cost to guaranteeing freshness here.
        path = write_incident_log(incident)
        return FileResponse(
            path.open('rb'),
            as_attachment=True,
            filename=path.name,
            content_type='text/plain',
        )


class HealingActionListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = HealingAction.objects.all()

        incident_filter = request.query_params.get('incident')
        if incident_filter:
            queryset = queryset.filter(incident_id=incident_filter)

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        return Response(HealingActionSerializer(queryset[:200], many=True).data)


class HealingActionDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        healing_action = get_object_or_404(HealingAction, pk=pk)
        data = HealingActionSerializer(healing_action).data

        from ai_engine.xai import xai_engine

        success = healing_action.status == 'EXECUTED'
        data['xai_explanation'] = xai_engine.explain_healing_action(
            healing_action.incident, healing_action, success
        )
        return Response(data)


class ManualApprovalView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsNetworkAdministrator]

    def post(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)

        if incident.status != 'MANUAL_REVIEW':
            return Response(
                {'error': f"Incident #{pk} is not awaiting manual review "
                           f"(current status: {incident.status})."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ManualApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data['approved']

        from ai_engine.orchestrator import orchestrator

        logger.info(
            '[HITL] Administrator %s %s incident #%s',
            request.user.username, 'approved' if approved else 'rejected', pk,
        )

        healing_action = orchestrator.process_manual_approval(pk, approved)
        incident.refresh_from_db()
        write_incident_log(incident, status=incident.status)

        return Response({
            'incident_id': incident.id,
            'incident_status': incident.status,
            'approved': approved,
            'healing_action': HealingActionSerializer(healing_action).data if healing_action else None,
        })


class ManualRollbackView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsNetworkAdministrator]

    def post(self, request, pk):
        incident = get_object_or_404(Incident, pk=pk)

        if incident.status not in ('HEALED', 'ROLLBACK'):
            return Response(
                {'error': f"Incident #{pk} cannot be rolled back (current: {incident.status}). "
                           f"Only HEALED incidents can be manually rolled back."},
                status=status.HTTP_409_CONFLICT,
            )

        from healing.actuator import actuator
        from django.utils import timezone

        # Figure 3.2: HEALED -> ROLLBACK -> MONITORING
        #
        # The actuator sets a terminal status of ROLLED_BACK by default
        # (needed for UC-07). For the API-driven rollback we want the
        # state machine's MONITORING terminal instead, so we request it
        # explicitly via the _rollback_target_status attribute.
        incident.status = 'ROLLBACK'
        incident.save(update_fields=['status'])

        incident._rollback_target_status = 'MONITORING'
        actuator.rollback(incident)

        # actuator.rollback() already persisted the target status, but be
        # explicit about resolved_at here in case it was already set.
        if incident.resolved_at is None:
            incident.resolved_at = timezone.now()
            incident.save(update_fields=['resolved_at'])

        incident.refresh_from_db()
        write_incident_log(incident, status=incident.status)

        logger.info(
            '[ROLLBACK] Administrator %s rolled back incident #%s -> %s',
            request.user.username, pk, incident.status,
        )

        return Response({
            'incident_id': incident.id,
            'incident_status': incident.status,
        })


class RLStatsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from ai_engine.rl_agent import rl_agent

        stats = rl_agent.get_stats()
        latest_policy = RLPolicy.objects.order_by('-updated_at').first()
        stats['policy'] = RLPolicySerializer(latest_policy).data if latest_policy else None
        return Response(stats)


class PolicyConfigView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdministrator]

    def get(self, request):
        config = HealingPolicyConfig.get_solo()
        return Response(HealingPolicyConfigSerializer(config).data)

    def put(self, request):
        config = HealingPolicyConfig.get_solo()
        serializer = HealingPolicyConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        logger.info('[POLICY] Administrator %s updated healing policy thresholds',
                     request.user.username)

        return Response(HealingPolicyConfigSerializer(config).data)