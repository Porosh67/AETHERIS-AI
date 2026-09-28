# AETHERIS AI

**Autonomous Incident Resolution — IBM Bob Hackathon 2.0**

> Production broke. Bob investigates. Aetheris repairs. Safety gates decide. Every action is verifiable.

---

## 1. The Problem

When a production incident occurs, developers must manually:

1. Investigate the failure
2. Identify root cause
3. Write an emergency patch
4. Test the patch
5. Review security and regression risk
6. Deploy a canary
7. Decide whether to roll out
8. Rollback or continue if unsafe
9. Document what happened

This creates high developer time, operational pressure, errors, rework, and delayed recovery.

## 2. Developer Workflow Being Improved

**Application Maintenance + Debugging + Hot-Patch / Release Validation**

AETHERIS AI converts an incident into a bounded, evidence-producing repair workflow. It investigates the incident, proposes a repair, tests it, audits it, validates it through deterministic release gates, runs a simulated canary, and either safely rolls out the repair or stops and quarantines it for human review.

The differentiator is **not** simply "AI writes patches."

The differentiator is: **Bounded autonomous incident resolution with evidence-backed stop conditions.**

The system explicitly knows when **NOT** to proceed.

## 3. Solution

AETHERIS AI is a full-stack developer tool that:

- **Receives** a production incident with error trace + telemetry context
- **Diagnoses** root cause via the Sentinel/Diagnosis agent (LLM-backed, mock-fallback)
- **Generates** a constrained patch diff (whitelisted patch types only)
- **Tests** the patch (deterministic test suite per incident category)
- **Audits** it for security, regression, and edge case risk (fail-closed on invalid output)
- **Gates** rollout via a deterministic code-only release gate (LLM never authorizes)
- **Canaries** the patch via a simulated health validation
- **Rolls out** or **Quarantines** with a hard 3-attempt cap
- **Signs** every incident resolution with HMAC-SHA256 cryptographic evidence
- **Verifies** evidence on demand (real verification — not decorative)

## 4. Why IBM Bob Is Central

IBM Bob IDE is the **primary engineering orchestrator** for this project. Bob performed:

- Repository architecture and project initialization
- State machine design and implementation
- All agent implementations (ChaosAgent, DiagnosisAgent, PatchAgent, AuditorAgent)
- Incident Orchestrator construction
- Deterministic Release Gate
- Canary Validator
- Evidence signing and verification system
- FastAPI backend with full REST API
- SQLite persistence layer
- React + Vite frontend (landing page + full dashboard)
- 100-test suite (unit + integration)
- Security review
- Both demo scenario verification (ROLLED_OUT + QUARANTINED)
- This README

watsonx.ai is an **inference subsystem only** — accessible behind the `InferenceGateway`. Bob is not just a code assistant; Bob is the engineering lead.

## 5. Architecture

```
Developer
   │
   ▼
Landing Page → Launch Demo
   │
   ▼
Dashboard (React + Vite)
   │  REST API (proxied)
   ▼
FastAPI Backend (Python 3.14)
   │
   ├── Incident Orchestrator ──────────────────────────┐
   │    │                                              │
   │    ├── ChaosAgent (bounded fault params)         │
   │    ├── DiagnosisAgent (Sentinel)                 │
   │    ├── PatchAgent (constrained diff)             │
   │    ├── AuditorAgent (fail-closed review)         │
   │    ├── DeterministicReleaseGate (code-only)      │
   │    └── CanaryValidator (simulated)               │
   │                                                  │
   ├── InferenceGateway ─── watsonx.ai / Granite      │
   │                         (mock fallback if absent) │
   │                                                  │
   ├── Evidence Signer (HMAC-SHA256)                  │
   │                                                  │
   └── SQLite DB (state + evidence + audit trail) ◄──┘
```

## 6. Data Flow

```
Incident Created
      │
      ▼ IDLE → INCIDENT_RECEIVED
      │
      ▼ DIAGNOSING
      │   DiagnosisAgent → LLM → validated JSON → root cause
      │
      ▼ PATCH_GENERATED
      │   PatchAgent → LLM → validated diff + hash
      │
      ▼ PATCH_TESTING
      │   TestRunner → deterministic test suite
      │   pass_rate < 95% → REPAIR_RETRY → retry or QUARANTINE
      │
      ▼ AUDITING
      │   AuditorAgent → LLM → validated findings
      │   malformed output → AUDIT_UNTRUSTED → REPAIR_RETRY → retry or QUARANTINE
      │
      ▼ CANARY_PENDING → CANARY_RUNNING
      │   DeterministicReleaseGate → code-only authorization
      │   CanaryValidator → simulated health checks
      │   fail → REPAIR_RETRY → retry or QUARANTINE
      │
      ▼ ROLLED_OUT (success) or QUARANTINED (failure)
      │
      ▼ EvidenceRecord (HMAC-SHA256 signed)
```

## 7. Agent Workflow

| Agent | Role | LLM? | Validated? |
|-------|------|-------|-----------|
| **ChaosAgent** | Bounded fault params — whitelist only | No | Input-validated |
| **DiagnosisAgent** | Root cause + repair strategy | Yes (mock fallback) | Output-validated |
| **PatchAgent** | Constrained diff generation | Yes (mock fallback) | Output-validated |
| **AuditorAgent** | Security/regression/edge case review | Yes (mock fallback) | Output-validated + fail-closed |

All LLM calls go through `InferenceGateway` with 15s timeout, 1 retry, and structured output parsing.

## 8. State Machine

```
IDLE → INCIDENT_RECEIVED → DIAGNOSING → PATCH_GENERATED → PATCH_TESTING
     → AUDITING → CANARY_PENDING → CANARY_RUNNING → ROLLED_OUT

Failure paths:
PATCH_TESTING  → REPAIR_RETRY → DIAGNOSING (retry) or QUARANTINED (max)
AUDITING       → AUDIT_UNTRUSTED → REPAIR_RETRY → DIAGNOSING or QUARANTINED
CANARY_RUNNING → REPAIR_RETRY → DIAGNOSING (retry) or QUARANTINED (max)
```

All transitions are validated by `validate_transition()` — invalid transitions raise `InvalidTransitionError` before any DB write.

## 9. Safety Boundaries

- **No unrestricted code execution** — all patch types are whitelisted (`APPROVED_PATCH_TYPES`)
- **No unrestricted chaos** — all fault categories are whitelisted (`APPROVED_INCIDENT_CATEGORIES`)
- **Fail-closed audit** — malformed LLM output → `AUDIT_UNTRUSTED` → no rollout
- **Deterministic gate** — LLM is NEVER the sole authorization for rollout
- **Hard attempt cap** — maximum 3 autonomous attempts, persisted in SQLite
- **Evidence** — every incident signed with HMAC-SHA256; verification is real code

## 10. Deterministic Release Gate

Located at [`orchestration/release_gate.py`](orchestration/release_gate.py).

The gate evaluates (code only, no LLM):

| Check | Threshold |
|-------|-----------|
| `test_pass_rate` | ≥ 95% |
| `audit_trusted` | Must be True |
| `security_risk` | ≤ MEDIUM |
| `regression_risk` | ≤ LOW |
| `audit_recommendation` | Must be APPROVE |
| `test_coverage_adequate` | Must be True |

`UNKNOWN` risk is treated as worst-case (order value: 99) — never as "no risk."

## 11. Self-Correction (3-Attempt Loop)

```python
while True:
    attempt = record.attempt_count + 1
    # Diagnose → Patch → Test → Audit → Gate → Canary
    # On any failure:
    record.attempt_count += 1  # persisted in DB
    if is_retry_allowed(record.attempt_count, max_attempts=3):
        → REPAIR_RETRY → DIAGNOSING  # try again
    else:
        → QUARANTINED  # human handoff
```

A failed inference call counts as a failed attempt. A validation failure counts. A canary failure counts.

## 12. Canary Behavior

The canary validator is explicitly labeled `[SIMULATED]` in the UI.

It simulates health polling, error rate measurement, and latency measurement. Results are evaluated deterministically against thresholds:

- Error rate threshold: 2%
- p99 latency threshold: 500ms
- Minimum passing polls: 3/3

**No real cloud deployment is claimed.**

## 13. Quarantine Behavior

When attempt 3 fails:

```
REPAIR_RETRY → QUARANTINED
```

- Patch is NOT rolled out
- Evidence is preserved and signed
- Human handoff panel displayed in UI
- Evidence available for manual review
- `attempt_count == max_attempts` always at quarantine

## 14. Cryptographic Evidence

AETHERIS uses **dual-layer HMAC-SHA256 evidence signing** (not DSSE — the two layers are distinct HMAC applications, chosen for simplicity and stdlib-only implementation):

- **Input layer** (`audit/evidence_hmac.py`) — tags telemetry, test results, and patch diffs at capture time; verified before the Auditor runs. A failed input HMAC → `AUDIT_UNTRUSTED` → no rollout.
- **Final layer** (`audit/evidence_signer.py`) — signs the complete resolution record after the incident reaches ROLLED_OUT or QUARANTINED, for tamper-evident long-term storage.

Every incident resolution (ROLLED_OUT or QUARANTINED) generates a signed evidence record:

```python
# Signing (audit/evidence_signer.py)
payload = build_evidence_payload(...)  # canonical dict
signature = hmac.new(key_bytes, json.dumps(payload, sort_keys=True), sha256).hexdigest()

# Verification
ok = hmac.compare_digest(sign_payload(stored_payload), stored_signature)
# Returns True ONLY if signatures match (timing-safe)
```

The UI calls `POST /api/incidents/{pk}/evidence/verify` — signature is re-derived server-side. The UI shows `VERIFIED` only if `ok == True`.

Evidence payload includes: `incident_id`, `timestamp`, `affected_service`, `final_state`, `attempt_count`, `patch_hash`, `test_results`, `audit_findings`, `gate_checks`, `canary_metrics`, `state_transitions`, `signing_key_id`, `data_classification: SYNTHETIC_DEMO`.

## 15. Synthetic Dataset

All demo data is **synthetic and project-owned**. No real client data, PII, or company-confidential information is used.

| File | Contents |
|------|----------|
| [`data/incidents.json`](data/incidents.json) | 6 synthetic incident records |
| [`data/telemetry.json`](data/telemetry.json) | 5 synthetic metric time series |
| [`data/service_snapshots.json`](data/service_snapshots.json) | 2 synthetic service health snapshots |
| [`data/demo_scenarios.json`](data/demo_scenarios.json) | 2 demo scenario definitions |

Each record is marked `"synthetic": true`.

## 16. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14, FastAPI, SQLModel, SQLite |
| Frontend | React 18, Vite 5, TailwindCSS 3 |
| AI Inference | watsonx.ai / IBM Granite (mock fallback) |
| Evidence | HMAC-SHA256 (Python `hmac` stdlib) |
| Testing | pytest, pytest-asyncio |
| Build | npm, Vite |

## 17. Setup

### Prerequisites
- Python 3.14+
- Node.js 18+ (npm)

### 1. Clone and set up environment

```bash
# Copy environment config
cp .env.example .env

# Generate a signing key
python -c "import secrets; print('EVIDENCE_SIGNING_KEY=' + secrets.token_hex(32))"
# Paste the output into .env
```

### 2. Install backend

```bash
pip install fastapi uvicorn sqlmodel pydantic pydantic-settings httpx python-dotenv pytest pytest-asyncio aiofiles cryptography
```

### 3. Install frontend

```bash
cd frontend
# Windows with Node.js not on PATH:
"C:\Program Files\nodejs\npm.cmd" install
# Or if npm is on PATH:
npm install
```

### 4. Start backend

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start frontend

```bash
cd frontend
npm run dev
# Or: "C:\Program Files\nodejs\npm.cmd" run dev
```

Visit: http://localhost:5173

## 18. Environment Variables

See [`.env.example`](.env.example).

| Variable | Required | Description |
|----------|----------|-------------|
| `EVIDENCE_SIGNING_KEY` | Yes (use strong key in prod) | HMAC-SHA256 signing key |
| `WATSONX_API_KEY` | Optional | watsonx.ai API key (mock used if absent) |
| `WATSONX_PROJECT_ID` | Optional | watsonx.ai project ID |
| `WATSONX_URL` | Optional | watsonx.ai endpoint |
| `WATSONX_MODEL_ID` | Optional | Model ID (default: granite-3-8b-instruct) |
| `ALLOWED_ORIGINS` | Optional | CORS origins |

**Never commit `.env` to version control.**

## 19. Demo Instructions

### Landing Page
Visit http://localhost:5173 — the landing page explains the product and provides a `Launch Demo` button.

### Scenario 1: Safe Repair
1. Click **Launch Demo**
2. Select **"Safe Repair — NULL_ERROR in orders-service"**
3. Watch the Bob execution trace in real time
4. Observe: DIAGNOSING → PATCH_GENERATED → PATCH_TESTING → AUDITING → CANARY_RUNNING → **ROLLED_OUT**
5. Click **VERIFY EVIDENCE** — observe `VERIFIED: VALID`

### Scenario 2: Controlled Failure
1. Click **Reset Demo**
2. Select **"Controlled Failure — SCHEMA_DRIFT exhausts all 3 attempts → QUARANTINED"**
3. Watch 3 repair attempts fail
4. Observe: REPAIR_RETRY (x3) → **QUARANTINED** → Human handoff panel
5. Click **VERIFY EVIDENCE** — quarantine evidence is also signed and verifiable

### Reset for re-judging
Click **Reset Demo** at any time to clear state and run again.

## 20. Tests

```bash
# Run full test suite
python -m pytest tests/ -v

# Run unit tests only
python -m pytest tests/unit/ -v

# Run integration tests only
python -m pytest tests/integration/ -v

# Run end-to-end demo verification
python scripts/demo_verification.py
```

**Current results: 100/100 tests passing.**

Test coverage includes:
- Valid state transitions (16 tests)
- Invalid state transitions (6 tests)
- Terminal states (4 tests)
- Attempt limit enforcement (6 tests)
- Evidence signing (11 tests)
- Evidence verification with tamper detection (3 tests)
- Release gate — all pass/fail combinations (14 tests)
- Risk order validation (4 tests)
- Auditor fail-closed behavior (8 tests)
- Auditor output validation (4 tests)
- Canary pass/fail/simulation labeling (5 tests)
- ChaosAgent boundary enforcement (7 tests)
- API health, taxonomy, CRUD, scenario (15 tests)

## 21. Bob Development Evidence

Bob session evidence screenshots are stored in [`bob_sessions/`](bob_sessions/).

Evidence naming convention:
```
aetheris_task01_architecture_summary.png
aetheris_task02_state_machine_summary.png
aetheris_task03_orchestration_summary.png
aetheris_task04_ai_integration_summary.png
aetheris_task05_audit_security_summary.png
aetheris_task06_frontend_summary.png
aetheris_task07_testing_summary.png
aetheris_task08_final_verification_summary.png
```

Session logs are in [`bob_sessions/SESSION-001.md`](bob_sessions/SESSION-001.md).

## 22. Known Limitations

- **Canary is simulated** — no real cloud deployment. Explicitly labeled in UI.
- **watsonx.ai is optional** — mock inference used when not configured. Mock responses are deterministic and clearly labeled.
- **No rate limiting** on API endpoints (acceptable for hackathon demo; production would require middleware).
- **SQLite is single-writer** — not suitable for concurrent multi-user production (known, intentional choice for simplicity).
- **npm not on PATH** on Windows in some configurations — use full path `C:\Program Files\nodejs\npm.cmd` if needed.
- **Evidence key in default** — `EVIDENCE_SIGNING_KEY` has a dev default. Generate and use a real key in production.
- **No auth system** — intentionally omitted per blueprint. Demo is instantly accessible.

## 23. Future Improvements

- Real watsonx.ai Granite integration tested end-to-end
- Real canary via Docker Compose service health checks
- Webhook/SSE event stream for live dashboard updates (vs polling)
- Multi-attempt diff visualization in UI
- PostgreSQL backend option for production scaling
- GitHub Actions CI with automated test + demo verification
- Signed evidence export (download as JSON + detached signature)
- Rate limiting + request validation middleware
- Additional incident categories and richer telemetry simulation
- Policy-as-code for release gate thresholds

---

*AETHERIS AI — Built with IBM Bob IDE — IBM Bob Hackathon 2.0*
*All demo data is synthetic. No real client/production data used.*
## License
MIT — see [LICENSE](./LICENSE)