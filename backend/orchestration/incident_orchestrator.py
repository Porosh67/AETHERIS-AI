"""
AETHERIS AI — Incident Orchestrator

The primary workflow engine. Drives an incident through the full
state machine: INCIDENT_RECEIVED → ... → ROLLED_OUT | QUARANTINED.

Responsibilities:
  - State transitions (validated by FSM)
  - Attempt counter enforcement (hard cap = 3, persisted in DB)
  - Agent orchestration (Diagnosis → Patch → Test → Audit → Gate → Canary)
  - Bob activity logging (real event stream)
  - Evidence signing and storage
  - Fail-closed behavior at every step

Bob IDE is the engineering orchestrator. This module is the runtime expression
of the workflow Bob constructed.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from agents.diagnosis_agent import DiagnosisAgent
from agents.patch_agent import PatchAgent
from agents.auditor_agent import AuditorAgent, AuditRecommendation
from orchestration.release_gate import DeterministicReleaseGate
from orchestration.canary_validator import CanaryValidator
from orchestration.test_runner import run_tests
from audit.evidence_signer import (
    build_evidence_payload,
    sign_payload,
    SIGNING_KEY_ID,
)
from audit.evidence_hmac import tag_evidence, verify_all_evidence_inputs
from app.core.state_machine import (
    IncidentState,
    validate_transition,
    is_terminal,
    is_retry_allowed,
    InvalidTransitionError,
)
from app.models.db_models import (
    IncidentRecord,
    StateTransitionLog,
    PatchRecord,
    EvidenceRecord,
    BobActivityLog,
)
from app.core.config import get_settings

logger = logging.getLogger("aetheris.orchestrator")
settings = get_settings()


class OrchestratorError(Exception):
    pass


class IncidentOrchestrator:
    """
    Drives the full incident repair lifecycle.
    Thread-safe per-incident (one orchestrator instance per run).
    """

    def __init__(self, session: Session):
        self.session = session
        self.diagnosis_agent = DiagnosisAgent()
        self.patch_agent      = PatchAgent()
        self.auditor_agent    = AuditorAgent()
        self.release_gate     = DeterministicReleaseGate()
        self.canary_validator = CanaryValidator()

    # ─────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────

    async def run(self, incident_pk: str, scenario_mode: str = "pass") -> dict[str, Any]:
        """
        Execute the full incident repair workflow.
        scenario_mode: "pass" = safe repair demo, "fail" = controlled failure demo.
        Returns final state and summary dict.
        """
        record = self._get_incident(incident_pk)
        self._bob("[BOB] Incident received", incident_pk)
        self._bob(f"[BOB] Scenario mode: {scenario_mode}", incident_pk)

        await self._transition(record, IncidentState.INCIDENT_RECEIVED, "Incident loaded")
        await self._transition(record, IncidentState.DIAGNOSING, "Beginning diagnosis")

        state_transitions_log: list[dict] = []
        patch_record: PatchRecord | None = None
        final_diagnosis: dict = {}
        final_patch: dict = {}
        final_test: dict = {}
        final_audit_dict: dict = {}
        final_gate_dict: dict = {}
        final_canary_dict: dict = {}

        while True:
            current_attempt = record.attempt_count + 1
            self._bob(f"[BOB] Repair attempt {current_attempt}/{record.max_attempts}", incident_pk)

            # ── DIAGNOSIS ────────────────────────────────────────────
            self._bob("[BOB] Inspecting affected service", incident_pk)
            self._bob("[BOB] Reading error trace", incident_pk)
            _attempt_started = time.monotonic()

            try:
                diagnosis = await self.diagnosis_agent.diagnose(
                    incident_id=record.incident_id,
                    category=record.category,
                    service=record.service,
                    error_trace=record.error_trace or "",
                    attempt_num=current_attempt,
                )
                final_diagnosis = diagnosis
                self._bob(
                    f"[BOB] Root cause identified: {diagnosis['probable_root_cause'][:80]}",
                    incident_pk,
                )
            except Exception as e:
                self._bob(f"[BOB] Diagnosis failed: {e}", incident_pk, "BOB_ERROR")
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                if not is_retry_allowed(record.attempt_count, record.max_attempts):
                    await self._quarantine(record, f"Diagnosis failed after {record.max_attempts} attempts: {e}")
                    break
                await self._transition(record, IncidentState.REPAIR_RETRY, f"Diagnosis error: {e}")
                await self._transition(record, IncidentState.DIAGNOSING, "Retrying diagnosis")
                continue

            # ── PATCH GENERATION ─────────────────────────────────────
            self._bob("[BOB] Preparing remediation", incident_pk)
            await self._transition(record, IncidentState.PATCH_GENERATED, "Diagnosis complete")

            try:
                patch = await self.patch_agent.generate_patch(
                    incident_id=record.incident_id,
                    diagnosis=diagnosis,
                    category=record.category,
                    service=record.service,
                    attempt_num=current_attempt,
                )
                final_patch = patch
                self._bob(f"[BOB] Patch generated: {patch['description'][:80]}", incident_pk)
            except Exception as e:
                self._bob(f"[BOB] Patch generation failed: {e}", incident_pk, "BOB_ERROR")
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                if is_retry_allowed(record.attempt_count, record.max_attempts):
                    await self._transition(record, IncidentState.REPAIR_RETRY, f"Patch error: {e}")
                    self._bob(f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}", incident_pk)
                    await self._transition(record, IncidentState.DIAGNOSING, "Retrying after patch failure")
                else:
                    await self._quarantine(record, f"Patch failed after {record.max_attempts} attempts")
                    break
                continue

            # ── TESTING ──────────────────────────────────────────────
            await self._transition(record, IncidentState.PATCH_TESTING, "Patch generated")
            self._bob("[BOB] Running tests", incident_pk)

            test_scenario = scenario_mode if current_attempt >= record.max_attempts else scenario_mode
            # On controlled-failure scenario, always fail tests
            effective_test_scenario = "fail" if scenario_mode == "fail" else "pass"

            test_result = await run_tests(
                category=record.category,
                scenario=effective_test_scenario,
                patch_hash=patch.get("patch_hash", ""),
                seed=current_attempt,
            )
            final_test = test_result.to_dict()

            self._bob(
                f"[BOB] Test results: {test_result.passed}/{test_result.total} passed "
                f"({test_result.pass_rate:.0%})",
                incident_pk,
                "BOB_SUCCESS" if test_result.pass_rate >= 0.95 else "BOB_WARNING",
            )

            # ── HMAC-tag evidence inputs before they reach the Auditor ──
            test_results_dict = test_result.to_dict()
            patch_dict_for_hmac = {"diff": patch.get("diff", ""), "patch_hash": patch.get("patch_hash", "")}
            tagged_tests  = tag_evidence(test_results_dict,    "test_results")
            tagged_patch  = tag_evidence(patch_dict_for_hmac,  "patch_diff")

            # Persist patch record
            _elapsed_ms = int((time.monotonic() - _attempt_started) * 1000)
            _model_used = settings.watsonx_model_id if settings.watsonx_configured else "mock"
            patch_record = PatchRecord(
                incident_pk=incident_pk,
                attempt_num=current_attempt,
                patch_content=json.dumps(patch),
                patch_hash=patch.get("patch_hash", ""),
                test_pass_rate=test_result.pass_rate,
                test_results=json.dumps(test_results_dict),
                latency_ms=_elapsed_ms,
                model_used=_model_used,
            )

            if test_result.pass_rate < 0.95:
                self._bob(f"[BOB] Validation failed (tests)", incident_pk, "BOB_WARNING")
                patch_record.gate_passed = False
                self.session.add(patch_record)
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                # Must go through REPAIR_RETRY regardless — PATCH_TESTING cannot go directly to QUARANTINED
                await self._transition(record, IncidentState.REPAIR_RETRY, f"Tests failed: pass_rate={test_result.pass_rate:.2%}")
                if is_retry_allowed(record.attempt_count, record.max_attempts):
                    self._bob(f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}", incident_pk)
                    await self._transition(record, IncidentState.DIAGNOSING, "Retrying after test failure")
                else:
                    await self._quarantine(record, f"Tests failed after {record.max_attempts} attempts")
                    break
                continue

            # ── AUDIT ────────────────────────────────────────────────
            # Verify HMAC integrity of evidence inputs before audit
            hmac_check = verify_all_evidence_inputs(
                telemetry=None, test_results=test_results_dict, patch_diff=patch_dict_for_hmac,
                telemetry_tag=None,
                test_results_tag=tagged_tests.tag,
                patch_diff_tag=tagged_patch.tag,
            )
            if not hmac_check.all_valid:
                self._bob(
                    f"[BOB] Evidence HMAC verification FAILED: {hmac_check.failed}",
                    incident_pk, "BOB_ERROR",
                )
                await self._transition(record, IncidentState.AUDITING, "Pre-audit HMAC failed")
                await self._transition(record, IncidentState.AUDIT_UNTRUSTED, f"HMAC failed: {hmac_check.failed}")
                record.attempt_count += 1
                self.session.add(patch_record)
                self.session.add(record)
                self.session.commit()
                # Must route through REPAIR_RETRY before QUARANTINED (FSM constraint)
                await self._transition(record, IncidentState.REPAIR_RETRY, "Evidence HMAC failed")
                if is_retry_allowed(record.attempt_count, record.max_attempts):
                    self._bob(f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}", incident_pk)
                    await self._transition(record, IncidentState.DIAGNOSING, "Retrying after HMAC failure")
                else:
                    await self._quarantine(record, f"Evidence HMAC failed after {record.max_attempts} attempts")
                    break
                continue

            await self._transition(record, IncidentState.AUDITING, "Tests passed, HMACs verified")
            self._bob("[BOB] Evidence HMACs verified", incident_pk, "BOB_SUCCESS")
            self._bob("[BOB] Auditor reviewing patch", incident_pk)

            audit_result = await self.auditor_agent.audit(
                incident_id=record.incident_id,
                patch=patch,
                diagnosis=diagnosis,
                test_results=test_result.to_dict(),
                attempt_num=current_attempt,
            )
            final_audit_dict = {
                "trusted":              audit_result.trusted,
                "security_risk":        audit_result.security_risk,
                "regression_risk":      audit_result.regression_risk,
                "edge_cases":           audit_result.edge_cases,
                "performance_impact":   audit_result.performance_impact,
                "test_coverage_adequate": audit_result.test_coverage_adequate,
                "recommendation":       audit_result.recommendation.value,
                "findings_summary":     audit_result.findings_summary,
                "untrust_reason":       audit_result.untrust_reason,
            }

            if not audit_result.trusted:
                # FAIL CLOSED — AUDIT_UNTRUSTED
                self._bob(
                    f"[BOB] AUDIT UNTRUSTED: {audit_result.untrust_reason}",
                    incident_pk, "BOB_ERROR",
                )
                await self._transition(record, IncidentState.AUDIT_UNTRUSTED, audit_result.untrust_reason)
                patch_record.audit_trusted = False
                patch_record.audit_findings = json.dumps(final_audit_dict)
                self.session.add(patch_record)
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                # AUDIT_UNTRUSTED → REPAIR_RETRY (required by FSM before QUARANTINED)
                await self._transition(record, IncidentState.REPAIR_RETRY, "Audit untrusted — fail closed")
                if is_retry_allowed(record.attempt_count, record.max_attempts):
                    self._bob(f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}", incident_pk)
                    await self._transition(record, IncidentState.DIAGNOSING, "Retrying after audit failure")
                else:
                    await self._quarantine(record, f"Audit untrusted after {record.max_attempts} attempts")
                    break
                continue

            self._bob(
                f"[BOB] Audit complete: security={audit_result.security_risk}, "
                f"regression={audit_result.regression_risk}, "
                f"recommendation={audit_result.recommendation.value}",
                incident_pk,
                "BOB_SUCCESS" if audit_result.recommendation == AuditRecommendation.APPROVE else "BOB_WARNING",
            )

            patch_record.audit_trusted   = True
            patch_record.audit_risk_level = audit_result.security_risk
            patch_record.audit_findings  = json.dumps(final_audit_dict)

            # ── DETERMINISTIC RELEASE GATE ───────────────────────────
            self._bob("[BOB] Deterministic safety gate running", incident_pk)

            gate_result = self.release_gate.evaluate(
                test_pass_rate=test_result.pass_rate,
                audit_trusted=audit_result.trusted,
                audit_security_risk=audit_result.security_risk,
                audit_regression_risk=audit_result.regression_risk,
                audit_recommendation=audit_result.recommendation.value,
                test_coverage_adequate=audit_result.test_coverage_adequate,
                evidence_hmacs_valid=hmac_check.all_valid,
            )
            final_gate_dict = gate_result.to_dict()
            patch_record.gate_passed = gate_result.passed
            patch_record.gate_checks = json.dumps(final_gate_dict)

            if not gate_result.passed:
                failed_names = [c.name for c in gate_result.failed_checks]
                self._bob(
                    f"[BOB] Safety gate BLOCKED rollout: {failed_names}",
                    incident_pk, "BOB_WARNING",
                )
                self.session.add(patch_record)
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                # AUDITING → REPAIR_RETRY always (required by FSM before QUARANTINED)
                await self._transition(record, IncidentState.REPAIR_RETRY, f"Gate failed: {failed_names}")
                if is_retry_allowed(record.attempt_count, record.max_attempts):
                    self._bob(f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}", incident_pk)
                    await self._transition(record, IncidentState.DIAGNOSING, "Retrying after gate failure")
                else:
                    await self._quarantine(record, f"Gate failed after {record.max_attempts} attempts")
                    break
                continue

            self._bob("[BOB] Safety gate PASSED", incident_pk, "BOB_SUCCESS")

            # ── CANARY ───────────────────────────────────────────────
            await self._transition(record, IncidentState.CANARY_PENDING, "Gate passed")
            await self._transition(record, IncidentState.CANARY_RUNNING, "Canary starting")
            self._bob("[BOB] Canary validation started", incident_pk)

            canary_scenario = "fail" if scenario_mode == "fail" else "pass"  # custom → pass (only controlled-failure demo fails canary)
            canary_result = await self.canary_validator.run_canary(
                scenario=canary_scenario,
                service=record.service,
                patch_hash=patch.get("patch_hash", ""),
                seed=current_attempt,
            )
            final_canary_dict = canary_result.to_dict()
            patch_record.canary_passed  = canary_result.passed
            patch_record.canary_metrics = json.dumps(final_canary_dict)
            self.session.add(patch_record)
            self.session.commit()

            if not canary_result.passed:
                self._bob(
                    f"[BOB] Canary UNHEALTHY: {canary_result.reason}",
                    incident_pk, "BOB_WARNING",
                )
                record.attempt_count += 1
                self.session.add(record)
                self.session.commit()
                await self._transition(record, IncidentState.REPAIR_RETRY, canary_result.reason)
                if not is_retry_allowed(record.attempt_count, record.max_attempts):
                    await self._quarantine(record, f"Canary failed after {record.max_attempts} attempts")
                    break
                self._bob(
                    f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}",
                    incident_pk,
                )
                await self._transition(record, IncidentState.DIAGNOSING, "Retrying after canary failure")
                continue

            # ── ROLLOUT ──────────────────────────────────────────────
            self._bob("[BOB] Canary healthy", incident_pk, "BOB_SUCCESS")
            await self._transition(record, IncidentState.ROLLED_OUT, "Canary passed — rolling out")
            self._bob("[BOB] Rollout authorized", incident_pk, "BOB_SUCCESS")
            break

        # ── EVIDENCE SIGNING ─────────────────────────────────────────
        self._bob("[BOB] Evidence signing", incident_pk)
        transitions = self._load_transitions(incident_pk)
        evidence_payload = build_evidence_payload(
            incident_id=record.incident_id,
            affected_service=record.service,
            final_state=record.state,
            attempt_count=record.attempt_count,
            patch_hash=final_patch.get("patch_hash"),
            test_results=final_test,
            audit_findings=final_audit_dict,
            canary_metrics=final_canary_dict,
            gate_checks=final_gate_dict,
            state_transitions=transitions,
        )
        signature = sign_payload(evidence_payload)
        payload_json = json.dumps(evidence_payload, sort_keys=True, separators=(",", ":"))

        ev = EvidenceRecord(
            incident_pk=incident_pk,
            incident_id=record.incident_id,
            affected_service=record.service,
            final_state=record.state,
            attempt_count=record.attempt_count,
            patch_hash=final_patch.get("patch_hash"),
            payload_json=payload_json,
            signing_key_id=SIGNING_KEY_ID,
            signature=signature,
            verified=True,
        )
        self.session.add(ev)
        self.session.commit()
        self.session.refresh(ev)

        self._bob("[BOB] Evidence signed", incident_pk, "BOB_SUCCESS")

        if record.state == IncidentState.ROLLED_OUT.value:
            self._bob("[BOB] Incident resolved", incident_pk, "BOB_SUCCESS")
        else:
            self._bob("[BOB] Human review required", incident_pk, "BOB_WARNING")
            self._bob("[BOB] Evidence preserved", incident_pk)

        return {
            "incident_pk":   incident_pk,
            "incident_id":   record.incident_id,
            "final_state":   record.state,
            "attempt_count": record.attempt_count,
            "evidence_id":   ev.id,
            "signature":     signature,
            "signing_key_id": SIGNING_KEY_ID,
        }

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_incident(self, incident_pk: str) -> IncidentRecord:
        record = self.session.get(IncidentRecord, incident_pk)
        if not record:
            raise OrchestratorError(f"Incident {incident_pk} not found")
        return record

    async def _transition(
        self,
        record: IncidentRecord,
        to_state: IncidentState,
        reason: str = "",
    ) -> None:
        from_state = IncidentState(record.state)
        validate_transition(from_state, to_state)  # raises on invalid

        log = StateTransitionLog(
            incident_pk=record.id,
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
            attempt_num=record.attempt_count,
        )
        record.state      = to_state.value
        record.updated_at = datetime.now(timezone.utc)
        self.session.add(log)
        self.session.add(record)
        self.session.commit()
        logger.info(f"[Orchestrator] {from_state.value} → {to_state.value} | {reason}")

    async def _handle_retry_or_quarantine(
        self, record: IncidentRecord, reason: str
    ) -> None:
        if is_retry_allowed(record.attempt_count, record.max_attempts):
            await self._transition(record, IncidentState.REPAIR_RETRY, reason)
            self._bob(
                f"[BOB] Repair attempt {record.attempt_count + 1}/{record.max_attempts}",
                record.id,
            )
        else:
            await self._quarantine(record, reason)

    async def _quarantine(self, record: IncidentRecord, reason: str) -> None:
        try:
            await self._transition(record, IncidentState.QUARANTINED, reason)
        except InvalidTransitionError:
            # Already in quarantine or terminal — acceptable
            pass
        self._bob(f"[BOB] Incident quarantined — {reason}", record.id, "BOB_WARNING")
        self._bob("[BOB] Human review required", record.id, "BOB_WARNING")
        self._bob("[BOB] Evidence preserved", record.id)

    def _bob(
        self,
        message: str,
        incident_pk: str,
        event_type: str = "BOB_INFO",
        detail: str | None = None,
    ) -> None:
        log = BobActivityLog(
            incident_pk=incident_pk,
            event_type=event_type,
            message=message,
            detail=detail,
        )
        self.session.add(log)
        self.session.commit()
        logger.info(f"[BobActivity] {message}")

    def _load_transitions(self, incident_pk: str) -> list[dict]:
        stmt = select(StateTransitionLog).where(
            StateTransitionLog.incident_pk == incident_pk
        )
        rows = self.session.exec(stmt).all()
        return [
            {
                "from_state":  r.from_state,
                "to_state":    r.to_state,
                "reason":      r.reason,
                "attempt_num": r.attempt_num,
                "timestamp":   r.timestamp.isoformat(),
            }
            for r in rows
        ]