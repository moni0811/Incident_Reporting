"""
Tests for PolicyEngine — deterministic safety and compliance rules.

Run with:
    pip install pytest
    pytest 05_tests/tests/test_policy_engine.py -v
"""

import pytest
import datetime
from triage_agent.policy_engine import PolicyEngine

pytestmark = pytest.mark.unit

@pytest.fixture
def engine():
    return PolicyEngine()


# ─────────────────────────────────────────────
# POLICY A: Safety Keyword Override
# ─────────────────────────────────────────────
class TestSafetyKeywordOverride:

    def test_fire_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="There is a fire on the third floor",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_gas_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Strong gas smell coming from the basement",
            ai_result={"severity": "MEDIUM", "confidence": 0.85}
        )
        assert result["severity"] == "CRITICAL"

    def test_explosion_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Explosion heard near the parking lot",
            ai_result={"severity": "HIGH", "confidence": 0.88}
        )
        assert result["severity"] == "CRITICAL"

    def test_flood_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Street flood blocking entire road",
            ai_result={"severity": "MEDIUM", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_smoke_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Heavy smoke coming from the building",
            ai_result={"severity": "LOW", "confidence": 0.95}
        )
        assert result["severity"] == "CRITICAL"

    def test_earthquake_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="earthquake damage reported on 5th ave",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_collapsed_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Wall collapsed onto the sidewalk",
            ai_result={"severity": "MEDIUM", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_emergency_keyword_forces_critical(self, engine):
        result = engine.enforce_policies(
            description="Emergency situation at the school entrance",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_keyword_override_sets_needs_review(self, engine):
        """Safety override must always flag for human review."""
        result = engine.enforce_policies(
            description="fire spotted near trash cans",
            ai_result={"severity": "LOW", "confidence": 0.95}
        )
        assert result["needs_review"] is True

    def test_keyword_override_logs_applied_policy(self, engine):
        result = engine.enforce_policies(
            description="gas leak reported",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert "Safety Keyword Override" in result["applied_policies"]

    def test_already_critical_ai_no_duplicate_override(self, engine):
        """If AI already said CRITICAL, no override should be added."""
        result = engine.enforce_policies(
            description="fire in the building",
            ai_result={"severity": "CRITICAL", "confidence": 0.95}
        )
        assert "Safety Keyword Override" not in result["applied_policies"]

    def test_keyword_case_insensitive(self, engine):
        """Keywords must be caught regardless of casing."""
        result = engine.enforce_policies(
            description="FIRE on the rooftop",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert result["severity"] == "CRITICAL"

    def test_no_keyword_preserves_ai_severity(self, engine):
        """Non-emergency descriptions should keep AI severity."""
        result = engine.enforce_policies(
            description="Graffiti on the park bench",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert result["severity"] == "LOW"


# ─────────────────────────────────────────────
# POLICY B: SLA Assignment
# ─────────────────────────────────────────────
class TestSLAAssignment:

    def test_sla_always_assigned(self, engine):
        result = engine.enforce_policies(
            description="Broken streetlight",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert "SLA Assignment" in result["applied_policies"]
        assert result["deadline"] is not None

    def test_critical_sla_is_2_hours(self, engine):
        before = datetime.datetime.now()
        result = engine.enforce_policies(
            description="fire reported",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        deadline = datetime.datetime.fromisoformat(result["deadline"])
        diff = deadline - before
        assert 1.9 * 3600 < diff.total_seconds() < 2.1 * 3600

    def test_high_sla_is_4_hours(self, engine):
        before = datetime.datetime.now()
        result = engine.enforce_policies(
            description="Large pothole blocking lane",
            ai_result={"severity": "HIGH", "confidence": 0.9}
        )
        deadline = datetime.datetime.fromisoformat(result["deadline"])
        diff = deadline - before
        assert 3.9 * 3600 < diff.total_seconds() < 4.1 * 3600

    def test_medium_sla_is_24_hours(self, engine):
        before = datetime.datetime.now()
        result = engine.enforce_policies(
            description="Broken park bench",
            ai_result={"severity": "MEDIUM", "confidence": 0.9}
        )
        deadline = datetime.datetime.fromisoformat(result["deadline"])
        diff = deadline - before
        assert 23.9 * 3600 < diff.total_seconds() < 24.1 * 3600

    def test_low_sla_is_3_days(self, engine):
        before = datetime.datetime.now()
        result = engine.enforce_policies(
            description="Faded road marking",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        deadline = datetime.datetime.fromisoformat(result["deadline"])
        diff = deadline - before
        assert 2.9 * 86400 < diff.total_seconds() < 3.1 * 86400

    def test_deadline_is_valid_iso_format(self, engine):
        result = engine.enforce_policies(
            description="Noise complaint",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        # Should not raise
        datetime.datetime.fromisoformat(result["deadline"])

    def test_deadline_is_in_the_future(self, engine):
        result = engine.enforce_policies(
            description="Broken hydrant",
            ai_result={"severity": "MEDIUM", "confidence": 0.9}
        )
        deadline = datetime.datetime.fromisoformat(result["deadline"])
        assert deadline > datetime.datetime.now()


# ─────────────────────────────────────────────
# POLICY C: Confidence Guardrail
# ─────────────────────────────────────────────
class TestConfidenceGuardrail:

    def test_low_confidence_flags_review(self, engine):
        result = engine.enforce_policies(
            description="Some ambiguous complaint",
            ai_result={"severity": "LOW", "confidence": 0.5}
        )
        assert result["needs_review"] is True

    def test_confidence_exactly_at_threshold_flags_review(self, engine):
        """confidence = 0.79 should trigger the guardrail."""
        result = engine.enforce_policies(
            description="Complaint",
            ai_result={"severity": "LOW", "confidence": 0.79}
        )
        assert result["needs_review"] is True

    def test_confidence_at_0_8_does_not_flag(self, engine):
        """confidence = 0.8 is NOT below threshold — should not flag."""
        result = engine.enforce_policies(
            description="Graffiti on wall",
            ai_result={"severity": "LOW", "confidence": 0.8}
        )
        assert "Low Confidence Override" not in result["applied_policies"]

    def test_high_confidence_no_review(self, engine):
        result = engine.enforce_policies(
            description="Broken traffic light",
            ai_result={"severity": "MEDIUM", "confidence": 0.95}
        )
        assert "Low Confidence Override" not in result["applied_policies"]

    def test_low_confidence_logs_applied_policy(self, engine):
        result = engine.enforce_policies(
            description="Unclear complaint",
            ai_result={"severity": "LOW", "confidence": 0.6}
        )
        assert "Low Confidence Override" in result["applied_policies"]

    def test_low_confidence_preserves_severity(self, engine):
        """Low confidence should flag review but NOT change severity."""
        result = engine.enforce_policies(
            description="Minor pothole",
            ai_result={"severity": "MEDIUM", "confidence": 0.5}
        )
        assert result["severity"] == "MEDIUM"


# ─────────────────────────────────────────────
# Combined / Edge Cases
# ─────────────────────────────────────────────
class TestCombinedPolicies:

    def test_keyword_and_low_confidence_both_apply(self, engine):
        """Both Safety Override and Confidence Guardrail can fire together."""
        result = engine.enforce_policies(
            description="Possible gas smell not sure",
            ai_result={"severity": "LOW", "confidence": 0.5}
        )
        assert result["severity"] == "CRITICAL"
        assert result["needs_review"] is True
        assert "Safety Keyword Override" in result["applied_policies"]
        assert "Low Confidence Override" in result["applied_policies"]

    def test_sla_always_present_in_applied_policies(self, engine):
        """SLA Assignment should appear in every single result."""
        descriptions = [
            ("fire in building", {"severity": "LOW", "confidence": 0.9}),
            ("graffiti on wall", {"severity": "LOW", "confidence": 0.9}),
            ("broken bench", {"severity": "MEDIUM", "confidence": 0.5}),
        ]
        for desc, ai in descriptions:
            result = engine.enforce_policies(description=desc, ai_result=ai)
            assert "SLA Assignment" in result["applied_policies"], f"SLA missing for: {desc}"

    def test_result_always_has_required_keys(self, engine):
        """Every result must contain these 4 keys."""
        result = engine.enforce_policies(
            description="Any complaint",
            ai_result={"severity": "LOW", "confidence": 0.9}
        )
        assert "severity" in result
        assert "needs_review" in result
        assert "deadline" in result
        assert "applied_policies" in result

    def test_missing_confidence_defaults_to_no_flag(self, engine):
        """If AI result has no confidence key, should default to 1.0 (no flag)."""
        result = engine.enforce_policies(
            description="Broken streetlight",
            ai_result={"severity": "LOW"}
        )
        assert "Low Confidence Override" not in result["applied_policies"]

    def test_missing_severity_defaults_to_low(self, engine):
        """If AI result has no severity key, should default to LOW."""
        result = engine.enforce_policies(
            description="Minor issue",
            ai_result={"confidence": 0.9}
        )
        assert result["severity"] == "LOW"

    def test_all_emergency_keywords_covered(self, engine):
        """Every keyword in the list must trigger an override."""
        keywords = ["fire", "gas", "smoke", "explosion", "collapsed",
                    "flood", "earthquake", "emergency"]
        for keyword in keywords:
            result = engine.enforce_policies(
                description=f"There is a {keyword} situation",
                ai_result={"severity": "LOW", "confidence": 0.9}
            )
            assert result["severity"] == "CRITICAL", f"Keyword '{keyword}' did not trigger override"
