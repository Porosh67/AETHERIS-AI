"""
AETHERIS AI — Evidence Input HMAC Protection

Protects intermediate evidence inputs (telemetry snapshots, test results,
patch diffs) with HMAC-SHA256 tags before they reach the Auditor.

This is distinct from the final evidence attestation (audit/evidence_signer.py):

  Input HMAC  = protects data flowing INTO the audit step
  Final HMAC  = attests the complete incident resolution record

If any input HMAC fails verification:
  -> AUDIT_UNTRUSTED -> NO ROLLOUT -> retry or quarantine

Key: loaded from environment (EVIDENCE_SIGNING_KEY)
     Never hardcoded, never committed, never displayed.
"""
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

from backend.app.core.config import get_settings

logger = logging.getLogger("aetheris.evidence_hmac")


def _key_bytes() -> bytes:
    return get_settings().evidence_signing_key.encode("utf-8")


def hmac_tag(payload: dict | str) -> str:
    """
    Compute HMAC-SHA256 tag for an evidence input payload.
    Returns 64-char hex string.
    """
    if isinstance(payload, dict):
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    else:
        canonical = str(payload)
    return hmac.new(_key_bytes(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_tag(payload: dict | str, tag: str) -> bool:
    """
    Verify an evidence input HMAC tag.
    Returns True only if the tag matches. Timing-safe.
    """
    try:
        expected = hmac_tag(payload)
        return hmac.compare_digest(expected, tag)
    except Exception:
        return False


@dataclass
class TaggedEvidence:
    """An evidence input with its HMAC tag."""
    payload: dict
    tag: str
    kind: str  # "telemetry" | "test_results" | "patch_diff"

    def verify(self) -> bool:
        return verify_tag(self.payload, self.tag)


def tag_evidence(payload: dict, kind: str) -> TaggedEvidence:
    """Create a TaggedEvidence from a dict payload."""
    return TaggedEvidence(payload=payload, tag=hmac_tag(payload), kind=kind)


@dataclass
class EvidenceVerificationResult:
    all_valid: bool
    results: dict[str, bool]
    failed: list[str]


def verify_all_evidence_inputs(
    telemetry: dict | None,
    test_results: dict | None,
    patch_diff: dict | None,
    telemetry_tag: str | None,
    test_results_tag: str | None,
    patch_diff_tag: str | None,
) -> EvidenceVerificationResult:
    """
    Verify HMAC tags for all evidence inputs supplied to the Auditor.
    If any tag is missing or invalid, returns all_valid=False.
    Fail-closed: missing tag = failed.
    """
    checks: dict[str, bool] = {}

    def check(name: str, payload: dict | None, tag: str | None) -> None:
        if payload is None:
            checks[name] = True  # not provided — skip
            return
        if not tag:
            logger.warning(f"[EvidenceHMAC] {name}: tag missing — fail closed")
            checks[name] = False
            return
        ok = verify_tag(payload, tag)
        if not ok:
            logger.warning(f"[EvidenceHMAC] {name}: HMAC verification FAILED")
        checks[name] = ok

    check("telemetry",    telemetry,    telemetry_tag)
    check("test_results", test_results, test_results_tag)
    check("patch_diff",   patch_diff,   patch_diff_tag)

    failed = [k for k, v in checks.items() if not v]
    return EvidenceVerificationResult(
        all_valid=not failed,
        results=checks,
        failed=failed,
    )
