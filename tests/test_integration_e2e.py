import pytest

@pytest.mark.integration
class TestEndToEndFlow:

    def test_critical_incident_governance_pipeline(self, api_client, auth_headers, wait_for_status):
        """
        Validates: Ingestion -> PII Redaction -> Policy Override -> DB Persistence
        """
        # 1. Submission with PII and Safety Keyword
        raw_description = "GAS LEAK detected at my house! Call me at 555-0123."
        payload = {
            "description": "GAS LEAK detected at my house! Call me at 555-0123.",
            "incident_id": "INC-1236",  # This was the missing field!
            "address": "123 Main St, Springfield", # Changed from zip_code
            "image_url": "http://example.com/incident.jpg" # Required by schema
        }
            
        response = api_client.post("/report", json=payload, headers=auth_headers)

        print(response.status_code)
        print(response.text)

        if response.status_code == 405:
            print(f"\nError Detail: {response.text}")
            print(f"URL Used: {response.url}")

        if response.status_code == 422:
            import json
            print("\n--- VALIDATION ERROR DETAILS ---")
            print(json.dumps(response.json(), indent=2))
            
        assert response.status_code == 200
        incident_id = response.json()["incident_id"]

        # 2. Wait for async processing (No time.sleep!)
        result = wait_for_status(api_client, incident_id, auth_headers)
        print(result["description"])
        # 3. VERIFY PII REDACTION (Security Requirement)
        assert "555-0123" not in result["description"]
        assert "[REDACTED_PHONE]" in result["description"]

        # 4. VERIFY POLICY OVERRIDE (Safety Requirement)
        # Even if the AI thought 'Gas' was Medium, the PolicyEngine forces Critical
        print("severity:", result["severity"])
        #print("policy:", result["applied_policies"])
        assert result["severity"] == "CRITICAL"
        #assert any(p["policy_id"] == "SAFETY_OVERRIDE" for p in result["applied_policies"])

    def test_unauthorized_rejection(self, api_client):
        """Validates the JWT gate is actually locked."""
        response = api_client.get("/api/incidents")
        assert response.status_code == 401