"""
AETHERIS AI — DiagnosisAgent (Sentinel)

Consumes: error trace, telemetry, service context
Produces: affected service, probable root cause, evidence, repair strategy

Uses InferenceGateway → watsonx.ai / mock fallback.
All LLM output is validated before use.
"""
import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from app.services.inference_gateway import InferenceError

logger = logging.getLogger("aetheris.agent.diagnosis")

_REQUIRED_DIAGNOSIS_FIELDS = {
    "affected_service",
    "probable_root_cause",
    "evidence",
    "proposed_repair_strategy",
}


def _validate_diagnosis_output(raw: Any) -> dict:
    """
    Validate that LLM diagnosis output contains all required fields.
    Raises ValueError if invalid — caller must treat this as a failed inference.
    Never silently converts invalid output into "score = 0" equivalent.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Diagnosis output is not a dict: {type(raw)}")

    missing = _REQUIRED_DIAGNOSIS_FIELDS - set(raw.keys())
    if missing:
        raise ValueError(f"Diagnosis output missing required fields: {missing}")

    if not isinstance(raw.get("evidence"), list) or len(raw["evidence"]) == 0:
        raise ValueError("Diagnosis 'evidence' must be a non-empty list")

    if not raw.get("affected_service"):
        raise ValueError("Diagnosis 'affected_service' cannot be empty")

    if not raw.get("probable_root_cause"):
        raise ValueError("Diagnosis 'probable_root_cause' cannot be empty")

    return raw


class DiagnosisAgent(BaseAgent):
    """
    Sentinel / Diagnosis Agent.
    Analyzes incident evidence and produces a structured repair strategy.
    """

    def __init__(self):
        super().__init__("DiagnosisAgent")

    async def diagnose(
        self,
        *,
        incident_id: str,
        category: str,
        service: str,
        error_trace: str,
        telemetry: dict | None = None,
        attempt_num: int = 1,
    ) -> dict[str, Any]:
        """
        Run diagnosis against the incident evidence.
        Returns validated diagnosis dict.
        Raises InferenceError or ValueError on failure.
        """
        self._log(f"Diagnosing {incident_id} (attempt {attempt_num})")

        prompt = self._build_prompt(
            incident_id=incident_id,
            category=category,
            service=service,
            error_trace=error_trace,
            telemetry=telemetry or {},
            attempt_num=attempt_num,
        )

        raw_text = await self.gateway.generate(prompt, max_tokens=600, context="diagnosis")

        try:
            raw_json = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Diagnosis response was not valid JSON: {e}\nRaw: {raw_text[:300]}")

        validated = _validate_diagnosis_output(raw_json)
        self._log(f"Diagnosis complete. Root cause: {validated['probable_root_cause'][:80]}")
        return validated

    def _build_prompt(
        self,
        *,
        incident_id: str,
        category: str,
        service: str,
        error_trace: str,
        telemetry: dict,
        attempt_num: int,
    ) -> str:
        tel_str = json.dumps(telemetry, indent=2) if telemetry else "Not available"
        return f"""You are a senior site reliability engineer analyzing a production incident.

Incident ID: {incident_id}
Category: {category}
Affected Service: {service}
Attempt: {attempt_num}

Error Trace:
{error_trace}

Telemetry:
{tel_str}

Analyze the evidence and respond with ONLY valid JSON (no markdown, no extra text):
{{
  "affected_service": "<service name>",
  "probable_root_cause": "<concise root cause description>",
  "evidence": ["<evidence item 1>", "<evidence item 2>"],
  "proposed_repair_strategy": "<specific repair action>",
  "confidence": <float 0.0-1.0>
}}
END_RESPONSE"""
