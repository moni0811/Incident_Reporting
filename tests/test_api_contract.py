# tests/test_api_contract.py
import pytest
import httpx

BASE_URL = "http://localhost:8000"

@pytest.mark.contract
def test_incident_schema(auth_headers):
    """Validate the API contract for /api/incidents/{id}."""
    headers = {"Authorization": f"Bearer {auth_headers}"}

    # Create an incident
    payload = {
            "description": "GAS LEAK detected at my house!",
            "incident_id": "INC-12370",  # This was the missing field!
            "address": "123 Main St, Springfield", # Changed from zip_code
            "image_url": "http://example.com/incident.jpg" # Required by schema
        }
    res = httpx.post(f"{BASE_URL}/report", json=payload, headers=auth_headers)
    print("1st response :", res)
    incident_id = res.json()["incident_id"]
    print("incident_id:",incident_id)

    # Fetch it
    res = httpx.get(f"{BASE_URL}/api/incidents/{incident_id}", headers=auth_headers)
    print('res:', res)
    data = res.json()
    print('data:',data)

    required_keys = {
        "incident_id",
        "description",
        "severity",
        "needs_review",
        "policies_applied",
        "deadline",
        "status",
        "created_at",
    }

    assert required_keys.issubset(data.keys()), f"Missing keys: {required_keys - data.keys()}"
    #assert isinstance(data["policies_applied"], list)
    assert isinstance(data["needs_review"], bool)