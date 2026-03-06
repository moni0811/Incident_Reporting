import pytest
import httpx
import os
import time

BASE_URL = os.getenv("APP_URL", "http://localhost:8000")

@pytest.fixture(scope="session")
def api_client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client

@pytest.fixture(scope="session")
def auth_headers(api_client):
    try:
        payload = {"username": "admin", "password": "admin@1234"}
        response = api_client.post("/token", data=payload)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    except Exception as e:
        pytest.fail(f"API unreachable at {BASE_URL}. Run port-forward first.")

@pytest.fixture
def wait_for_status():
    def _wait(client, incident_id, headers, target_status="processed", timeout=12):
        start = time.time()
        while time.time() - start < timeout:
            r = client.get(f"/api/incidents/{incident_id}", headers=headers)
            print("response:",r.status_code,r.json().get("status") )
            if r.status_code == 200 and r.json().get("status") == target_status:
                return r.json()
            time.sleep(0.5)
        raise TimeoutError(f"Incident {incident_id} timed out.")
    return _wait