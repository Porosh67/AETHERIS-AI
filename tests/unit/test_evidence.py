"""
AETHERIS AI — Evidence Signing & Verification Tests
Tests that signing is real, verification is real, and tampered evidence fails.
"""
import json
import pytest
from audit.evidence_signer import (
    build_evidence_payload,
    sign_payload,
    verify_evidence,
    SIGNING_KEY_ID,
)


class TestEvidenceSigning:
    def _sample_payload(self) -> dict:
        return build_evidence_payload(
            incident_id="INC-TEST-001",
            affected_service="orders-service",
            final_state="ROLLED_OUT",
            attempt_count=1,
            patch_hash="abc123def456",
            test_results={"passed": 5, "failed": 0},
            audit_findings={"security_risk": "LOW"},
            canary_metrics={"error_rate": 0.005},
            gate_checks={"passed": True},
            state_transitions=[
                {"from_state": "IDLE", "to_state": "INCIDENT_RECEIVED"}
            ],
        )

    def test_sign_returns_hex_string(self):
        payload = self._sample_payload()
        sig = sign_payload(payload)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex = 64 chars

    def test_verify_valid_evidence_returns_true(self):
        payload = self._sample_payload()
        sig = sign_payload(payload)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        assert verify_evidence(payload_json, sig) is True

    def test_verify_tampered_payload_returns_false(self):
        payload = self._sample_payload()
        sig = sign_payload(payload)
        # Tamper: change the final state
        payload["final_state"] = "ROLLED_OUT_TAMPERED"
        tampered_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        assert verify_evidence(tampered_json, sig) is False

    def test_verify_wrong_signature_returns_false(self):
        payload = self._sample_payload()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        wrong_sig = "a" * 64
        assert verify_evidence(payload_json, wrong_sig) is False

    def test_verify_invalid_json_returns_false(self):
        assert verify_evidence("{not valid json}", "a" * 64) is False

    def test_verify_empty_string_returns_false(self):
        assert verify_evidence("", "") is False

    def test_signing_is_deterministic(self):
        payload = self._sample_payload()
        sig1 = sign_payload(payload)
        sig2 = sign_payload(payload)
        assert sig1 == sig2

    def test_different_payloads_produce_different_signatures(self):
        p1 = self._sample_payload()
        p2 = self._sample_payload()
        p2["incident_id"] = "INC-DIFFERENT"
        assert sign_payload(p1) != sign_payload(p2)

    def test_signing_key_id_is_correct(self):
        assert SIGNING_KEY_ID == "aetheris-hmac-sha256-v1"

    def test_payload_contains_required_fields(self):
        payload = self._sample_payload()
        required = {
            "incident_id", "evidence_id", "timestamp", "affected_service",
            "final_state", "attempt_count", "signing_key_id", "builder",
            "data_classification",
        }
        assert required.issubset(set(payload.keys()))

    def test_payload_data_classification_is_synthetic(self):
        payload = self._sample_payload()
        assert payload["data_classification"] == "SYNTHETIC_DEMO"
