"""
AETHERIS AI — SQLModel database models
Persistent storage via SQLite. No heavy ORM required.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class IncidentRecord(SQLModel, table=True):
    """Core persistent incident record — state + attempt tracking."""
    __tablename__ = "incidents"

    id:               str      = Field(default_factory=_new_id, primary_key=True)
    incident_id:      str      = Field(index=True)
    title:            str
    category:         str
    severity:         str
    service:          str
    state:            str      = Field(default="IDLE")
    attempt_count:    int      = Field(default=0)
    max_attempts:     int      = Field(default=3)
    created_at:       datetime = Field(default_factory=_utcnow)
    updated_at:       datetime = Field(default_factory=_utcnow)
    error_trace:      Optional[str] = None
    scenario_id:      Optional[str] = None


class StateTransitionLog(SQLModel, table=True):
    """Immutable log of every state transition for auditability."""
    __tablename__ = "state_transitions"

    id:           str      = Field(default_factory=_new_id, primary_key=True)
    incident_pk:  str      = Field(index=True)  # FK to IncidentRecord.id
    from_state:   str
    to_state:     str
    reason:       Optional[str] = None
    attempt_num:  int      = Field(default=0)
    timestamp:    datetime = Field(default_factory=_utcnow)


class PatchRecord(SQLModel, table=True):
    """Stores generated patch content and test/audit results."""
    __tablename__ = "patches"

    id:                  str      = Field(default_factory=_new_id, primary_key=True)
    incident_pk:         str      = Field(index=True)
    attempt_num:         int
    patch_content:       str
    patch_hash:          str
    test_pass_rate:      Optional[float] = None
    test_results:        Optional[str]   = None   # JSON string
    audit_risk_level:    Optional[str]   = None
    audit_findings:      Optional[str]   = None   # JSON string
    audit_trusted:       bool            = Field(default=False)
    gate_passed:         Optional[bool]  = None
    gate_checks:         Optional[str]   = None   # JSON string
    canary_passed:       Optional[bool]  = None
    canary_metrics:      Optional[str]   = None   # JSON string
    latency_ms:          Optional[int]   = None   # total agent pipeline time for this attempt
    model_used:          Optional[str]   = None   # inference model id (or "mock" if not configured)
    created_at:          datetime        = Field(default_factory=_utcnow)


class EvidenceRecord(SQLModel, table=True):
    """Cryptographically signed evidence record for a completed incident."""
    __tablename__ = "evidence"

    id:               str      = Field(default_factory=_new_id, primary_key=True)
    incident_pk:      str      = Field(index=True, unique=True)
    incident_id:      str
    timestamp:        datetime = Field(default_factory=_utcnow)
    affected_service: str
    final_state:      str
    attempt_count:    int
    patch_hash:       Optional[str] = None
    payload_json:     str           # Full evidence payload as JSON
    signing_key_id:   str
    signature:        str           # HMAC-SHA256 hex digest
    verified:         Optional[bool] = None


class BobActivityLog(SQLModel, table=True):
    """Real-time Bob execution trace — event stream persisted to DB."""
    __tablename__ = "bob_activity"

    id:          str      = Field(default_factory=_new_id, primary_key=True)
    incident_pk: str      = Field(index=True)
    event_type:  str      # e.g. BOB_INFO, BOB_SUCCESS, BOB_WARNING, BOB_ERROR
    message:     str
    detail:      Optional[str] = None
    timestamp:   datetime = Field(default_factory=_utcnow)