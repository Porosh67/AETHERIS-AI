"""
AETHERIS AI — Incident Normalizer

Converts raw free-text incident input into a normalized incident record
ready for the standard diagnosis pipeline.

All user input is treated strictly as DATA — never executed as code.

If the input cannot be normalized, returns a NEEDS_CLARIFICATION result
with a clear reason. This does NOT consume a patch retry slot.
"""
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional

# Input size limits — security: prevent oversized payloads
MAX_DESCRIPTION_LEN = 4000
MAX_STACK_TRACE_LEN = 8000

# Approved service names — user cannot inject arbitrary service names
APPROVED_SERVICES = [
    "gateway-service",
    "orders-service",
    "payments-service",
    "inventory-service",
    "unknown-service",  # fallback for custom inputs
]

# Keyword heuristics for category detection (data-driven, not code execution)
CATEGORY_SIGNALS: list[tuple[str, list[str]]] = [
    ("NULL_ERROR", [
        "null", "nullpointer", "npe", "nonetype", "none type",
        "attributeerror", "typeerror: 'none'", "is not defined",
        "undefined", "cannot read property", "null reference",
    ]),
    ("SCHEMA_DRIFT", [
        "schema", "missing field", "required field", "validation error",
        "field.*required", "unexpected field", "payload", "serialization",
        "keyerror", "missing key", "required but not found",
    ]),
    ("LATENCY_REGRESSION", [
        "timeout", "latency", "slow", "p99", "sla", "response time",
        "took too long", "deadline exceeded", "timed out",
    ]),
    ("RATE_LIMIT_MISCONFIGURATION", [
        "429", "too many requests", "rate limit", "throttle", "quota exceeded",
        "ratelimit", "rate_limit", "burst",
    ]),
    ("DEPENDENCY_FAILURE", [
        "connection refused", "connection reset", "econnrefused", "unreachable",
        "upstream", "dependency", "service unavailable", "503", "circuit breaker",
        "dns", "host not found", "cannot connect",
    ]),
    ("RESOURCE_EXHAUSTION", [
        "out of memory", "oom", "memory error", "memoryerror", "disk full",
        "no space", "cpu", "exhausted", "resource limit", "killed",
        "java heap space", "gc overhead",
    ]),
]

SEVERITY_SIGNALS: list[tuple[str, list[str]]] = [
    ("CRITICAL", ["critical", "fatal", "crash", "down", "outage", "100%", "all requests"]),
    ("HIGH",     ["high", "degraded", "major", "significant", "most"]),
    ("MEDIUM",   ["medium", "moderate", "some", "intermittent", "flapping"]),
    ("LOW",      ["low", "minor", "occasionally", "rare"]),
]

SERVICE_SIGNALS: list[tuple[str, list[str]]] = [
    ("orders-service",    ["order", "checkout", "cart", "purchase"]),
    ("payments-service",  ["payment", "charge", "billing", "transaction", "currency"]),
    ("inventory-service", ["inventory", "stock", "sku", "product", "warehouse"]),
    ("gateway-service",   ["gateway", "proxy", "api gateway", "rate limit", "routing"]),
]


@dataclass
class NormalizedIncident:
    """Successfully normalized incident — ready for the standard pipeline."""
    incident_id: str
    title: str
    category: str
    severity: str
    service: str
    error_trace: str
    source: str   # "preset" | "custom"
    raw_description: str
    raw_stack_trace: str
    normalized: bool = True
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None


@dataclass
class NormalizationFailure:
    """Normalization could not determine a valid incident — pipeline not entered."""
    needs_clarification: bool = True
    normalized: bool = False
    reason: str = ""
    suggestion: str = ""


def _detect_category(text: str) -> str:
    lower = text.lower()
    for category, signals in CATEGORY_SIGNALS:
        for signal in signals:
            if re.search(signal, lower):
                return category
    return "NULL_ERROR"  # conservative default


def _detect_severity(text: str) -> str:
    lower = text.lower()
    for severity, signals in SEVERITY_SIGNALS:
        for signal in signals:
            if signal in lower:
                return severity
    return "HIGH"  # conservative default


def _detect_service(text: str) -> str:
    lower = text.lower()
    for service, signals in SERVICE_SIGNALS:
        for signal in signals:
            if signal in lower:
                return service
    return "unknown-service"


def _generate_incident_id(description: str) -> str:
    digest = hashlib.sha256(description.encode("utf-8")).hexdigest()[:8].upper()
    return f"INC-CUSTOM-{digest}"


def _extract_title(description: str) -> str:
    """Extract a concise title from the first meaningful line."""
    lines = [ln.strip() for ln in description.splitlines() if ln.strip()]
    if not lines:
        return "Custom incident"
    first = lines[0]
    # Truncate to 120 chars
    return first[:120] + ("..." if len(first) > 120 else "")


def _sanitize_text(text: str, max_len: int) -> str:
    """
    Sanitize user input: strip null bytes, control chars (except newline/tab),
    truncate to max_len. Treat as data only.
    """
    # Remove null bytes and most control characters (keep \n \t \r)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return sanitized[:max_len]


def normalize_custom_incident(
    description: str,
    stack_trace: str = "",
) -> NormalizedIncident | NormalizationFailure:
    """
    Normalize a custom free-text incident into a structured record.

    Security guarantees:
    - Input is treated strictly as DATA
    - No eval, exec, or subprocess calls
    - Input size is enforced
    - Output schema is fixed — user cannot inject new fields

    Returns NormalizedIncident on success, NormalizationFailure on failure.
    The failure does NOT consume a repair retry slot.
    """
    # ── Input validation ─────────────────────────────────────────
    if not description or not description.strip():
        return NormalizationFailure(
            reason="Incident description is empty.",
            suggestion="Provide a description of the incident, e.g. an error message or service impact.",
        )

    if len(description) > MAX_DESCRIPTION_LEN:
        return NormalizationFailure(
            reason=f"Description exceeds maximum length ({MAX_DESCRIPTION_LEN} chars).",
            suggestion=f"Shorten the description to under {MAX_DESCRIPTION_LEN} characters.",
        )

    if len(stack_trace) > MAX_STACK_TRACE_LEN:
        return NormalizationFailure(
            reason=f"Stack trace exceeds maximum length ({MAX_STACK_TRACE_LEN} chars).",
            suggestion=f"Truncate the stack trace to under {MAX_STACK_TRACE_LEN} characters.",
        )

    # ── Sanitize ─────────────────────────────────────────────────
    clean_desc = _sanitize_text(description, MAX_DESCRIPTION_LEN)
    clean_trace = _sanitize_text(stack_trace, MAX_STACK_TRACE_LEN)

    # Combined text for signal detection
    combined = f"{clean_desc}\n{clean_trace}"

    # ── Detection ────────────────────────────────────────────────
    category = _detect_category(combined)
    severity = _detect_severity(combined)
    service  = _detect_service(combined)
    title    = _extract_title(clean_desc)

    # Build error_trace from stack_trace or fallback to description
    error_trace = clean_trace if clean_trace.strip() else clean_desc[:500]

    incident_id = _generate_incident_id(clean_desc)

    return NormalizedIncident(
        incident_id=incident_id,
        title=title,
        category=category,
        severity=severity,
        service=service,
        error_trace=error_trace,
        source="custom",
        raw_description=clean_desc,
        raw_stack_trace=clean_trace,
    )
