# tests/test_policy_idempotence.py
import pytest
from triage_agent.policy_engine import PolicyEngine

def test_policy_engine_idempotent():
    engine = PolicyEngine()

    desc = "gas smell in basement"
    ai = {"severity": "LOW", "confidence": 0.5}

    first = engine.enforce_policies(desc, ai)
    second = engine.enforce_policies(desc, ai)

    assert first["applied_policies"] == second["applied_policies"]
    assert len(second["applied_policies"]) == len(set(second["applied_policies"]))