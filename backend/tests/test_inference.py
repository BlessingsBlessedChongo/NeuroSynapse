from ai_engine.model_loader import CANONICAL, models_healthy, predict_all


def test_dedicated_models_load_and_predict():
    assert models_healthy()
    result = predict_all({key: 0.0 for key in CANONICAL})
    assert result['fault_type'] in {'manual_review', 'ddos', 'link_failure', 'service_crash'}
    assert 0.0 <= result['confidence'] <= 1.0


def test_feature_contract_is_stable():
    assert CANONICAL == [
        'cpu_usage', 'memory_usage', 'latency_ms', 'packet_loss',
        'interface_up_count', 'bandwidth_util', 'error_count', 'ospf_neighbors',
    ]
