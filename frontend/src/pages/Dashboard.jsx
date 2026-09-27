import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { RefreshCw, Play, AlertTriangle, ChevronLeft, ShieldAlert, CheckCircle2, Terminal } from 'lucide-react'
import {
  getScenarios, getDataIncidents, createIncident, createCustomIncident,
  runWorkflow, getIncident, getActivity, getPatches,
  getTransitions, getEvidence, verifyEvidence, resetIncident,
} from '../api'
import { StatePill, SeverityBadge, MetricCard } from '../components/StatusComponents'
import BobActivityFeed from '../components/BobActivityFeed'
import StateMachineVisualizer from '../components/StateMachineVisualizer'
import { PatchView, TestResultsView, AuditView, GateView, CanaryView, EvidenceView } from '../components/WorkflowPanels'
import { ThemeToggle } from '../components/ThemeProvider'
import AetherisLogo from '../components/Logo'

// ── Scene picker ──────────────────────────────────────────────────

function ScenarioPicker({ scenarios, dataIncidents, onSelect }) {
  return (
    <div className="max-w-3xl mx-auto py-16 px-6">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 bg-indigo-950/60 border border-indigo-800/40 rounded-full px-4 py-1.5 mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse-dot" />
          <span className="text-xs text-indigo-300 font-medium">Select Demo Scenario</span>
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">Choose an Incident</h1>
        <p className="text-gray-500 text-sm">Bob will investigate, repair, validate, and either roll out or quarantine.</p>
      </div>

      <div className="space-y-4">
        {scenarios.map(sc => {
          const incident = dataIncidents.find(i => i.incident_id === sc.incident_id)
          return (
            <div key={sc.scenario_id} className="card p-6 hover:border-indigo-700/50 transition-colors cursor-pointer"
              onClick={() => onSelect(sc, incident)}>
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-white">{sc.name}</h3>
                <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
                  sc.expected_outcome === 'ROLLED_OUT'
                    ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800/30'
                    : 'bg-red-900/30 text-red-400 border-red-800/30'
                }`}>
                  {sc.expected_outcome}
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-3">{sc.description}</p>
              <div className="flex items-center gap-4 text-xs text-gray-600 font-mono">
                <span>fault: {sc.fault_type}</span>
                <span>service: {sc.target_service}</span>
                <span>attempts: {sc.expected_attempts}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Custom incident input (real-time, free-text) ─────────────────

function CustomIncidentForm({ onSubmit, submitting, error }) {
  const [description, setDescription] = useState('')
  const [stackTrace, setStackTrace] = useState('')

  return (
    <div className="max-w-3xl mx-auto px-6 pb-16">
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-3">
          <Terminal size={16} className="text-indigo-400" />
          <h3 className="font-semibold text-white text-sm">Custom Incident — Real-Time Input</h3>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          Type a real error description or paste a stack trace. It runs through the exact same
          Normalizer → Diagnosis → Patch → Audit → Gate → Canary pipeline as the demo scenarios above.
        </p>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="e.g. Users are getting intermittent 500 errors on checkout when the payment webhook is slow to respond..."
          className="w-full bg-[#0a0d14] border border-[#1f2937] rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600 min-h-[90px] resize-y"
          maxLength={2000}
        />
        <textarea
          value={stackTrace}
          onChange={e => setStackTrace(e.target.value)}
          placeholder="Optional: paste a stack trace / log snippet"
          className="w-full mt-2 bg-[#0a0d14] border border-[#1f2937] rounded-lg p-3 text-xs font-mono text-gray-400 placeholder-gray-700 focus:outline-none focus:border-indigo-600 min-h-[60px] resize-y"
          maxLength={4000}
        />
        {error && (
          <div className="mt-3 text-sm text-amber-400 bg-amber-950/20 border border-amber-800/40 rounded-lg p-3">
            {error}
          </div>
        )}
        <button
          onClick={() => onSubmit(description, stackTrace)}
          disabled={submitting || !description.trim()}
          className="btn-primary mt-3 text-sm py-2 px-5 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Play size={14} />
          {submitting ? 'Submitting...' : 'Run Custom Incident'}
        </button>
      </div>
    </div>
  )
}

// ── Outcome banner ────────────────────────────────────────────────

function OutcomeBanner({ state, attemptCount, maxAttempts }) {
  if (state === 'ROLLED_OUT') {
    return (
      <div className="card border-emerald-800/60 bg-emerald-950/20 p-5 flex items-center gap-4">
        <CheckCircle2 size={28} className="text-emerald-400 flex-shrink-0" />
        <div>
          <div className="font-bold text-emerald-400 text-lg">Incident Resolved — Rolled Out</div>
          <div className="text-sm text-emerald-600">Patch deployed safely after {attemptCount} attempt(s). Evidence signed and verified.</div>
        </div>
      </div>
    )
  }
  if (state === 'QUARANTINED') {
    return (
      <div className="card border-red-800/60 bg-red-950/20 p-5 flex items-center gap-4">
        <ShieldAlert size={28} className="text-red-400 flex-shrink-0" />
        <div>
          <div className="font-bold text-red-400 text-lg">Quarantined — Human Review Required</div>
          <div className="text-sm text-red-600">
            Automation stopped after {maxAttempts} failed attempts. Repair unsafe — manual intervention needed. Evidence preserved.
          </div>
        </div>
      </div>
    )
  }
  return null
}

// ── Main Dashboard ────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const { incidentPk } = useParams()

  const [scenarios, setScenarios]         = useState([])
  const [dataIncidents, setDataIncidents] = useState([])
  const [incident, setIncident]           = useState(null)
  const [activity, setActivity]           = useState([])
  const [patches, setPatches]             = useState([])
  const [transitions, setTransitions]     = useState([])
  const [evidence, setEvidence]           = useState(null)
  const [loading, setLoading]             = useState(false)
  const [verifying, setVerifying]         = useState(false)
  const [error, setError]                 = useState(null)
  const [scenarioPk, setScenarioPk]       = useState(incidentPk || null)
  const [customError, setCustomError]     = useState(null)
  const [customSubmitting, setCustomSubmitting] = useState(false)

  const isRunning = incident && !['ROLLED_OUT','QUARANTINED','IDLE'].includes(incident.state)
  const isComplete = incident && ['ROLLED_OUT','QUARANTINED'].includes(incident.state)

  // Load scenarios + data incidents on mount
  useEffect(() => {
    getScenarios().then(r => setScenarios(r.data)).catch(() => {})
    getDataIncidents().then(r => setDataIncidents(r.data)).catch(() => {})
  }, [])

  // Poll incident state when running
  const pollIncident = useCallback(async () => {
    if (!scenarioPk) return
    try {
      const [incR, actR, patR, trR] = await Promise.all([
        getIncident(scenarioPk),
        getActivity(scenarioPk),
        getPatches(scenarioPk),
        getTransitions(scenarioPk),
      ])
      setIncident(incR.data)
      setActivity(actR.data)
      setPatches(patR.data)
      setTransitions(trR.data)

      // Load evidence when complete
      if (['ROLLED_OUT','QUARANTINED'].includes(incR.data.state)) {
        try {
          const evR = await getEvidence(scenarioPk)
          setEvidence(evR.data)
        } catch {}
      }
    } catch (e) {
      console.error('Poll error', e)
    }
  }, [scenarioPk])

  useEffect(() => {
    if (!scenarioPk) return
    pollIncident()
    // Poll every 1s while running, 5s when complete
    const interval = setInterval(pollIncident, isComplete ? 5000 : 1000)
    return () => clearInterval(interval)
  }, [scenarioPk, isComplete, pollIncident])

  // Handle scenario selection
  const handleSelectScenario = async (scenario, incidentData) => {
    setError(null)
    setLoading(true)
    try {
      const mode = scenario.expected_outcome === 'ROLLED_OUT' ? 'pass' : 'fail'
      const payload = {
        incident_id:  incidentData.incident_id,
        title:        incidentData.title,
        category:     incidentData.category,
        severity:     incidentData.severity,
        service:      incidentData.service,
        error_trace:  incidentData.error_trace,
        scenario_id:  scenario.scenario_id,
        auto_run:     true,
        scenario_mode: mode,
      }
      // Create + run in ONE request (avoids Vercel SQLite /tmp isolation)
      const created = await createIncident(payload)
      const pk = created.data.id
      setScenarioPk(pk)
      setIncident(created.data)
      navigate(`/dashboard/${pk}`)
      // Final poll for activity/patches/evidence
      setTimeout(() => pollIncident(), 300)
    } catch (e) {
      setError('Failed to start scenario: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  // Handle custom free-text incident (real-time input, same downstream pipeline)
  const handleCustomIncident = async (description, stackTrace) => {
    setCustomError(null)
    setCustomSubmitting(true)
    try {
      const created = await createCustomIncident({
        description,
        stack_trace: stackTrace,
        auto_run: true,
        scenario_mode: 'custom',
      })
      const pk = created.data.id
      setScenarioPk(pk)
      setIncident(created.data)
      navigate(`/dashboard/${pk}`)
      setTimeout(() => pollIncident(), 300)
    } catch (e) {
      const detail = e.response?.data?.detail
      if (detail?.error === 'NEEDS_CLARIFICATION') {
        setCustomError(`Needs clarification: ${detail.reason}${detail.suggestion ? ' — ' + detail.suggestion : ''}`)
      } else {
        setCustomError('Failed to submit: ' + (detail || e.message))
      }
    } finally {
      setCustomSubmitting(false)
    }
  }

  // Reset for re-run
  const handleReset = async () => {
    if (!scenarioPk) return
    await resetIncident(scenarioPk)
    setScenarioPk(null)
    setIncident(null)
    setActivity([])
    setPatches([])
    setTransitions([])
    setEvidence(null)
    setError(null)
    navigate('/dashboard')
  }

  // Back to scenario picker without resetting the incident on the backend —
  // just returns to the selection view so the user can run another test.
  const handleBackToScenarios = () => {
    setScenarioPk(null)
    setIncident(null)
    setActivity([])
    setPatches([])
    setTransitions([])
    setEvidence(null)
    setError(null)
    navigate('/dashboard')
  }

  // Evidence verification
  const handleVerify = async () => {
    if (!scenarioPk) return
    setVerifying(true)
    try {
      const r = await verifyEvidence(scenarioPk)
      setEvidence(prev => ({ ...prev, ...r.data }))
    } catch (e) {
      setError('Verification failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setVerifying(false)
    }
  }

  // ── Render: Scenario picker ──────────────────────────────────────
  if (!scenarioPk && !loading) {
    return (
      <div className="min-h-screen bg-[#0a0d14]">
        <nav className="fixed top-0 w-full z-50 border-b border-[#1f2937] bg-[#0a0d14]/90 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <button onClick={() => navigate('/')} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
              <ChevronLeft size={16} />
              <div className="flex items-center gap-2">
                <AetherisLogo size={28} />
                <span className="font-bold text-white">AETHERIS AI</span>
              </div>
            </button>
            <ThemeToggle />
          </div>
        </nav>
        <div className="pt-14">
          {error && (
            <div className="max-w-3xl mx-auto mt-4 px-6">
              <div className="card border-red-800/50 bg-red-950/20 p-3 text-sm text-red-400">{error}</div>
            </div>
          )}
          <ScenarioPicker
            scenarios={scenarios}
            dataIncidents={dataIncidents}
            onSelect={handleSelectScenario}
          />
          <CustomIncidentForm
            onSubmit={handleCustomIncident}
            submitting={customSubmitting}
            error={customError}
          />
        </div>
      </div>
    )
  }

  // ── Render: Active dashboard ─────────────────────────────────────
  const lastPatch = patches[patches.length - 1]
  const allPatchTests = lastPatch?.tests
  const allPatchAudit = lastPatch?.audit
  const allPatchGate  = lastPatch?.gate
  const allPatchCanary = lastPatch?.canary

  return (
    <div className="min-h-screen bg-[#0a0d14]">

      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 border-b border-[#1f2937] bg-[#0a0d14]/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={handleBackToScenarios} className="text-gray-600 hover:text-gray-400 transition-colors" title="Back to scenarios">
              <ChevronLeft size={16} />
            </button>
            <div className="flex items-center gap-2">
              <AetherisLogo size={28} />
              <span className="font-bold text-white">AETHERIS AI</span>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {incident && <StatePill state={incident.state} />}
            {loading && (
              <div className="flex items-center gap-2 text-xs text-indigo-400 font-mono">
                <RefreshCw size={12} className="animate-spin" />
                Starting...
              </div>
            )}
            <ThemeToggle />
            {scenarioPk && (
              <>
                <button onClick={handleBackToScenarios} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                  <ChevronLeft size={12} />
                  <span className="hidden sm:inline">Back to Scenarios</span>
                </button>
                <button onClick={handleReset} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                  <RefreshCw size={12} />
                  Reset Demo
                </button>
              </>
            )}
          </div>
        </div>
      </nav>

      <div className="pt-14 max-w-7xl mx-auto px-6 py-6">
        {error && (
          <div className="card border-red-800/50 bg-red-950/20 p-3 text-sm text-red-400 mb-4">{error}</div>
        )}

        {/* Outcome Banner */}
        {isComplete && incident && (
          <div className="mb-6">
            <OutcomeBanner
              state={incident.state}
              attemptCount={incident.attempt_count}
              maxAttempts={incident.max_attempts}
            />
          </div>
        )}

        {/* Incident Header */}
        {incident && (
          <div className="card p-5 mb-6">
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <AlertTriangle size={16} className="text-red-400" />
                  <span className="font-mono text-sm text-gray-400">{incident.incident_id}</span>
                  <SeverityBadge severity={incident.severity} />
                </div>
                <h2 className="text-lg font-bold text-white">{incident.title}</h2>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500 font-mono">
                  <span>service: {incident.service}</span>
                  <span>category: {incident.category}</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <div className="text-xs text-gray-600 mb-1">Attempts</div>
                  <div className={`text-2xl font-bold font-mono ${
                    incident.attempt_count >= incident.max_attempts ? 'text-red-400' : 'text-amber-400'
                  }`}>
                    {incident.attempt_count}/{incident.max_attempts}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Metrics row */}
        {incident && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <MetricCard
              label="Final State"
              value={incident.state}
              color={
                incident.state === 'ROLLED_OUT' ? 'text-emerald-400' :
                incident.state === 'QUARANTINED' ? 'text-red-400' :
                'text-indigo-400'
              }
            />
            <MetricCard
              label="Test Pass Rate"
              value={lastPatch?.test_pass_rate != null ? (lastPatch.test_pass_rate * 100).toFixed(0) + '%' : '—'}
              color={lastPatch?.test_pass_rate >= 0.95 ? 'text-emerald-400' : 'text-red-400'}
            />
            <MetricCard
              label="Security Risk"
              value={lastPatch?.audit?.security_risk || '—'}
              color={
                lastPatch?.audit?.security_risk === 'LOW' ? 'text-emerald-400' :
                lastPatch?.audit?.security_risk === 'MEDIUM' ? 'text-yellow-400' :
                'text-red-400'
              }
            />
            <MetricCard
              label="Gate"
              value={lastPatch?.gate_passed == null ? '—' : lastPatch.gate_passed ? 'PASSED' : 'BLOCKED'}
              color={lastPatch?.gate_passed ? 'text-emerald-400' : 'text-red-400'}
            />
          </div>
        )}

        {/* Main content grid */}
        <div className="grid lg:grid-cols-3 gap-6">

          {/* Left column: state machine + activity */}
          <div className="lg:col-span-1 space-y-6">
            <StateMachineVisualizer
              currentState={incident?.state || 'IDLE'}
              transitions={transitions}
            />
            <BobActivityFeed events={activity} />
          </div>

          {/* Right columns: workflow panels */}
          <div className="lg:col-span-2 space-y-6">
            {lastPatch && <PatchView patch={lastPatch} />}
            <div className="grid md:grid-cols-2 gap-6">
              {allPatchTests && <TestResultsView tests={allPatchTests} />}
              {allPatchAudit && <AuditView audit={allPatchAudit} />}
            </div>
            {allPatchGate  && <GateView gate={allPatchGate} />}
            {allPatchCanary && <CanaryView canary={allPatchCanary} />}
            {evidence && (
              <EvidenceView
                evidence={evidence}
                onVerify={handleVerify}
                verifying={verifying}
              />
            )}

            {/* Human handoff panel */}
            {incident?.state === 'QUARANTINED' && (
              <div className="card border-amber-800/40 bg-amber-950/10 p-5">
                <div className="flex items-start gap-3">
                  <ShieldAlert size={20} className="text-amber-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold text-amber-400 mb-1">Human Handoff Required</div>
                    <p className="text-sm text-gray-500 leading-relaxed">
                      Autonomous repair exhausted {incident.max_attempts} attempts without achieving a safe rollout.
                      The incident has been quarantined. Evidence has been preserved and cryptographically signed
                      for manual review. Human engineer intervention is required to investigate and resolve.
                    </p>
                    <div className="mt-3 flex gap-2 text-xs font-mono text-gray-600">
                      <span>· Do not roll out this patch</span>
                      <span>· Review evidence chain</span>
                      <span>· Escalate if needed</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Patch history */}
        {patches.length > 1 && (
          <div className="mt-6">
            <div className="card p-4">
              <div className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-3">Patch Attempt History</div>
              <div className="space-y-2">
                {patches.map(p => (
                  <div key={p.id} className="flex items-center gap-4 py-2 border-b border-[#1f2937] last:border-0 text-xs font-mono">
                    <span className="text-gray-600">Attempt {p.attempt_num}</span>
                    <span className="text-gray-500">{p.patch_hash?.slice(0, 12)}...</span>
                    <span className={p.test_pass_rate >= 0.95 ? 'text-emerald-500' : 'text-red-500'}>
                      tests {p.test_pass_rate != null ? (p.test_pass_rate * 100).toFixed(0) + '%' : '—'}
                    </span>
                    <span className={p.audit_trusted ? 'text-emerald-500' : 'text-red-500'}>
                      audit {p.audit_trusted ? 'trusted' : 'untrusted'}
                    </span>
                    <span className={p.gate_passed ? 'text-emerald-500' : 'text-red-500'}>
                      gate {p.gate_passed == null ? '—' : p.gate_passed ? 'pass' : 'fail'}
                    </span>
                    <span className={p.canary_passed ? 'text-emerald-500' : p.canary_passed === false ? 'text-red-500' : 'text-gray-600'}>
                      canary {p.canary_passed == null ? '—' : p.canary_passed ? 'pass' : 'fail'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 text-center text-xs text-gray-700 font-mono">
          Built with IBM Bob IDE · AETHERIS AI · Hackathon 2.0 · All data synthetic
        </div>
      </div>
    </div>
  )
}