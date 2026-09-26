"""
AETHERIS AI — InferenceGateway

Thin abstraction layer for watsonx.ai / Granite inference.
Centralizes:
  - provider/model configuration
  - 15-second timeout
  - retries (1 retry on transient error)
  - structured response handling
  - error handling + logging
  - mock fallback when watsonx is not configured

IMPORTANT: This gateway is a subsystem only.
IBM Bob IDE is the primary engineering orchestrator.
watsonx.ai is the inference backend.
"""
import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger("aetheris.inference")

TIMEOUT_SECONDS = 15
MAX_RETRIES = 1

# Approved incident categories — must match exactly for fault injection
APPROVED_INCIDENT_CATEGORIES = {
    "NULL_ERROR",
    "SCHEMA_DRIFT",
    "LATENCY_REGRESSION",
    "RATE_LIMIT_MISCONFIGURATION",
    "DEPENDENCY_FAILURE",
    "RESOURCE_EXHAUSTION",
}


class InferenceError(Exception):
    """Raised when inference fails and cannot be retried."""


class InferenceGateway:
    """
    Wraps watsonx.ai REST API with timeout, retry, and mock fallback.
    All agent calls MUST go through this class — never call inference directly.
    """

    def __init__(self):
        self.settings = get_settings()

    async def _call_watsonx(self, prompt: str, max_tokens: int = 512) -> str:
        """Make a real call to watsonx.ai text generation endpoint."""
        token = await self._get_iam_token()
        url = f"{self.settings.watsonx_url}/ml/v1/text/generation?version=2023-05-29"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "model_id": self.settings.watsonx_model_id,
            "project_id": self.settings.watsonx_project_id,
            "input": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.2,
                "top_p": 0.9,
                "stop_sequences": ["```\n\n", "END_RESPONSE"],
            },
        }
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["results"][0]["generated_text"].strip()

    async def _get_iam_token(self) -> str:
        """Exchange watsonx API key for IAM bearer token."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": self.settings.watsonx_api_key,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        context: str = "general",
    ) -> str:
        """
        Generate text via watsonx.ai with timeout + retry.
        Falls back to mock if watsonx not configured.
        Raises InferenceError after exhausting retries.
        """
        if not self.settings.watsonx_configured:
            logger.info("[InferenceGateway] watsonx not configured — using mock fallback")
            return self._mock_response(prompt, context)

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    self._call_watsonx(prompt, max_tokens),
                    timeout=TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[InferenceGateway] Timeout on attempt {attempt+1}")
                last_exc = InferenceError(f"Inference timed out after {TIMEOUT_SECONDS}s")
            except httpx.HTTPStatusError as e:
                logger.error(f"[InferenceGateway] HTTP error: {e.response.status_code}")
                last_exc = InferenceError(f"HTTP {e.response.status_code} from watsonx")
                if e.response.status_code < 500:
                    break  # Client error — don't retry
            except Exception as e:
                logger.error(f"[InferenceGateway] Unexpected error: {e}")
                last_exc = InferenceError(str(e))

            if attempt < MAX_RETRIES:
                await asyncio.sleep(1)

        raise last_exc or InferenceError("Unknown inference failure")

    def _mock_response(self, prompt: str, context: str) -> str:
        """
        Deterministic mock responses keyed on context type.
        Used when watsonx is not configured (local/demo mode).
        All mock responses are clearly labeled as mock output.
        """
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]

        if context == "diagnosis":
            return json.dumps({
                "mock": True,
                "affected_service": "orders-service",
                "probable_root_cause": "NullPointerException caused by missing null guard on user_id field returned from identity resolver",
                "evidence": [
                    "Error trace shows NPE at CheckoutController.java:87",
                    "user_id field missing from identity resolver response",
                    "Error rate spiked from 0.3% to 23.4% at 08:20",
                ],
                "proposed_repair_strategy": "Add null guard before accessing user_id; raise explicit ValueError with context",
                "confidence": 0.87,
                "prompt_hash": prompt_hash,
            })

        if context == "patch":
            return json.dumps({
                "mock": True,
                "file": "services/orders-service/checkout_controller.py",
                "patch_type": "NULL_GUARD",
                "description": "Add null guard before accessing user_id field",
                "diff": (
                    "--- a/checkout_controller.py\n"
                    "+++ b/checkout_controller.py\n"
                    "@@ -84,6 +84,10 @@\n"
                    " def processOrder(self, request):\n"
                    "+    if request.user_id is None:\n"
                    "+        raise ValueError('user_id is required and cannot be None')\n"
                    "     user = self.identity_resolver.resolve(request.user_id)\n"
                ),
                "lines_changed": 2,
                "risk_surface": "MINIMAL",
                "prompt_hash": prompt_hash,
            })

        if context == "audit":
            return json.dumps({
                "mock": True,
                "security_risk": "LOW",
                "regression_risk": "LOW",
                "edge_cases": ["Empty string user_id still passes null guard — consider empty check"],
                "performance_impact": "NEGLIGIBLE",
                "test_coverage_adequate": True,
                "recommendation": "APPROVE",
                "findings_summary": "Patch introduces a safe null guard. No security vectors introduced. Regression risk is low.",
                "confidence": 0.91,
                "prompt_hash": prompt_hash,
            })

        return json.dumps({"mock": True, "response": "Mock response", "context": context, "prompt_hash": prompt_hash})


# Module-level singleton
_gateway: InferenceGateway | None = None


def get_inference_gateway() -> InferenceGateway:
    global _gateway
    if _gateway is None:
        _gateway = InferenceGateway()
    return _gateway
