"""
AETHERIS AI — ChaosAgent Tests
Tests bounded fault injection and taxonomy enforcement.
"""
import pytest
from agents.chaos_agent import (
    ChaosAgent,
    APPROVED_INCIDENT_CATEGORIES,
    APPROVED_SERVICES,
)


class TestChaosAgentBoundaries:
    def setup_method(self):
        self.agent = ChaosAgent()

    def test_generates_fault_for_valid_category(self):
        for cat in APPROVED_INCIDENT_CATEGORIES:
            fault = self.agent.generate_fault(category=cat, service="orders-service", seed=42)
            assert fault["category"] == cat
            assert fault["bounded"] is True
            assert fault["arbitrary_code"] is False

    def test_rejects_unknown_category(self):
        with pytest.raises(ValueError, match="not in the approved taxonomy"):
            self.agent.generate_fault(category="ARBITRARY_EXPLOIT")

    def test_rejects_unknown_service(self):
        with pytest.raises(ValueError, match="not in the approved service list"):
            self.agent.generate_fault(service="admin-service")

    def test_fault_has_required_fields(self):
        fault = self.agent.generate_fault(seed=1)
        required = {"fault_id", "category", "service", "severity", "description",
                    "error_rate_percent", "bounded", "arbitrary_code"}
        assert required.issubset(set(fault.keys()))

    def test_fault_never_contains_executable_code(self):
        for cat in APPROVED_INCIDENT_CATEGORIES:
            fault = self.agent.generate_fault(category=cat, seed=99)
            assert fault["arbitrary_code"] is False
            # Ensure no exec/eval/import in description
            desc = fault.get("description", "")
            assert "exec(" not in desc
            assert "eval(" not in desc
            assert "__import__" not in desc

    def test_deterministic_with_seed(self):
        f1 = self.agent.generate_fault(seed=42)
        f2 = self.agent.generate_fault(seed=42)
        assert f1["category"] == f2["category"]
        assert f1["service"]  == f2["service"]

    def test_all_approved_services_valid(self):
        for svc in APPROVED_SERVICES:
            fault = self.agent.generate_fault(service=svc, seed=10)
            assert fault["service"] == svc
