from django.test import Client


def test_health_endpoint_reports_dependencies():
    response = Client().get('/api/health/')
    assert response.status_code == 200
    payload = response.json()
    assert payload['models_healthy'] is True
    assert payload['db_ok'] is True
