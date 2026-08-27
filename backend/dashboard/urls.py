from django.urls import path

from dashboard import views

urlpatterns = [
    path('summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('alerts/', views.AlertsView.as_view(), name='dashboard-alerts'),
    path('incidents/', views.IncidentListView.as_view(), name='incident-list'),
    path('incidents/<int:pk>/', views.IncidentDetailView.as_view(), name='incident-detail'),
    path('incidents/<int:pk>/approve/', views.ManualApprovalView.as_view(), name='incident-approve'),
    path('incidents/<int:pk>/rollback/', views.ManualRollbackView.as_view(), name='incident-rollback'),
    path('healing-actions/', views.HealingActionListView.as_view(), name='healing-action-list'),
    path('healing-actions/<int:pk>/', views.HealingActionDetailView.as_view(), name='healing-action-detail'),
    path('rl-stats/', views.RLStatsView.as_view(), name='rl-stats'),
    path('policy/', views.PolicyConfigView.as_view(), name='policy-config'),
]