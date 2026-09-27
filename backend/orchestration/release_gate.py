"""
AETHERIS AI — Deterministic Release Gate

THE LLM IS NEVER THE SOLE AUTHORIZATION MECHANISM FOR ROLLOUT.

This gate performs code-only deterministic checks.
All thresholds are configured — no AI decisions here.
Gate FAILS CLOSED: any missing required check = NO ROLLOUT.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("aetheris.release_gate")

# Default thresholds — can be overridden per scenario
DEFAULT_THRESHOLDS = {
    "min_test_pass_rate":        0.95,
    "max_security_risk":         "MEDIUM",   # MEDIUM or lower passes
    "max_regression_risk":       "LOW",      # LOW or lower passes
    "require_test_coverage":     True,
    "require_audit_trusted":     True,
    "require_approve_or_above":  True,       # APPROVE required from auditor
}

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3, "UNKNOWN": 99}


@dataclass
class GateCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    passed: bool
    checks: list[GateCheck] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
            "failed_checks": [c.name for c in self.failed_checks],
        }


class DeterministicReleaseGate:
    """
    Deterministic gate — pure Python, no LLM calls.
    Authorizes or blocks rollout based on hard numeric/categorical thresholds.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def evaluate(
        self,
        *,
        test_pass_rate: float,
        audit_trusted: bool,
        audit_security_risk: str,
        audit_regression_risk: str,
        audit_recommendation: str,
        test_coverage_adequate: bool,
        evidence_hmacs_valid: bool = True,   # input HMAC verification result
    ) -> GateResult:
        """
        Run all deterministic checks.
        Returns GateResult. If ANY required check fails → passed=False.
        """
        checks: list[GateCheck] = []

        # ── Check 0: Evidence input HMAC integrity ────────────────────
        checks.append(GateCheck(
            name="evidence_hmacs_valid",
            passed=evidence_hmacs_valid,
            detail="All evidence input HMACs must be verified before audit",
        ))

        # ── Check 1: Test pass rate ───────────────────────────────────
        min_rate = self.thresholds["min_test_pass_rate"]
        checks.append(GateCheck(
            name="test_pass_rate",
            passed=test_pass_rate >= min_rate,
            detail=f"pass_rate={test_pass_rate:.2%} (required >= {min_rate:.2%})",
        ))

        # ── Check 2: Audit trusted ────────────────────────────────────
        if self.thresholds["require_audit_trusted"]:
            checks.append(GateCheck(
                name="audit_trusted",
                passed=audit_trusted,
                detail="Audit output must be structurally valid and trusted",
            ))

        # ── Check 3: Security risk threshold ─────────────────────────
        max_sec = self.thresholds["max_security_risk"]
        sec_ok = RISK_ORDER.get(audit_security_risk, 99) <= RISK_ORDER.get(max_sec, 99)
        checks.append(GateCheck(
            name="security_risk",
            passed=sec_ok,
            detail=f"security_risk={audit_security_risk} (max allowed: {max_sec})",
        ))

        # ── Check 4: Regression risk threshold ───────────────────────
        max_reg = self.thresholds["max_regression_risk"]
        reg_ok = RISK_ORDER.get(audit_regression_risk, 99) <= RISK_ORDER.get(max_reg, 99)
        checks.append(GateCheck(
            name="regression_risk",
            passed=reg_ok,
            detail=f"regression_risk={audit_regression_risk} (max allowed: {max_reg})",
        ))

        # ── Check 5: Audit recommendation ────────────────────────────
        if self.thresholds["require_approve_or_above"]:
            rec_ok = audit_recommendation == "APPROVE"
            checks.append(GateCheck(
                name="audit_recommendation",
                passed=rec_ok,
                detail=f"recommendation={audit_recommendation} (required: APPROVE)",
            ))

        # ── Check 6: Test coverage ────────────────────────────────────
        if self.thresholds["require_test_coverage"]:
            checks.append(GateCheck(
                name="test_coverage_adequate",
                passed=test_coverage_adequate,
                detail="Auditor must confirm adequate test coverage",
            ))

        overall = all(c.passed for c in checks)
        logger.info(
            f"[ReleaseGate] Result: {'PASS' if overall else 'FAIL'} "
            f"({sum(c.passed for c in checks)}/{len(checks)} checks passed)"
        )
        return GateResult(passed=overall, checks=checks)
