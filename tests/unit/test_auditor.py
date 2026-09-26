"""
AETHERIS AI — Auditor Agent Tests
Tests fail-closed behavior on malformed output, validation, and AuditResult.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from agents.auditor_agent import AuditorAgent, AuditResult, AuditRecommendation, _validate_audit_output


class TestAuditOutputValidation:
    def _valid_raw(self) -> dict:
        return {
            "security_risk": "LOW",
            "regression_risk": "LOW",
            "edge_cases": ["empty string user_id"],
            "performance_impact": "NEGLIGIBLE",
            "test_coverage_adequate": True,
            "recommendation": "APPROVE",
            "findings_summary": "Patch is safe.",
        }

    def test_valid_output_passes(self):
        result = _validate_audit_output(self._valid_raw())
        assert result["recommendation"] == "APPROVE"

    def test_missing_security_risk_raises(self):
        raw = self._valid_raw()
        del raw["security_risk"]
        with pytest.raises(ValueError, match="missing required fields"):
            _validate_audit_output(raw)

    def test_missing_recommendation_raises(self):
        raw = self._valid_raw()
        del raw["recommendation"]
        with pytest.raises(ValueError, match="missing required fields"):
            _validate_audit_output(raw)

    def test_invalid_security_risk_raises(self):
        raw = self._valid_raw()
        raw["security_risk"] = "VERY_BAD"
        with pytest.raises(ValueError, match="Invalid security_risk"):
            _validate_audit_output(raw)

    def test_invalid_recommendation_raises(self):
        raw = self._valid_raw()
        raw["recommendation"] = "PROCEED"
        with pytest.raises(ValueError, match="Invalid recommendation"):
            _validate_audit_output(raw)

    def test_non_list_edge_cases_raises(self):
        raw = self._valid_raw()
        raw["edge_cases"] = "a string not a list"
        with pytest.raises(ValueError, match="edge_cases"):
            _validate_audit_output(raw)

    def test_non_bool_test_coverage_raises(self):
        raw = self._valid_raw()
        raw["test_coverage_adequate"] = "yes"
        with pytest.raises(ValueError):
            _validate_audit_output(raw)

    def test_not_dict_raises(self):
        with pytest.raises(ValueError, match="not a dict"):
            _validate_audit_output(["not", "a", "dict"])


class TestAuditorAgentFailClosed:
    @pytest.mark.asyncio
    async def test_invalid_json_returns_untrusted(self):
        agent = AuditorAgent()
        with patch.object(agent.gateway, "generate", new=AsyncMock(return_value="not json at all")):
            result = await agent.audit(
                incident_id="INC-001",
                patch={"diff": "test"},
                diagnosis={"root_cause": "NPE"},
                test_results={"passed": 5},
                attempt_num=1,
            )
        assert result.trusted is False
        assert result.recommendation == AuditRecommendation.REJECT
        assert result.untrust_reason is not None

    @pytest.mark.asyncio
    async def test_missing_fields_returns_untrusted(self):
        agent = AuditorAgent()
        incomplete = json.dumps({"security_risk": "LOW"})  # missing required fields
        with patch.object(agent.gateway, "generate", new=AsyncMock(return_value=incomplete)):
            result = await agent.audit(
                incident_id="INC-001",
                patch={"diff": "test"},
                diagnosis={},
                test_results={},
                attempt_num=1,
            )
        assert result.trusted is False

    @pytest.mark.asyncio
    async def test_exception_returns_untrusted(self):
        agent = AuditorAgent()
        with patch.object(agent.gateway, "generate", new=AsyncMock(side_effect=Exception("network error"))):
            result = await agent.audit(
                incident_id="INC-001",
                patch={},
                diagnosis={},
                test_results={},
                attempt_num=1,
            )
        assert result.trusted is False
        assert "Unexpected audit error" in result.untrust_reason

    @pytest.mark.asyncio
    async def test_valid_response_returns_trusted(self):
        agent = AuditorAgent()
        valid_response = json.dumps({
            "security_risk": "LOW",
            "regression_risk": "LOW",
            "edge_cases": [],
            "performance_impact": "NEGLIGIBLE",
            "test_coverage_adequate": True,
            "recommendation": "APPROVE",
            "findings_summary": "All clear.",
        })
        with patch.object(agent.gateway, "generate", new=AsyncMock(return_value=valid_response)):
            result = await agent.audit(
                incident_id="INC-001",
                patch={"diff": "test"},
                diagnosis={},
                test_results={},
                attempt_num=1,
            )
        assert result.trusted is True
        assert result.recommendation == AuditRecommendation.APPROVE
