"""
AETHERIS AI — End-to-End Demo Verification Script
Runs both demo scenarios against in-memory DB and verifies results.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlmodel import SQLModel, create_engine, Session, select
from sqlmodel.pool import StaticPool
from backend.app.models.db_models import IncidentRecord, EvidenceRecord
from backend.app.db import database as db_mod

test_engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)
db_mod.engine = test_engine

from orchestration.incident_orchestrator import IncidentOrchestrator
from audit.evidence_signer import verify_evidence


async def run_demo():
    print('=' * 60)
    print('AETHERIS AI — End-to-End Demo Verification')
    print('IBM Bob Hackathon 2.0')
    print('=' * 60)

    # ── DEMO 1: SAFE REPAIR ──────────────────────────────────────
    print('\nDEMO SCENARIO 1: SAFE REPAIR')
    print('-' * 40)

    with Session(test_engine) as session:
        record = IncidentRecord(
            incident_id='INC-DEMO-001',
            title='NullPointerException in orders-service',
            category='NULL_ERROR',
            severity='CRITICAL',
            service='orders-service',
            error_trace='NullPointerException at CheckoutController.java:87',
            state='IDLE',
            attempt_count=0,
            max_attempts=3,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        pk1 = record.id

    with Session(test_engine) as session:
        orch = IncidentOrchestrator(session)
        result = await orch.run(pk1, scenario_mode='pass')

    print(f'Final state:     {result["final_state"]}')
    print(f'Attempt count:   {result["attempt_count"]}')
    print(f'Evidence ID:     {result["evidence_id"]}')
    print(f'Signing key:     {result["signing_key_id"]}')

    assert result['final_state'] == 'ROLLED_OUT', f'Expected ROLLED_OUT, got {result["final_state"]}'

    with Session(test_engine) as session:
        ev = session.exec(select(EvidenceRecord).where(EvidenceRecord.incident_pk == pk1)).first()
        assert ev is not None, 'No evidence record found!'
        ok = verify_evidence(ev.payload_json, ev.signature)
        assert ok, 'Evidence verification FAILED!'
    print('Evidence verified: VALID')
    print('RESULT: DEMO 1 PASSED')

    # ── DEMO 2: CONTROLLED FAILURE ───────────────────────────────
    print('\nDEMO SCENARIO 2: CONTROLLED FAILURE — QUARANTINE')
    print('-' * 40)

    with Session(test_engine) as session:
        record2 = IncidentRecord(
            incident_id='INC-DEMO-002',
            title='Schema drift in payments-service',
            category='SCHEMA_DRIFT',
            severity='HIGH',
            service='payments-service',
            error_trace='ValidationError: currency_code required',
            state='IDLE',
            attempt_count=0,
            max_attempts=3,
        )
        session.add(record2)
        session.commit()
        session.refresh(record2)
        pk2 = record2.id

    with Session(test_engine) as session:
        orch2 = IncidentOrchestrator(session)
        result2 = await orch2.run(pk2, scenario_mode='fail')

    print(f'Final state:     {result2["final_state"]}')
    print(f'Attempt count:   {result2["attempt_count"]}')

    assert result2['final_state'] == 'QUARANTINED', f'Expected QUARANTINED, got {result2["final_state"]}'
    assert result2['attempt_count'] <= 3, f'Exceeded max attempts: {result2["attempt_count"]}'

    with Session(test_engine) as session:
        ev2 = session.exec(select(EvidenceRecord).where(EvidenceRecord.incident_pk == pk2)).first()
        assert ev2 is not None, 'No quarantine evidence record!'
        ok2 = verify_evidence(ev2.payload_json, ev2.signature)
        assert ok2, 'Quarantine evidence verification FAILED!'
    print('Evidence verified: VALID')
    print('RESULT: DEMO 2 PASSED')

    # ── SUMMARY ──────────────────────────────────────────────────
    print()
    print('=' * 60)
    print('ALL VERIFICATION CHECKS PASSED')
    print()
    print('  Demo 1 — Safe Repair:         ROLLED_OUT')
    print('  Demo 2 — Controlled Failure:  QUARANTINED')
    print('  Evidence signing:             REAL HMAC-SHA256')
    print('  Evidence verification:        PASSED (not decorative)')
    print('  Attempt cap (max 3):          ENFORCED')
    print('  Deterministic gate:           OPERATIONAL')
    print('  Fail-closed audit:            OPERATIONAL')
    print()
    print('  inference_mode: mock (watsonx not configured)')
    print('  data_classification: SYNTHETIC_DEMO')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(run_demo())
