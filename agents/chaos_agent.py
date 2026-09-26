"""
AETHERIS AI — ChaosAgent

Generates BOUNDED fault parameters from the approved incident taxonomy only.
NEVER generates unrestricted arbitrary production code.
Only returns parameters from the whitelist of approved incident categories.
"""
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.base_agent import BaseAgent

APPROVED_INCIDENT_CATEGORIES = [
    "NULL_ERROR",
    "SCHEMA_DRIFT",
    "LATENCY_REGRESSION",
    "RATE_LIMIT_MISCONFIGURATION",
    "DEPENDENCY_FAILURE",
    "RESOURCE_EXHAUSTION",
]

APPROVED_SERVICES = [
    "gateway-service",
    "orders-service",
    "payments-service",
    "inventory-service",
]

# Pre-defined fault templates — no arbitrary code, only parameterized entries
_FAULT_TEMPLATES: dict[str, dict] = {
    "NULL_ERROR": {
        "severity": "CRITICAL",
        "description_template": "NullPointerException in {service} — {field} field not validated before access",
        "error_rate_range": (15.0, 40.0),
        "latency_impact_ms": 200,
        "fields": ["user_id", "order_id", "session_token", "payment_method"],
    },
    "SCHEMA_DRIFT": {
        "severity": "HIGH",
        "description_template": "Schema drift in {service} — required field '{field}' missing from payload after deploy",
        "error_rate_range": (30.0, 60.0),
        "latency_impact_ms": 0,
        "fields": ["currency_code", "tenant_id", "api_version", "trace_id"],
    },
    "LATENCY_REGRESSION": {
        "severity": "HIGH",
        "description_template": "Latency regression in {service} — p99 exceeded SLA (query plan regression)",
        "error_rate_range": (5.0, 20.0),
        "latency_impact_ms": 7000,
        "fields": [],
    },
    "RATE_LIMIT_MISCONFIGURATION": {
        "severity": "MEDIUM",
        "description_template": "Rate limiter misconfiguration in {service} — per-user limit reduced by config change",
        "error_rate_range": (50.0, 80.0),
        "latency_impact_ms": 50,
        "fields": [],
    },
    "DEPENDENCY_FAILURE": {
        "severity": "CRITICAL",
        "description_template": "Dependency failure in {service} — cannot reach upstream service after pod restart",
        "error_rate_range": (90.0, 100.0),
        "latency_impact_ms": 29000,
        "fields": [],
    },
    "RESOURCE_EXHAUSTION": {
        "severity": "HIGH",
        "description_template": "Resource exhaustion in {service} — OOM under load (unbounded in-memory accumulation)",
        "error_rate_range": (20.0, 50.0),
        "latency_impact_ms": 12000,
        "fields": [],
    },
}


class ChaosAgent(BaseAgent):
    """
    Generates bounded fault injection parameters.
    Input validation: category must be from APPROVED_INCIDENT_CATEGORIES.
    Service must be from APPROVED_SERVICES.
    No code execution. No arbitrary payload generation.
    """

    def __init__(self):
        super().__init__("ChaosAgent")

    def generate_fault(
        self,
        category: str | None = None,
        service: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """
        Generate bounded fault parameters.
        Returns a dict of fault parameters — never executable code.
        """
        # ── Input validation ──────────────────────────────────────────────
        if category is not None and category not in APPROVED_INCIDENT_CATEGORIES:
            raise ValueError(
                f"Incident category '{category}' is not in the approved taxonomy. "
                f"Allowed: {APPROVED_INCIDENT_CATEGORIES}"
            )
        if service is not None and service not in APPROVED_SERVICES:
            raise ValueError(
                f"Service '{service}' is not in the approved service list. "
                f"Allowed: {APPROVED_SERVICES}"
            )

        rng = random.Random(seed)
        selected_category = category or rng.choice(APPROVED_INCIDENT_CATEGORIES)
        selected_service   = service or rng.choice(APPROVED_SERVICES)
        template           = _FAULT_TEMPLATES[selected_category]

        error_rate = round(
            rng.uniform(*template["error_rate_range"]), 1
        )
        field = rng.choice(template["fields"]) if template["fields"] else ""
        description = template["description_template"].format(
            service=selected_service, field=field
        )

        fault_params = {
            "fault_id":          str(uuid.uuid4()),
            "category":          selected_category,
            "service":           selected_service,
            "severity":          template["severity"],
            "description":       description,
            "error_rate_percent": error_rate,
            "latency_delta_ms":  template["latency_impact_ms"],
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "bounded":           True,
            "arbitrary_code":    False,
        }
        self._log(f"Generated fault: {selected_category} on {selected_service}")
        return fault_params
