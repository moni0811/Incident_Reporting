import datetime

class PolicyEngine:
    """
    The PolicyEngine enforces deterministic rules that override 
    probabilistic AI outputs to ensure safety and compliance.
    """

    def __init__(self):
        # Define high-danger keywords for the safety policy
        self.emergency_keywords = ["fire", "gas", "smoke", "explosion", "collapsed", "flood", "earthquake", "emergency"]

    def enforce_policies(self,description, ai_result):

        final_severity = ai_result.get("severity", "LOW")
        print('final_severity:', final_severity)
        needs_review = ai_result.get("needs_review", False)
        applied_polices = []

        # POLICY A: Safety Keyword Override (Hard Rule)
        # If danger words appear, it MUST be CRITICAL regardless of AI confidence.
        desc_lower = description.lower()
        if any(keyword in desc_lower for keyword in self.emergency_keywords):
            if final_severity != "CRITICAL":
                final_severity = "CRITICAL"
                needs_review = True  # Flag for human review due to override
                applied_polices.append("Safety Keyword Override")

        # POLICY B: Service Level Agreement (SLA) Assignment
        # Assign a resolution deadline based on final severity.
        deadline = self._calculate_sla(final_severity)
        applied_polices.append("SLA Assignment")
        
        # POLICY C: Confidence Guardrail (Redundancy)
        # If AI confidence is low, force a human review.
        if ai_result.get("confidence", 1.0) < 0.8:
            needs_review = True
            applied_polices.append("Low Confidence Override")
        print('final_severity:', final_severity)
        return {
            "severity": final_severity,
            "needs_review": needs_review,
            "deadline": deadline,
            "applied_policies": applied_polices
        }

    def _calculate_sla(self, severity):
        now = datetime.datetime.now()
        if severity == "CRITICAL":
            return (now + datetime.timedelta(hours=2)).isoformat()
        elif severity == "HIGH":
            return (now + datetime.timedelta(hours=4)).isoformat()
        elif severity == "MEDIUM":
            return (now + datetime.timedelta(hours=24)).isoformat()
        else:  # LOW
            return (now + datetime.timedelta(days=3)).isoformat()