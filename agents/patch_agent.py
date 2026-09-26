"""
AETHERIS AI — PatchAgent

Generates a constrained patch/diff against a known baseline.
All output is validated before use. Patch content is bounded —
no unrestricted code execution paths.
"""
import hashlib
import json
from typing import Any

from agents.base_agent import BaseAgent

_REQUIRED_PATCH_FIELDS = {"file", "patch_type", "description", "diff", "lines_changed"}

APPROVED_PATCH_TYPES = {
    "NULL_GUARD",
    "SCHEMA_FIX",
    "QUERY_OPTIMIZATION",
    "RATE_LIMIT_FIX",
    "RETRY_LOGIC",
    "RESOURCE_BOUND",
    "DEPENDENCY_CIRCUIT_BREAKER",
}


def _validate_patch_output(raw: Any) -> dict:
    """
    Validate patch output. Fail closed if required fields missing.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Patch output is not a dict: {type(raw)}")

    missing = _REQUIRED_PATCH_FIELDS - set(raw.keys())
    if missing:
        raise ValueError(f"Patch output missing required fields: {missing}")

    if not raw.get("diff") or len(raw["diff"]) < 10:
        raise ValueError("Patch 'diff' is empty or too short to be valid")

    patch_type = raw.get("patch_type", "")
    if patch_type not in APPROVED_PATCH_TYPES:
        raise ValueError(
            f"Patch type '{patch_type}' is not in approved types: {APPROVED_PATCH_TYPES}"
        )

    return raw


def compute_patch_hash(patch_content: str) -> str:
    """SHA-256 hash of patch diff content for evidence tracking."""
    return hashlib.sha256(patch_content.encode("utf-8")).hexdigest()


class PatchAgent(BaseAgent):
    """
    Generates constrained patches based on diagnosis output.
    """

    def __init__(self):
        super().__init__("PatchAgent")

    async def generate_patch(
        self,
        *,
        incident_id: str,
        diagnosis: dict,
        category: str,
        service: str,
        attempt_num: int = 1,
    ) -> dict[str, Any]:
        """
        Generate a patch based on diagnosis.
        Returns validated patch dict with computed hash.
        """
        self._log(f"Generating patch for {incident_id} (attempt {attempt_num})")

        prompt = self._build_prompt(
            incident_id=incident_id,
            diagnosis=diagnosis,
            category=category,
            service=service,
            attempt_num=attempt_num,
        )

        raw_text = await self.gateway.generate(prompt, max_tokens=800, context="patch")

        try:
            raw_json = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Patch response was not valid JSON: {e}\nRaw: {raw_text[:300]}")

        validated = _validate_patch_output(raw_json)
        validated["patch_hash"] = compute_patch_hash(validated["diff"])
        validated["attempt_num"] = attempt_num

        self._log(f"Patch generated. Hash: {validated['patch_hash'][:16]}...")
        return validated

    def _build_prompt(
        self,
        *,
        incident_id: str,
        diagnosis: dict,
        category: str,
        service: str,
        attempt_num: int,
    ) -> str:
        return f"""You are a senior software engineer generating a constrained hot-patch.

Incident ID: {incident_id}
Category: {category}
Service: {service}
Attempt: {attempt_num}

Diagnosis:
{json.dumps(diagnosis, indent=2)}

Approved patch types: {sorted(APPROVED_PATCH_TYPES)}

Generate a targeted, minimal patch. Respond with ONLY valid JSON (no markdown):
{{
  "file": "<path/to/file.py>",
  "patch_type": "<one of the approved types>",
  "description": "<what this patch does>",
  "diff": "<unified diff format>",
  "lines_changed": <integer>,
  "risk_surface": "<MINIMAL|LOW|MEDIUM>"
}}
END_RESPONSE"""
