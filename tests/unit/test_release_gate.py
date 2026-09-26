"""
AETHERIS AI — Deterministic Release Gate Tests
Tests all threshold checks, fail-closed behavior, and override scenarios.
"""
import pytest
from orchestration.release_gate import (
    DeterministicReleaseGate,
    GateResult,
    RISK_ORDER,
)


class TestReleaseGatePass:
    def _gate(self):
        return DeterministicReleaseGate()

    def _default_pass_kwargs(self):
        return dict(
            test_pass_rate=0.98,
            audit_trusted=True,
            audit_security_risk="LOW",
            audit_regression_risk="LOW",
            audit_recommendation="APPROVE",
            test_coverage_adequate=True,
        )

    def test_all_green_passes(self):
        result = self._gate().evaluate(**self._default_pass_kwargs())
        assert result.passed is True

    def test_pass_rate_exactly_at_threshold_passes(self):
        kwargs = self._default_pass_kwargs()
        kwargs["test_pass_rate"] = 0.95
        result = self._gate().evaluate(**kwargs)
        assert result.passed is True

    def test_medium_security_risk_passes(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_security_risk"] = "MEDIUM"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is True

    def test_gate_result_has_all_checks(self):
        result = self._gate().evaluate(**self._default_pass_kwargs())
        check_names = {c.name for c in result.checks}
        assert "test_pass_rate" in check_names
        assert "security_risk" in check_names
        assert "regression_risk" in check_names
        assert "audit_trusted" in check_names


class TestReleaseGateFail:
    def _gate(self):
        return DeterministicReleaseGate()

    def _default_pass_kwargs(self):
        return dict(
            test_pass_rate=0.98,
            audit_trusted=True,
            audit_security_risk="LOW",
            audit_regression_risk="LOW",
            audit_recommendation="APPROVE",
            test_coverage_adequate=True,
        )

    def test_low_pass_rate_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["test_pass_rate"] = 0.80
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False
        assert any(c.name == "test_pass_rate" and not c.passed for c in result.checks)

    def test_untrusted_audit_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_trusted"] = False
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_high_security_risk_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_security_risk"] = "HIGH"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_critical_security_risk_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_security_risk"] = "CRITICAL"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_high_regression_risk_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_regression_risk"] = "HIGH"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_reject_recommendation_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_recommendation"] = "REJECT"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_escalate_recommendation_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["audit_recommendation"] = "ESCALATE"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_inadequate_test_coverage_fails(self):
        kwargs = self._default_pass_kwargs()
        kwargs["test_coverage_adequate"] = False
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_unknown_risk_treated_as_worst_case(self):
        """UNKNOWN risk must be treated as worst-case — not as 0."""
        kwargs = self._default_pass_kwargs()
        kwargs["audit_security_risk"] = "UNKNOWN"
        result = self._gate().evaluate(**kwargs)
        assert result.passed is False

    def test_gate_to_dict_structure(self):
        result = self._gate().evaluate(**self._default_pass_kwargs())
        d = result.to_dict()
        assert "passed" in d
        assert "checks" in d
        assert "failed_checks" in d


class TestRiskOrder:
    def test_low_lt_medium(self):
        assert RISK_ORDER["LOW"] < RISK_ORDER["MEDIUM"]

    def test_medium_lt_high(self):
        assert RISK_ORDER["MEDIUM"] < RISK_ORDER["HIGH"]

    def test_high_lt_critical(self):
        assert RISK_ORDER["HIGH"] < RISK_ORDER["CRITICAL"]

    def test_unknown_is_worst(self):
        assert RISK_ORDER["UNKNOWN"] > RISK_ORDER["CRITICAL"]
