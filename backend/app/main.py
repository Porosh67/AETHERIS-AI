"""
AETHERIS AI — FastAPI Backend
Primary REST API serving the dashboard and orchestration.
"""
import json
import logging
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from .core.config import get_settings
from .db.database import create_db_and_tables, get_session, engine
from .models.db_models import (
    IncidentRecord,
    BobActivityLog,
    PatchRecord,
    EvidenceRecord,
    StateTransitionLog,
)
from .core.state_machine import IncidentState, is_terminal
from orchestration.incident_orchestrator import IncidentOrchestrator
from agents.chaos_agent import ChaosAgent, APPROVED_INCIDENT_CATEGORIES, APPROVED_SERVICES
from audit.evidence_signer import verify_evidence
from app.services.incident_normalizer import (
    normalize_custom_incident,
    NormalizedIncident,
    NormalizationFailure,
    MAX_DESCRIPTION_LEN,
    MAX_STACK_TRACE_LEN,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aetheris.api")
settings = get_settings()

# ── In-memory cache (survives warm serverless instances; fixes SQLite /tmp isolation) ──
_INCIDENT_CACHE: dict[str, dict] = {}
_ACTIVITY_CACHE: dict[str, list] = {}
_PATCH_CACHE: dict[str, list] = {}
_TRANSITION_CACHE: dict[str, list] = {}
_EVIDENCE_CACHE: dict[str, dict] = {}


def _hydrate_caches(session, incident_pk: str) -> dict:
    """Load incident + related rows into memory caches (for serverless)."""
    record = session.get(IncidentRecord, incident_pk)
    if not record:
        return {}
    result = _incident_dict(record)
    _INCIDENT_CACHE[incident_pk] = result
    try:
        acts = session.exec(
            select(BobActivityLog)
            .where(BobActivityLog.incident_pk == incident_pk)
            .order_by(BobActivityLog.timestamp)
        ).all()
        _ACTIVITY_CACHE[incident_pk] = [
            {
                "id": a.id,
                "event_type": a.event_type,
                "message": a.message,
                "detail": a.detail,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in acts
        ]
    except Exception as e:
        logger.warning(f"cache activity: {e}")
    try:
        patches = session.exec(
            select(PatchRecord)
            .where(PatchRecord.incident_pk == incident_pk)
            .order_by(PatchRecord.attempt_num)
        ).all()
        _PATCH_CACHE[incident_pk] = [_patch_dict(p) for p in patches]
    except Exception as e:
        logger.warning(f"cache patches: {e}")
    try:
        trans = session.exec(
            select(StateTransitionLog)
            .where(StateTransitionLog.incident_pk == incident_pk)
            .order_by(StateTransitionLog.timestamp)
        ).all()
        _TRANSITION_CACHE[incident_pk] = [
            {
                "from_state": t.from_state,
                "to_state": t.to_state,
                "reason": t.reason,
                "attempt_num": t.attempt_num,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in trans
        ]
    except Exception as e:
        logger.warning(f"cache transitions: {e}")
    try:
        ev = session.exec(
            select(EvidenceRecord).where(EvidenceRecord.incident_pk == incident_pk)
        ).first()
        if ev:
            _EVIDENCE_CACHE[incident_pk] = _evidence_dict(ev)
    except Exception as e:
        logger.warning(f"cache evidence: {e}")
    # Attach related data onto response for single-shot UI
    result["_activity"] = _ACTIVITY_CACHE.get(incident_pk, [])
    result["_patches"] = _PATCH_CACHE.get(incident_pk, [])
    result["_transitions"] = _TRANSITION_CACHE.get(incident_pk, [])
    result["_evidence"] = _EVIDENCE_CACHE.get(incident_pk)
    return result


# ── Embedded demo data (no filesystem dependency on Vercel) ────────
_DEMO_SCENARIOS = json.loads(r"""[
  {
    "scenario_id": "DEMO-001",
    "name": "Safe Repair — NULL_ERROR in orders-service",
    "description": "A NullPointerException in the orders-service checkout flow is detected. Bob diagnoses, generates a patch, tests pass, audit passes, deterministic gate passes, canary is healthy, rollout succeeds.",
    "incident_id": "INC-2024-001",
    "expected_outcome": "ROLLED_OUT",
    "expected_attempts": 1,
    "fault_type": "NULL_ERROR",
    "target_service": "orders-service",
    "synthetic_patch": {
      "file": "services/orders-service/checkout_controller.py",
      "description": "Add null guard before accessing user_id field",
      "diff_summary": "Line 87: if user_id is None: raise ValueError('user_id required')"
    },
    "gate_thresholds": {
      "min_test_pass_rate": 0.95,
      "max_security_risk": "MEDIUM",
      "max_regression_risk": "LOW",
      "canary_error_rate_threshold": 0.02,
      "canary_latency_threshold_ms": 500
    },
    "synthetic": true
  },
  {
    "scenario_id": "DEMO-002",
    "name": "Controlled Failure — SCHEMA_DRIFT exhausts all 3 attempts → QUARANTINED",
    "description": "A schema drift incident in payments-service triggers 3 repair attempts. Each attempt generates a patch that fails validation (simulated progressive failure). After attempt 3, the system quarantines and requires human review.",
    "incident_id": "INC-2024-002",
    "expected_outcome": "QUARANTINED",
    "expected_attempts": 3,
    "fault_type": "SCHEMA_DRIFT",
    "target_service": "payments-service",
    "synthetic_patch": {
      "file": "services/payments-service/payment_processor.py",
      "description": "Restore backward-compatible currency_code default (fails on all 3 attempts due to downstream schema mismatch)",
      "diff_summary": "Line 112: currency_code = payload.get('currency_code', 'USD')"
    },
    "gate_thresholds": {
      "min_test_pass_rate": 0.95,
      "max_security_risk": "MEDIUM",
      "max_regression_risk": "LOW",
      "canary_error_rate_threshold": 0.02,
      "canary_latency_threshold_ms": 500
    },
    "synthetic": true
  }
]""")
_DATA_INCIDENTS = json.loads(r"""[
  {
    "incident_id": "INC-2024-001",
    "title": "NullPointerException in orders-service checkout flow",
    "category": "NULL_ERROR",
    "severity": "CRITICAL",
    "service": "orders-service",
    "timestamp": "2024-01-15T08:23:11Z",
    "error_trace": "java.lang.NullPointerException\n  at com.aetheris.orders.CheckoutController.processOrder(CheckoutController.java:87)\n  at com.aetheris.orders.CheckoutController.checkout(CheckoutController.java:45)\n  at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)\nCaused by: user_id field returned null from downstream identity resolver",
    "affected_endpoint": "/api/v1/orders/checkout",
    "error_rate_percent": 23.4,
    "latency_p99_ms": 4200,
    "synthetic": true
  },
  {
    "incident_id": "INC-2024-002",
    "title": "Schema drift: payments-service missing required field 'currency_code'",
    "category": "SCHEMA_DRIFT",
    "severity": "HIGH",
    "service": "payments-service",
    "timestamp": "2024-01-15T10:41:33Z",
    "error_trace": "ValidationError: Field 'currency_code' is required but was not found in payload\n  at PaymentProcessor.validate(payment_processor.py:112)\n  at PaymentProcessor.charge(payment_processor.py:78)\nDeploy v2.3.1 removed backward-compatible currency_code default",
    "affected_endpoint": "/api/v1/payments/charge",
    "error_rate_percent": 45.1,
    "latency_p99_ms": 850,
    "synthetic": true
  },
  {
    "incident_id": "INC-2024-003",
    "title": "Latency regression in inventory-service stock lookup",
    "category": "LATENCY_REGRESSION",
    "severity": "HIGH",
    "service": "inventory-service",
    "timestamp": "2024-01-15T14:17:55Z",
    "error_trace": "TimeoutError: Upstream call to inventory DB exceeded 5000ms SLA\n  at InventoryService.getStock(inventory_service.py:201)\nQuery plan regression detected: full table scan on product_id without index",
    "affected_endpoint": "/api/v1/inventory/stock",
    "error_rate_percent": 8.7,
    "latency_p99_ms": 8900,
    "synthetic": true
  },
  {
    "incident_id": "INC-2024-004",
    "title": "Rate limiter misconfiguration causing 429 storms in gateway",
    "category": "RATE_LIMIT_MISCONFIGURATION",
    "severity": "MEDIUM",
    "service": "gateway-service",
    "timestamp": "2024-01-15T16:03:22Z",
    "error_trace": "HTTP 429 Too Many Requests\n  at GatewayRateLimiter.check(rate_limiter.py:67)\nConfig change in deploy v1.9.2 reduced per-user limit from 1000/min to 10/min",
    "affected_endpoint": "/api/v1/*",
    "error_rate_percent": 61.2,
    "latency_p99_ms": 220,
    "synthetic": true
  },
  {
    "incident_id": "INC-2024-005",
    "title": "Dependency failure: orders-service cannot reach payments-service",
    "category": "DEPENDENCY_FAILURE",
    "severity": "CRITICAL",
    "service": "orders-service",
    "timestamp": "2024-01-16T02:11:44Z",
    "error_trace": "ConnectionRefusedError: [Errno 111] Connection refused\n  at PaymentsClient.charge(payments_client.py:34)\n  at OrdersService.completeOrder(orders_service.py:156)\nService discovery returned stale endpoint after payments-service pod restart",
    "affected_endpoint": "/api/v1/orders/complete",
    "error_rate_percent": 100.0,
    "latency_p99_ms": 30000,
    "synthetic": true
  },
  {
    "incident_id": "INC-2024-006",
    "title": "Resource exhaustion: inventory-service OOM under high load",
    "category": "RESOURCE_EXHAUSTION",
    "severity": "HIGH",
    "service": "inventory-service",
    "timestamp": "2024-01-16T09:45:12Z",
    "error_trace": "MemoryError: Unable to allocate 512MB for batch stock computation\n  at InventoryBatchProcessor.compute(batch_processor.py:88)\nUnbounded in-memory accumulation of SKU records during bulk import",
    "affected_endpoint": "/api/v1/inventory/bulk-update",
    "error_rate_percent": 34.8,
    "latency_p99_ms": 15600,
    "synthetic": true
  }
]""")
_DATA_TELEMETRY = json.loads(r"""[
  {
    "metric": "requests_per_min",
    "service": "orders-service",
    "timestamps": ["08:00","08:05","08:10","08:15","08:20","08:25"],
    "values":     [1820,   1834,   1810,   1799,   412,    88],
    "unit": "req/min",
    "synthetic": true
  },
  {
    "metric": "p99_latency_ms",
    "service": "orders-service",
    "timestamps": ["08:00","08:05","08:10","08:15","08:20","08:25"],
    "values":     [182,    190,    210,    850,    4200,   4800],
    "unit": "ms",
    "synthetic": true
  },
  {
    "metric": "error_rate_percent",
    "service": "orders-service",
    "timestamps": ["08:00","08:05","08:10","08:15","08:20","08:25"],
    "values":     [0.3,    0.4,    1.2,    8.9,    23.4,   31.1],
    "unit": "%",
    "synthetic": true
  },
  {
    "metric": "error_rate_percent",
    "service": "payments-service",
    "timestamps": ["10:30","10:35","10:40","10:45","10:50"],
    "values":     [0.8,    2.1,    12.4,   45.1,   48.3],
    "unit": "%",
    "synthetic": true
  },
  {
    "metric": "p99_latency_ms",
    "service": "inventory-service",
    "timestamps": ["14:00","14:05","14:10","14:15","14:20"],
    "values":     [95,     102,    680,    3200,   8900],
    "unit": "ms",
    "synthetic": true
  }
]""")
_DATA_SNAPSHOTS = json.loads(r"""[
  {
    "snapshot_id": "SNAP-001",
    "timestamp": "2024-01-15T08:20:00Z",
    "services": {
      "gateway-service": {"status": "healthy", "cpu_percent": 34.2, "memory_mb": 512, "requests_per_min": 4200, "error_rate_percent": 0.4, "p99_latency_ms": 85},
      "orders-service":   {"status": "degraded","cpu_percent": 89.1, "memory_mb": 1024,"requests_per_min": 1800, "error_rate_percent": 23.4,"p99_latency_ms": 4200},
      "payments-service": {"status": "healthy", "cpu_percent": 41.0, "memory_mb": 768, "requests_per_min": 1600, "error_rate_percent": 0.8, "p99_latency_ms": 230},
      "inventory-service":{"status": "healthy", "cpu_percent": 28.5, "memory_mb": 480, "requests_per_min": 3100, "error_rate_percent": 0.2, "p99_latency_ms": 95}
    },
    "synthetic": true
  },
  {
    "snapshot_id": "SNAP-002",
    "timestamp": "2024-01-15T10:38:00Z",
    "services": {
      "gateway-service": {"status": "healthy", "cpu_percent": 38.7, "memory_mb": 520, "requests_per_min": 4100, "error_rate_percent": 0.3, "p99_latency_ms": 90},
      "orders-service":   {"status": "healthy", "cpu_percent": 42.3, "memory_mb": 800, "requests_per_min": 1900, "error_rate_percent": 0.5, "p99_latency_ms": 180},
      "payments-service": {"status": "critical","cpu_percent": 71.2, "memory_mb": 900, "requests_per_min": 1700, "error_rate_percent": 45.1,"p99_latency_ms": 850},
      "inventory-service":{"status": "healthy", "cpu_percent": 30.1, "memory_mb": 490, "requests_per_min": 3000, "error_rate_percent": 0.1, "p99_latency_ms": 88}
    },
    "synthetic": true
  }
]""")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    logger.info("[AETHERIS] Database tables ready")
    yield


app = FastAPI(
    title="AETHERIS AI",
    description="Autonomous Incident Resolution — IBM Bob Hackathon 2.0",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ──────────────────────────────────────

class CreateIncidentRequest(BaseModel):
    incident_id:  str
    title:        str
    category:     str
    severity:     str
    service:      str
    error_trace:  str
    scenario_id:  str | None = None
    auto_run:     bool = False
    scenario_mode: str = "pass"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in APPROVED_INCIDENT_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(APPROVED_INCIDENT_CATEGORIES)}")
        return v

    @field_validator("service")
    @classmethod
    def validate_service(cls, v: str) -> str:
        if v not in APPROVED_SERVICES:
            raise ValueError(f"service must be one of {sorted(APPROVED_SERVICES)}")
        return v


class RunWorkflowRequest(BaseModel):
    scenario_mode: str = "pass"

    @field_validator("scenario_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("pass", "fail", "custom"):
            raise ValueError("scenario_mode must be 'pass', 'fail', or 'custom'")
        return v


class CustomIncidentRequest(BaseModel):
    """
    Free-text custom incident intake.
    User input is treated strictly as data — never executed.
    """
    description: str
    stack_trace: str = ""
    auto_run: bool = False
    scenario_mode: str = "custom"

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("description cannot be empty")
        if len(v) > MAX_DESCRIPTION_LEN:
            raise ValueError(f"description exceeds {MAX_DESCRIPTION_LEN} char limit")
        return v

    @field_validator("stack_trace")
    @classmethod
    def validate_stack_trace(cls, v: str) -> str:
        if len(v) > MAX_STACK_TRACE_LEN:
            raise ValueError(f"stack_trace exceeds {MAX_STACK_TRACE_LEN} char limit")
        return v


# ── Health ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AETHERIS AI Backend",
        "version": "1.0.0",
        "watsonx_configured": settings.watsonx_configured,
        "inference_mode": "watsonx" if settings.watsonx_configured else "mock",
    }


# ── Incidents ──────────────────────────────────────────────────────

@app.get("/api/incidents")
def list_incidents(session: Session = Depends(get_session)) -> list[dict]:
    records = session.exec(select(IncidentRecord)).all()
    return [_incident_dict(r) for r in records]


@app.post("/api/incidents", status_code=201)
async def create_incident(
    req: CreateIncidentRequest,
    session: Session = Depends(get_session),
) -> dict:
    record = IncidentRecord(
        incident_id=req.incident_id,
        title=req.title,
        category=req.category,
        severity=req.severity,
        service=req.service,
        error_trace=req.error_trace,
        scenario_id=req.scenario_id,
        state=IncidentState.IDLE.value,
        attempt_count=0,
        max_attempts=settings.max_repair_attempts,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    result = _incident_dict(record)
    _INCIDENT_CACHE[record.id] = result

    # Run workflow in the SAME request (avoids SQLite /tmp isolation across lambdas)
    if req.auto_run:
        mode = req.scenario_mode if req.scenario_mode in ("pass", "fail", "custom") else "pass"
        orchestrator = IncidentOrchestrator(session)
        await orchestrator.run(record.id, scenario_mode=mode)
        session.refresh(record)
        result = _hydrate_caches(session, record.id)

    return result


@app.post("/api/incidents/custom", status_code=201)
async def create_custom_incident(
    req: CustomIncidentRequest,
    session: Session = Depends(get_session),
) -> dict:
    """
    Custom incident intake from free-text description + optional stack trace.

    The input is normalized via the IncidentNormalizer — the SAME downstream
    pipeline (diagnosis -> patch -> audit -> gate -> canary) is used.

    If normalization fails, returns 422 with NEEDS_CLARIFICATION reason.
    Normalization failure does NOT consume a patch retry slot.

    Security: input is treated strictly as data. Never executed.
    """
    result = normalize_custom_incident(
        description=req.description,
        stack_trace=req.stack_trace,
    )

    if isinstance(result, NormalizationFailure):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "NEEDS_CLARIFICATION",
                "reason": result.reason,
                "suggestion": result.suggestion,
            },
        )

    # normalized: NormalizedIncident — create the incident record
    record = IncidentRecord(
        incident_id=result.incident_id,
        title=result.title,
        category=result.category,
        severity=result.severity,
        service=result.service if result.service != "unknown-service" else "orders-service",
        error_trace=result.error_trace,
        scenario_id="custom",
        state=IncidentState.IDLE.value,
        attempt_count=0,
        max_attempts=settings.max_repair_attempts,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    response = _incident_dict(record)
    response["source"] = "custom"
    response["normalized"] = {
        "category_detected": result.category,
        "severity_detected": result.severity,
        "service_detected":  result.service,
        "raw_description":   result.raw_description[:200],
    }
    _INCIDENT_CACHE[record.id] = response

    if req.auto_run:
        mode = req.scenario_mode if req.scenario_mode in ("pass", "fail", "custom") else "custom"
        orchestrator = IncidentOrchestrator(session)
        await orchestrator.run(record.id, scenario_mode=mode)
        session.refresh(record)
        response = _hydrate_caches(session, record.id)
        response["source"] = "custom"

    return response


@app.get("/api/incidents/{incident_pk}")
def get_incident(incident_pk: str, session: Session = Depends(get_session)) -> dict:
    record = session.get(IncidentRecord, incident_pk)
    if record:
        d = _incident_dict(record)
        _INCIDENT_CACHE[incident_pk] = d
        return d
    if incident_pk in _INCIDENT_CACHE:
        return _INCIDENT_CACHE[incident_pk]
    raise HTTPException(status_code=404, detail="Incident not found")


@app.post("/api/incidents/{incident_pk}/run")
async def run_workflow(
    incident_pk: str,
    req: RunWorkflowRequest,
    session: Session = Depends(get_session),
) -> dict:
    """
    Trigger the full orchestration workflow for an incident.
    Returns after workflow completes (synchronous for demo reliability).
    """
    record = session.get(IncidentRecord, incident_pk)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")

    if is_terminal(IncidentState(record.state)):
        raise HTTPException(
            status_code=409,
            detail=f"Incident is already in terminal state: {record.state}",
        )

    orchestrator = IncidentOrchestrator(session)
    result = await orchestrator.run(incident_pk, scenario_mode=req.scenario_mode)
    session.refresh(record)
    hydrated = _hydrate_caches(session, incident_pk)
    if isinstance(result, dict):
        result.update({k: hydrated.get(k) for k in ("_activity", "_patches", "_transitions", "_evidence") if k in hydrated})
    return result


@app.delete("/api/incidents/{incident_pk}/reset")
def reset_incident(incident_pk: str, session: Session = Depends(get_session)) -> dict:
    """Reset an incident to IDLE for re-running demo scenarios."""
    record = session.get(IncidentRecord, incident_pk)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")

    record.state          = IncidentState.IDLE.value
    record.attempt_count  = 0
    session.add(record)

    # Clear related records for clean demo re-run
    for model in (StateTransitionLog, PatchRecord, EvidenceRecord, BobActivityLog):
        rows = session.exec(
            select(model).where(model.incident_pk == incident_pk)
        ).all()
        for row in rows:
            session.delete(row)

    session.commit()
    return {"status": "reset", "incident_pk": incident_pk}


# ── Bob Activity Stream ────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/activity")
def get_activity(
    incident_pk: str,
    session: Session = Depends(get_session),
) -> list[dict]:
    logs = session.exec(
        select(BobActivityLog)
        .where(BobActivityLog.incident_pk == incident_pk)
        .order_by(BobActivityLog.timestamp)
    ).all()
    if logs:
        data = [
            {
                "id":         log.id,
                "event_type": log.event_type,
                "message":    log.message,
                "detail":     log.detail,
                "timestamp":  log.timestamp.isoformat(),
            }
            for log in logs
        ]
        _ACTIVITY_CACHE[incident_pk] = data
        return data
    return _ACTIVITY_CACHE.get(incident_pk, [])


# ── Patch Records ──────────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/patches")
def get_patches(incident_pk: str, session: Session = Depends(get_session)) -> list[dict]:
    patches = session.exec(
        select(PatchRecord)
        .where(PatchRecord.incident_pk == incident_pk)
        .order_by(PatchRecord.attempt_num)
    ).all()
    if patches:
        data = [_patch_dict(p) for p in patches]
        _PATCH_CACHE[incident_pk] = data
        return data
    return _PATCH_CACHE.get(incident_pk, [])


# ── State Transitions ──────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/transitions")
def get_transitions(incident_pk: str, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(
        select(StateTransitionLog)
        .where(StateTransitionLog.incident_pk == incident_pk)
        .order_by(StateTransitionLog.timestamp)
    ).all()
    if rows:
        data = [
            {
                "from_state":  r.from_state,
                "to_state":    r.to_state,
                "reason":      r.reason,
                "attempt_num": r.attempt_num,
                "timestamp":   r.timestamp.isoformat(),
            }
            for r in rows
        ]
        _TRANSITION_CACHE[incident_pk] = data
        return data
    return _TRANSITION_CACHE.get(incident_pk, [])


# ── Evidence ───────────────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/evidence")
def get_evidence(incident_pk: str, session: Session = Depends(get_session)) -> dict:
    ev = session.exec(
        select(EvidenceRecord).where(EvidenceRecord.incident_pk == incident_pk)
    ).first()
    if ev:
        data = _evidence_dict(ev)
        _EVIDENCE_CACHE[incident_pk] = data
        return data
    if incident_pk in _EVIDENCE_CACHE:
        return _EVIDENCE_CACHE[incident_pk]
    raise HTTPException(status_code=404, detail="Evidence not yet available")


@app.post("/api/incidents/{incident_pk}/evidence/verify")
def verify_evidence_endpoint(
    incident_pk: str,
    session: Session = Depends(get_session),
) -> dict:
    """
    Actually verify the evidence signature.
    UI only shows VALID if this returns verified=True.
    """
    ev = session.exec(
        select(EvidenceRecord).where(EvidenceRecord.incident_pk == incident_pk)
    ).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")

    verified = verify_evidence(ev.payload_json, ev.signature)

    # Update stored verification result
    ev.verified = verified
    session.add(ev)
    session.commit()

    return {
        "verified":       verified,
        "signing_key_id": ev.signing_key_id,
        "signature":      ev.signature[:16] + "...",
        "incident_id":    ev.incident_id,
        "final_state":    ev.final_state,
        "attempt_count":  ev.attempt_count,
    }


# ── Chaos / Scenario Generation ────────────────────────────────────

@app.get("/api/scenarios")
def list_scenarios() -> list[dict]:
    return _DEMO_SCENARIOS


@app.get("/api/taxonomy")
def get_taxonomy() -> dict:
    return {
        "categories": sorted(APPROVED_INCIDENT_CATEGORIES),
        "services":   sorted(APPROVED_SERVICES),
    }


# ── Telemetry / Data ───────────────────────────────────────────────

@app.get("/api/data/incidents")
def get_data_incidents() -> list[dict]:
    return _DATA_INCIDENTS


@app.get("/api/data/telemetry")
def get_telemetry() -> list[dict]:
    return _DATA_TELEMETRY


@app.get("/api/data/snapshots")
def get_snapshots() -> list[dict]:
    return _DATA_SNAPSHOTS


# ── Helpers ────────────────────────────────────────────────────────

def _incident_dict(r: IncidentRecord) -> dict:
    return {
        "id":            r.id,
        "incident_id":   r.incident_id,
        "title":         r.title,
        "category":      r.category,
        "severity":      r.severity,
        "service":       r.service,
        "state":         r.state,
        "attempt_count": r.attempt_count,
        "max_attempts":  r.max_attempts,
        "created_at":    r.created_at.isoformat(),
        "updated_at":    r.updated_at.isoformat(),
        "scenario_id":   r.scenario_id,
    }


def _patch_dict(p: PatchRecord) -> dict:
    content = {}
    try:
        content = json.loads(p.patch_content) if p.patch_content else {}
    except Exception:
        pass
    audit = {}
    try:
        audit = json.loads(p.audit_findings) if p.audit_findings else {}
    except Exception:
        pass
    tests = {}
    try:
        tests = json.loads(p.test_results) if p.test_results else {}
    except Exception:
        pass
    gate = {}
    try:
        gate = json.loads(p.gate_checks) if p.gate_checks else {}
    except Exception:
        pass
    canary = {}
    try:
        canary = json.loads(p.canary_metrics) if p.canary_metrics else {}
    except Exception:
        pass
    return {
        "id":             p.id,
        "attempt_num":    p.attempt_num,
        "patch_hash":     p.patch_hash,
        "test_pass_rate": p.test_pass_rate,
        "audit_trusted":  p.audit_trusted,
        "audit_risk_level": p.audit_risk_level,
        "gate_passed":    p.gate_passed,
        "canary_passed":  p.canary_passed,
        "content":        content,
        "audit":          audit,
        "tests":          tests,
        "gate":           gate,
        "canary":         canary,
        "latency_ms":     p.latency_ms,
        "model_used":     p.model_used,
        "created_at":     p.created_at.isoformat(),
    }


def _evidence_dict(ev: EvidenceRecord) -> dict:
    payload = {}
    try:
        payload = json.loads(ev.payload_json)
    except Exception:
        pass
    return {
        "id":             ev.id,
        "incident_id":    ev.incident_id,
        "affected_service": ev.affected_service,
        "final_state":    ev.final_state,
        "attempt_count":  ev.attempt_count,
        "patch_hash":     ev.patch_hash,
        "signing_key_id": ev.signing_key_id,
        "signature":      ev.signature,
        "verified":       ev.verified,
        "timestamp":      ev.timestamp.isoformat(),
        "payload":        payload,
    }