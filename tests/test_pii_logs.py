import pytest
import httpx
import re
import time

BASE_URL = "http://localhost:8000"

PHONE_REGEX = r"\b\d{3}[-.]?\d{4}\b"

@pytest.mark.integration
def test_no_pii_in_logs(auth_headers):

    headers = auth_headers

    payload = {
        "incident_id": "TEST_022",
        "description": "Call me at 555-0199",
        "address": "123 Main St, Springfield, 94112",
        "image_url": "http://example.com/incident.jpg" # Required by schema
    }

    res = httpx.post(f"{BASE_URL}/report", json=payload, headers=headers)

    assert res.status_code == 200
    incident_id = res.json()["incident_id"]

    time.sleep(2)

    response = httpx.get(f"{BASE_URL}/api/incidents", headers=headers)

    assert response.status_code == 200

    incidents = response.json()

    incident = next((i for i in incidents if i["incident_id"] == incident_id), None)

    assert incident is not None
    assert not re.search(PHONE_REGEX, incident["description"])
    assert "[REDACTED_PHONE]" in incident["description"]