"""
AETHERIS AI — Cryptographic Evidence Signing & Verification

Uses HMAC-SHA256 to sign incident evidence payloads.
Verification is REAL — the UI only shows "VALID" if verify_evidence() passes.

Signing key is loaded from environment (EVIDENCE_SIGNING_KEY).
Never hardcoded in source.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings

SIGNING_KEY_ID = "aetheris-hmac-sha256-v1"


def _get_key_bytes() -> bytes:
    settings = get_settings()
    return settings.evidence_signing_key.encode("utf-8")


def sign_payload(payload: dict) -> str:
    """
    Return HMAC-SHA256 hex digest of the canonical JSON representation of payload.
    Canonical = keys sorted, no extra whitespace.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        _get_key_bytes(),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_evidence(payload_json: str, signature: str) -> bool:
    """
    Re-derive the HMAC signature from the stored payload JSON and compare
    to the stored signature using hmac.compare_digest (timing-safe).

    Returns True ONLY if signatures match.
    Returns False on any mismatch, parse error, or exception.
    """
    try:
        payload = json.loads(payload_json)
        expected = sign_payload(payload)
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def build_evidence_payload(
    *,
    incident_id: str,
    affected_service: str,
    final_state: str,
    attempt_count: int,
    patch_hash: str | None,
    test_results: dict | None,
    audit_findings: dict | None,
    canary_metrics: dict | None,
    gate_checks: dict | None,
    state_transitions: list[dict],
) -> dict:
    """
    Construct the canonical evidence payload dict.
    This exact dict is what gets signed — order is irrelevant (sign_payload sorts keys).
    """
    return {
        "incident_id":      incident_id,
        "evidence_id":      str(uuid.uuid4()),
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "affected_service": affected_service,
        "final_state":      final_state,
        "attempt_count":    attempt_count,
        "patch_hash":       patch_hash,
        "test_results":     test_results or {},
        "audit_findings":   audit_findings or {},
        "gate_checks":      gate_checks or {},
        "canary_metrics":   canary_metrics or {},
        "state_transitions": state_transitions,
        "signing_key_id":   SIGNING_KEY_ID,
        "builder":          "IBM Bob IDE — AETHERIS AI Hackathon 2.0",
        "data_classification": "SYNTHETIC_DEMO",
    }
