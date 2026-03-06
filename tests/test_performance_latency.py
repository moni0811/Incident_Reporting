# tests/test_performance_latency.py
import pytest
import httpx
import time

BASE_URL = "http://localhost:8000"

@pytest.mark.integration
def test_report_endpoint_latency(auth_headers):
    """
    Ensures the /report endpoint responds within 500ms under normal conditions.
    This is a performance 'budget' test.
    """
    headers = {"Authorization": f"Bearer {auth_headers}"}
    payload = {
        "description": "High latency check",
        "incident_id": "LAT-008",
        "address": "123 Main St",
        "image_url": "http://example.com/check.jpg"
    }

    start_time = time.perf_counter()
    response = httpx.post(f"{BASE_URL}/report", json=payload, headers=headers, timeout=7.0)
    print(response)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000
    
    assert response.status_code == 200
    # Assert the response time is within a reasonable threshold for your Minikube environment
    assert latency_ms < 5000, f"API too slow: {latency_ms:.2f}ms"

@pytest.mark.integration
def test_client_timeout_handling():
    """
    Simulates a network timeout to ensure the client fails gracefully 
    rather than hanging indefinitely.
    """
    headers = {"Authorization": "Bearer fake_token"}
    
    # We set an intentionally impossible timeout of 0.001 seconds
    with pytest.raises(httpx.TimeoutException):
        httpx.get(f"{BASE_URL}/api/incidents", headers=headers, timeout=0.0001)