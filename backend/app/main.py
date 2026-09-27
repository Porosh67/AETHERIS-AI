"""
AETHERIS AI — FastAPI Backend
Primary REST API serving the dashboard and orchestration.
"""
import json
import logging
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
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
def create_incident(
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
    return _incident_dict(record)


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
    return response


@app.get("/api/incidents/{incident_pk}")
def get_incident(incident_pk: str, session: Session = Depends(get_session)) -> dict:
    record = session.get(IncidentRecord, incident_pk)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _incident_dict(record)


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
    return [
        {
            "id":         log.id,
            "event_type": log.event_type,
            "message":    log.message,
            "detail":     log.detail,
            "timestamp":  log.timestamp.isoformat(),
        }
        for log in logs
    ]


# ── Patch Records ──────────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/patches")
def get_patches(incident_pk: str, session: Session = Depends(get_session)) -> list[dict]:
    patches = session.exec(
        select(PatchRecord)
        .where(PatchRecord.incident_pk == incident_pk)
        .order_by(PatchRecord.attempt_num)
    ).all()
    return [_patch_dict(p) for p in patches]


# ── State Transitions ──────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/transitions")
def get_transitions(incident_pk: str, session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(
        select(StateTransitionLog)
        .where(StateTransitionLog.incident_pk == incident_pk)
        .order_by(StateTransitionLog.timestamp)
    ).all()
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


# ── Evidence ───────────────────────────────────────────────────────

@app.get("/api/incidents/{incident_pk}/evidence")
def get_evidence(incident_pk: str, session: Session = Depends(get_session)) -> dict:
    ev = session.exec(
        select(EvidenceRecord).where(EvidenceRecord.incident_pk == incident_pk)
    ).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not yet available")
    return _evidence_dict(ev)


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
    try:
        file_path = BASE_DIR / "data" / "demo_scenarios.json"
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading scenarios: {e}")
        return []

@app.get("/api/taxonomy")
def get_taxonomy() -> dict:
    return {
        "categories": sorted(APPROVED_INCIDENT_CATEGORIES),
        "services":   sorted(APPROVED_SERVICES),
    }


# ── Telemetry / Data ───────────────────────────────────────────────

@app.get("/api/data/incidents")
def get_data_incidents() -> list[dict]:
    try:
        file_path = BASE_DIR / "data" / "incidents.json"
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/data/telemetry")
def get_telemetry() -> list[dict]:
    try:
        file_path = BASE_DIR / "data" / "telemetry.json"
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/data/snapshots")
def get_snapshots() -> list[dict]:
    try:
        file_path = BASE_DIR / "data" / "service_snapshots.json"
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

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