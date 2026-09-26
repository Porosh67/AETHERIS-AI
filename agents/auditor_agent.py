"""
AETHERIS AI — AuditorAgent

Reviews a generated patch and returns structured risk findings.
CRITICAL: Malformed/missing auditor output → AUDIT_UNTRUSTED → NO ROLLOUT.
System fails closed — never converts invalid output to "score = 0".
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger("aetheris.agent.auditor")

RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_REQUIRED_AUDIT_FIELDS = {
    "security_risk",
    "regression_risk",
    "edge_cases",
    "performance_impact",
    "test_coverage_adequate",
    "recommendation",
    "findings_summary",
}


class AuditRecommendation(str, Enum):
    APPROVE  = "APPROVE"
    REJECT   = "REJECT"
    ESCALATE = "ESCALATE"


@dataclass
class AuditResult:
    trusted: bool
    security_risk: str
    regression_risk: str
    edge_cases: list[str]
    performance_impact: str
    test_coverage_adequate: bool
    recommendation: AuditRecommendation
    findings_summary: str
    raw: dict
    untrust_reason: str | None = None


def _validate_audit_output(raw: Any) -> dict:
    """
    Validate auditor output structure.
    FAIL CLOSED: Any missing field raises ValueError.
    Never silently converts malformed output into an approval.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Audit output is not a dict: {type(raw)}")

    missing = _REQUIRED_AUDIT_FIELDS - set(raw.keys())
    if missing:
        raise ValueError(f"Audit output missing required fields: {missing}")

    risk = raw.get("security_risk", "")
    if risk not in RISK_LEVELS:
        raise ValueError(f"Invalid security_risk '{risk}'. Must be one of {RISK_LEVELS}")

    reg = raw.get("regression_risk", "")
    if reg not in RISK_LEVELS:
        raise ValueError(f"Invalid regression_risk '{reg}'. Must be one of {RISK_LEVELS}")

    rec = raw.get("recommendation", "")
    if rec not in {r.value for r in AuditRecommendation}:
        raise ValueError(f"Invalid recommendation '{rec}'. Must be APPROVE/REJECT/ESCALATE")

    if not isinstance(raw.get("edge_cases"), list):
        raise ValueError("'edge_cases' must be a list")

    if not isinstance(raw.get("test_coverage_adequate"), bool):
        raise ValueError("'test_coverage_adequate' must be a boolean")

    return raw


class AuditorAgent(BaseAgent):
    """
    Audits a generated patch for security, regression, and quality risk.
    Returns AuditResult. If LLM output is malformed, trusted=False.
    """

    def __init__(self):
        super().__init__("AuditorAgent")

    async def audit(
        self,
        *,
        incident_id: str,
        patch: dict,
        diagnosis: dict,
        test_results: dict,
        attempt_num: int = 1,
    ) -> AuditResult:
        """
        Run audit on patch + test results.
        If output is invalid → returns AuditResult(trusted=False) — AUDIT_UNTRUSTED.
        """
        self._log(f"Auditing patch for {incident_id} (attempt {attempt_num})")

        prompt = self._build_prompt(
            incident_id=incident_id,
            patch=patch,
            diagnosis=diagnosis,
            test_results=test_results,
            attempt_num=attempt_num,
        )

        try:
            raw_text = await self.gateway.generate(prompt, max_tokens=600, context="audit")
            raw_json = json.loads(raw_text)
            validated = _validate_audit_output(raw_json)

            result = AuditResult(
                trusted=True,
                security_risk=validated["security_risk"],
                regression_risk=validated["regression_risk"],
                edge_cases=validated["edge_cases"],
                performance_impact=validated["performance_impact"],
                test_coverage_adequate=bool(validated["test_coverage_adequate"]),
                recommendation=AuditRecommendation(validated["recommendation"]),
                findings_summary=validated["findings_summary"],
                raw=validated,
            )
            self._log(
                f"Audit complete. security_risk={result.security_risk}, "
                f"regression_risk={result.regression_risk}, "
                f"recommendation={result.recommendation.value}"
            )
            return result

        except json.JSONDecodeError as e:
            reason = f"Audit response was not valid JSON: {e}"
        except ValueError as e:
            reason = f"Audit output validation failed: {e}"
        except Exception as e:
            reason = f"Unexpected audit error: {e}"

        # ── FAIL CLOSED ────────────────────────────────────────────────
        logger.error(f"[AuditorAgent] AUDIT_UNTRUSTED — {reason}")
        return AuditResult(
            trusted=False,
            security_risk="UNKNOWN",
            regression_risk="UNKNOWN",
            edge_cases=[],
            performance_impact="UNKNOWN",
            test_coverage_adequate=False,
            recommendation=AuditRecommendation.REJECT,
            findings_summary="Audit output was untrusted — failing closed. No rollout.",
            raw={},
            untrust_reason=reason,
        )

    def _build_prompt(
        self,
        *,
        incident_id: str,
        patch: dict,
        diagnosis: dict,
        test_results: dict,
        attempt_num: int,
    ) -> str:
        return f"""You are a senior security and reliability auditor reviewing an emergency patch.

Incident ID: {incident_id}
Attempt: {attempt_num}

Patch:
{json.dumps(patch, indent=2)}

Diagnosis:
{json.dumps(diagnosis, indent=2)}

Test Results:
{json.dumps(test_results, indent=2)}

Respond with ONLY valid JSON (no markdown, no extra text):
{{
  "security_risk": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "regression_risk": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "edge_cases": ["<edge case 1>", "<edge case 2>"],
  "performance_impact": "<NEGLIGIBLE|LOW|MEDIUM|HIGH>",
  "test_coverage_adequate": <true|false>,
  "recommendation": "<APPROVE|REJECT|ESCALATE>",
  "findings_summary": "<one paragraph summary>"
}}
END_RESPONSE"""
