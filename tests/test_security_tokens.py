# tests/test_security_tokens.py
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_expired_token_rejected():
    expired = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.EXPIRED"
    headers = {"Authorization": expired}

    res = httpx.get(f"{BASE_URL}/api/incidents", headers=headers)
    assert res.status_code == 401

def test_malformed_token_rejected():
    malformed = "Bearer abc.def"
    headers = {"Authorization": malformed}

    res = httpx.get(f"{BASE_URL}/api/incidents", headers=headers)
    assert res.status_code == 401