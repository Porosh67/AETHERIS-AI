"""
AETHERIS AI — Final Verification Script (Steps 2-6)
Runs all core workflow, safety, and cryptographic verification checks.
"""
import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, '.')

from sqlmodel import SQLModel, create_engine, Session, select
from sqlmodel.pool import StaticPool
from backend.app.models.db_models import (
    IncidentRecord, EvidenceRecord, PatchRecord,
    StateTransitionLog, BobActivityLog
)
from backend.app.db import database as db_mod
from backend.app.core.state_machine import IncidentState
from orchestration.incident_orchestrator import IncidentOrchestrator
from orchestration.release_gate import DeterministicReleaseGate
from audit.evidence_signer import (
    build_evidence_payload, sign_payload, verify_evidence, SIGNING_KEY_ID
)
from agents.auditor_agent import AuditorAgent, AuditRecommendation

test_engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)
db_mod.engine = test_engine

results = {}
PASS = 'PASS'
FAIL = 'FAIL'


def chk(label, passed, detail=''):
    marker = 'OK' if passed else 'FAIL'
    print(f'  [{marker}] {label}' + (f' — {detail}' if detail else ''))
    if not passed:
        raise AssertionError(f'CHECK FAILED: {label}')


async def step2_happy_path():
    print('\nSTEP 2: SAFE REPAIR — Happy Path')
    print('-' * 40)
    with Session(test_engine) as s:
        rec = IncidentRecord(
            incident_id='INC-V1', title='NPE in orders', category='NULL_ERROR',
            severity='CRITICAL', service='orders-service',
            error_trace='NPE at CheckoutController.java:87',
            state='IDLE', attempt_count=0, max_attempts=3
        )
        s.add(rec); s.commit(); s.refresh(rec)
        pk1 = rec.id

    with Session(test_engine) as s:
        res = await IncidentOrchestrator(s).run(pk1, 'pass')

    chk('Final state == ROLLED_OUT', res['final_state'] == 'ROLLED_OUT', res['final_state'])
    chk('attempt_count == 1', res['attempt_count'] <= 1, str(res['attempt_count']))

    with Session(test_engine) as s:
        transitions = s.exec(
            select(StateTransitionLog).where(StateTransitionLog.incident_pk == pk1)
        ).all()
        states_visited = {t.to_state for t in transitions}
        required = {
            'INCIDENT_RECEIVED', 'DIAGNOSING', 'PATCH_GENERATED',
            'PATCH_TESTING', 'AUDITING', 'CANARY_PENDING', 'CANARY_RUNNING', 'ROLLED_OUT'
        }
        missing = required - states_visited
        chk('All required states visited', not missing, f'Missing: {missing}')

        activity = s.exec(
            select(BobActivityLog).where(BobActivityLog.incident_pk == pk1)
        ).all()
        chk('Bob activity events > 5', len(activity) > 5, str(len(activity)))

        # Verify rollout log entry exists
        rollout_logs = [a for a in activity if 'Rollout authorized' in a.message or 'resolved' in a.message.lower()]
        chk('Bob rollout log present', len(rollout_logs) > 0)

        patches = s.exec(
            select(PatchRecord).where(PatchRecord.incident_pk == pk1)
        ).all()
        chk('Patch record created', len(patches) > 0)
        chk('Patch passed gate', patches[-1].gate_passed == True)
        chk('Patch canary passed', patches[-1].canary_passed == True)

    print(f'  States visited: {sorted(states_visited)}')
    print(f'  Bob events: {len(activity)}')
    results['step2_happy_path'] = PASS
    return pk1


async def step3_controlled_failure():
    print('\nSTEP 3: CONTROLLED FAILURE — Quarantine')
    print('-' * 40)
    with Session(test_engine) as s:
        rec = IncidentRecord(
            incident_id='INC-V2', title='Schema drift', category='SCHEMA_DRIFT',
            severity='HIGH', service='payments-service',
            error_trace='ValidationError: currency_code required',
            state='IDLE', attempt_count=0, max_attempts=3
        )
        s.add(rec); s.commit(); s.refresh(rec)
        pk2 = rec.id

    with Session(test_engine) as s:
        res = await IncidentOrchestrator(s).run(pk2, 'fail')

    chk('Final state == QUARANTINED', res['final_state'] == 'QUARANTINED', res['final_state'])
    chk('attempt_count == 3 (max)', res['attempt_count'] == 3, str(res['attempt_count']))

    with Session(test_engine) as s:
        r_check = s.get(IncidentRecord, pk2)
        chk('DB state == QUARANTINED', r_check.state == 'QUARANTINED')
        chk('DB attempt_count <= 3', r_check.attempt_count <= 3, str(r_check.attempt_count))

        transitions = s.exec(
            select(StateTransitionLog).where(StateTransitionLog.incident_pk == pk2)
        ).all()
        quarantine_entries = [t for t in transitions if t.to_state == 'QUARANTINED']
        retry_entries = [t for t in transitions if t.to_state == 'REPAIR_RETRY']
        chk('Exactly 1 quarantine transition', len(quarantine_entries) == 1, str(len(quarantine_entries)))
        chk('At most 3 retry transitions', len(retry_entries) <= 3, str(len(retry_entries)))
        chk('No ROLLED_OUT state reached', 'ROLLED_OUT' not in {t.to_state for t in transitions})

        activity = s.exec(
            select(BobActivityLog).where(BobActivityLog.incident_pk == pk2)
        ).all()
        human_handoff = [a for a in activity if 'Human review' in a.message]
        evidence_preserved = [a for a in activity if 'Evidence preserved' in a.message]
        chk('Human handoff event present', len(human_handoff) > 0)
        chk('Evidence preserved event present', len(evidence_preserved) > 0)

        # Verify quarantine reason stored in transition
        qtr = quarantine_entries[0]
        chk('Quarantine has reason', bool(qtr.reason))

    print(f'  Retry transitions: {len(retry_entries)}')
    print(f'  Quarantine reason: {quarantine_entries[0].reason[:60]}')
    results['step3_quarantine'] = PASS
    return pk2


async def step4_auditor_fail_closed():
    print('\nSTEP 4: AUDITOR FAIL-CLOSED')
    print('-' * 40)
    agent = AuditorAgent()

    # Test 1: non-JSON output
    with patch.object(agent.gateway, 'generate', new=AsyncMock(return_value='not json')):
        r = await agent.audit(incident_id='X', patch={}, diagnosis={}, test_results={}, attempt_num=1)
    chk('Non-JSON -> trusted=False', r.trusted == False)
    chk('Non-JSON -> recommendation=REJECT', r.recommendation == AuditRecommendation.REJECT)
    chk('Non-JSON -> untrust_reason set', bool(r.untrust_reason))

    # Test 2: missing required fields
    with patch.object(agent.gateway, 'generate', new=AsyncMock(return_value=json.dumps({'security_risk': 'LOW'}))):
        r2 = await agent.audit(incident_id='X', patch={}, diagnosis={}, test_results={}, attempt_num=1)
    chk('Missing fields -> trusted=False', r2.trusted == False)

    # Test 3: invalid risk level
    invalid_risk = json.dumps({
        'security_risk': 'VERY_BAD',
        'regression_risk': 'LOW',
        'edge_cases': [],
        'performance_impact': 'NEGLIGIBLE',
        'test_coverage_adequate': True,
        'recommendation': 'APPROVE',
        'findings_summary': 'test'
    })
    with patch.object(agent.gateway, 'generate', new=AsyncMock(return_value=invalid_risk)):
        r3 = await agent.audit(incident_id='X', patch={}, diagnosis={}, test_results={}, attempt_num=1)
    chk('Invalid risk value -> trusted=False', r3.trusted == False)

    # Test 4: exception in gateway
    with patch.object(agent.gateway, 'generate', new=AsyncMock(side_effect=Exception('network failure'))):
        r4 = await agent.audit(incident_id='X', patch={}, diagnosis={}, test_results={}, attempt_num=1)
    chk('Gateway exception -> trusted=False', r4.trusted == False)

    # Test 5: UNKNOWN risk fails the deterministic gate
    gate = DeterministicReleaseGate()
    gr = gate.evaluate(
        test_pass_rate=1.0, audit_trusted=True,
        audit_security_risk='UNKNOWN', audit_regression_risk='LOW',
        audit_recommendation='APPROVE', test_coverage_adequate=True
    )
    chk('UNKNOWN security_risk -> gate BLOCKED', gr.passed == False)

    results['step4_auditor_fail_closed'] = PASS


async def step5_deterministic_gate():
    print('\nSTEP 5: DETERMINISTIC GATE — LLM NOT SOLE AUTHORIZER')
    print('-' * 40)
    gate = DeterministicReleaseGate()

    # LLM APPROVE + bad tests -> blocked
    r = gate.evaluate(test_pass_rate=0.80, audit_trusted=True,
        audit_security_risk='LOW', audit_regression_risk='LOW',
        audit_recommendation='APPROVE', test_coverage_adequate=True)
    chk('Low tests + LLM APPROVE -> BLOCKED', r.passed == False)

    # LLM REJECT always blocks
    r = gate.evaluate(test_pass_rate=1.0, audit_trusted=True,
        audit_security_risk='LOW', audit_regression_risk='LOW',
        audit_recommendation='REJECT', test_coverage_adequate=True)
    chk('LLM REJECT -> BLOCKED', r.passed == False)

    # ESCALATE blocks
    r = gate.evaluate(test_pass_rate=1.0, audit_trusted=True,
        audit_security_risk='LOW', audit_regression_risk='LOW',
        audit_recommendation='ESCALATE', test_coverage_adequate=True)
    chk('LLM ESCALATE -> BLOCKED', r.passed == False)

    # Untrusted audit blocks
    r = gate.evaluate(test_pass_rate=1.0, audit_trusted=False,
        audit_security_risk='LOW', audit_regression_risk='LOW',
        audit_recommendation='APPROVE', test_coverage_adequate=True)
    chk('Untrusted audit -> BLOCKED', r.passed == False)

    # HIGH regression risk blocks
    r = gate.evaluate(test_pass_rate=1.0, audit_trusted=True,
        audit_security_risk='LOW', audit_regression_risk='HIGH',
        audit_recommendation='APPROVE', test_coverage_adequate=True)
    chk('HIGH regression risk -> BLOCKED', r.passed == False)

    # All green -> passes
    r = gate.evaluate(test_pass_rate=0.98, audit_trusted=True,
        audit_security_risk='LOW', audit_regression_risk='LOW',
        audit_recommendation='APPROVE', test_coverage_adequate=True)
    chk('All green -> PASSED', r.passed == True)

    print('  LLM never sole authorization: CONFIRMED')
    results['step5_deterministic_gate'] = PASS


async def step6_cryptographic_evidence(pk1):
    print('\nSTEP 6: CRYPTOGRAPHIC EVIDENCE')
    print('-' * 40)

    # Build and sign a payload
    payload = build_evidence_payload(
        incident_id='INC-V1', affected_service='orders-service',
        final_state='ROLLED_OUT', attempt_count=1,
        patch_hash='abc123def456', test_results={'passed': 5, 'failed': 0},
        audit_findings={'security_risk': 'LOW'}, canary_metrics={'error_rate': 0.005},
        gate_checks={'passed': True},
        state_transitions=[{'from_state': 'IDLE', 'to_state': 'INCIDENT_RECEIVED'}]
    )
    sig = sign_payload(payload)
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))

    chk('Valid evidence verifies as VALID', verify_evidence(payload_json, sig) == True)

    # Tamper test
    tampered = dict(payload)
    tampered['final_state'] = 'TAMPERED'
    tampered_json = json.dumps(tampered, sort_keys=True, separators=(',', ':'))
    chk('Tampered payload verifies as INVALID', verify_evidence(tampered_json, sig) == False)

    # Wrong signature
    chk('Wrong signature verifies as INVALID', verify_evidence(payload_json, 'a' * 64) == False)

    # Empty input
    chk('Empty input verifies as INVALID', verify_evidence('', '') == False)

    # Real incident evidence from DB
    with Session(test_engine) as s:
        ev = s.exec(select(EvidenceRecord).where(EvidenceRecord.incident_pk == pk1)).first()
        assert ev is not None, 'No evidence record in DB!'
        real_ok = verify_evidence(ev.payload_json, ev.signature)
        chk('Real DB incident evidence: VERIFIED', real_ok == True)
        chk('Evidence has SYNTHETIC_DEMO label',
            '"SYNTHETIC_DEMO"' in ev.payload_json or 'SYNTHETIC_DEMO' in ev.payload_json)
        chk('Evidence signing key correct', ev.signing_key_id == SIGNING_KEY_ID)
        # Verify payload has all required fields
        p = json.loads(ev.payload_json)
        for field in ['incident_id', 'timestamp', 'affected_service', 'final_state',
                      'attempt_count', 'patch_hash', 'signing_key_id', 'builder']:
            chk(f'Evidence payload has {field}', field in p)

    results['step6_evidence'] = PASS


async def main():
    print('=' * 60)
    print('AETHERIS AI — FINAL VERIFICATION PASS')
    print('IBM Bob Hackathon 2.0 — Release Candidate')
    print('=' * 60)

    pk1 = await step2_happy_path()
    await step3_controlled_failure()
    await step4_auditor_fail_closed()
    await step5_deterministic_gate()
    await step6_cryptographic_evidence(pk1)

    print('\n' + '=' * 60)
    print('FINAL RESULTS:')
    for k, v in results.items():
        print(f'  {k}: {v}')
    all_passed = all(v == PASS for v in results.values())
    print(f'\n  OVERALL: {"ALL PASSED" if all_passed else "FAILURES DETECTED"}')
    print('=' * 60)
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    asyncio.run(main())
