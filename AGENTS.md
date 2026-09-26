# AETHERIS AI — Agent & Project Context

## Project
**AETHERIS AI** — Autonomous Incident Resolution with Bounded Hot-Patch Deployment Workflow  
IBM Bob Hackathon 2.0

## IBM Bob's Role
IBM Bob IDE is the **primary engineering agent** for this project. Bob performs:
- Architecture design and enforcement
- Full-stack implementation (backend, frontend, agents, orchestration)
- State machine construction
- AI workflow integration
- Test generation and execution
- Security review
- Evidence trail creation
- Documentation authoring

## Project Structure
```
/frontend        — React + Vite dashboard & landing page
/backend         — FastAPI Python backend, REST API, SQLite state
/agents          — Chaos, Diagnosis, Patch, Auditor agent logic
/orchestration   — Incident orchestrator, state machine, release gate
/audit           — Evidence signing, verification, audit store
/data            — Synthetic incident/telemetry datasets
/services        — Simulated microservices (gateway/orders/payments/inventory)
/tests           — Unit + integration tests (pytest)
/docs            — Architecture diagrams, design docs
/bob_sessions    — Bob session evidence (screenshots, logs)
/scripts         — Setup, seed, reset utilities
```

## Key Architecture Decisions
1. **Backend**: FastAPI + SQLite (via SQLModel). No heavy DB infrastructure.
2. **Frontend**: React + Vite + TailwindCSS. No auth system required.
3. **State Machine**: Explicit Python enum-driven FSM with persistent SQLite state.
4. **AI Gateway**: Thin `InferenceGateway` class wrapping watsonx.ai/Granite — mock-fallback enabled.
5. **Evidence**: HMAC-SHA256 signing of incident records. Verification is real, not decorative.
6. **Safety**: Deterministic release gate is code-only, never LLM-controlled.
7. **Attempt Cap**: Hard 3-attempt max persisted in SQLite — enforced server-side.

## Incident State Machine
```
IDLE -> INCIDENT_RECEIVED -> DIAGNOSING -> PATCH_GENERATED -> PATCH_TESTING
     -> AUDITING -> CANARY_PENDING -> CANARY_RUNNING -> ROLLED_OUT
     
Failure paths:
PATCH_TESTING  -> REPAIR_RETRY -> (attempt < 3) -> DIAGNOSING
AUDITING       -> REPAIR_RETRY
CANARY_RUNNING -> REPAIR_RETRY
REPAIR_RETRY (attempt == 3) -> QUARANTINED
```

## Agent Taxonomy
- **ChaosAgent**: Generates bounded fault parameters from approved incident taxonomy only
- **DiagnosisAgent**: Consumes telemetry + error trace → root cause + repair strategy
- **PatchAgent**: Generates constrained diff/patch against known baseline
- **AuditorAgent**: Returns structured risk findings (security/regression/edge cases)

## Safety Rules (Non-Negotiable)
- LLM output NEVER authorizes rollout — deterministic gate only
- Malformed auditor output → AUDIT_UNTRUSTED → NO ROLLOUT
- 3-attempt cap enforced in DB, not memory
- No unrestricted code execution
- Fail-closed on all safety signals

## Demo Scenarios
1. **SAFE_REPAIR**: Full successful lifecycle → rollout → evidence signed
2. **CONTROLLED_FAILURE**: 3 failed attempts → QUARANTINED → human handoff

## Environment Variables (see .env.example)
- `WATSONX_API_KEY` — watsonx.ai API key (optional; mock used if absent)
- `WATSONX_PROJECT_ID` — watsonx.ai project ID
- `WATSONX_URL` — watsonx.ai endpoint URL
- `EVIDENCE_SIGNING_KEY` — HMAC key for evidence signing
- `ALLOWED_ORIGINS` — CORS origins for frontend

## Synthetic Data
All demo data is synthetic and project-owned. No real client/PII data used.
See `/data/` for incident records, telemetry, service snapshots, demo scenarios.
