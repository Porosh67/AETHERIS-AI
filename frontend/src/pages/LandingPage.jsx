import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Zap, GitBranch, CheckCircle, AlertTriangle, Lock } from 'lucide-react'
import { ThemeToggle } from '../components/ThemeProvider'
import AetherisLogo from '../components/Logo'

const STATES = [
  'INCIDENT_RECEIVED',
  'DIAGNOSING',
  'PATCH_GENERATED',
  'PATCH_TESTING',
  'AUDITING',
  'CANARY_RUNNING',
  'ROLLED_OUT',
]

function WorkflowStep({ icon: Icon, label, description, accent }) {
  return (
    <div className="flex items-start gap-4">
      <div className={`p-2 rounded-lg border ${accent} flex-shrink-0 mt-0.5`}>
        <Icon size={18} />
      </div>
      <div>
        <div className="font-semibold text-gray-100 text-sm">{label}</div>
        <div className="text-xs text-gray-500 mt-0.5">{description}</div>
      </div>
    </div>
  )
}

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-[#0a0d14] text-gray-100 overflow-x-hidden">

      {/* ── Nav ─────────────────────────────────────── */}
      <nav className="fixed top-0 w-full z-50 border-b border-[#1f2937] bg-[#0a0d14]/90 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AetherisLogo size={28} />
            <span className="font-bold text-white tracking-tight">AETHERIS AI</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="hidden sm:inline text-xs text-gray-500 font-mono">IBM Bob Hackathon 2.0</span>
            <ThemeToggle />
            <button
              onClick={() => navigate('/dashboard')}
              className="btn-primary text-sm py-1.5 px-3 sm:px-4"
            >
              Launch Demo
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────── */}
      <section className="pt-32 pb-20 px-6 text-center relative">
        {/* Background grid */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{backgroundImage: 'linear-gradient(#6366f1 1px, transparent 1px), linear-gradient(90deg, #6366f1 1px, transparent 1px)', backgroundSize: '40px 40px'}}
        />

        <div className="relative max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-indigo-950/60 border border-indigo-800/40 rounded-full px-4 py-1.5 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse-dot" />
            <span className="text-xs text-indigo-300 font-medium">IBM Bob Hackathon 2.0 — Live Demo</span>
          </div>

          <h1 className="text-6xl md:text-7xl font-bold tracking-tight mb-4">
            <span className="text-white">AETHERIS</span>
          </h1>
          <p className="text-xl text-indigo-400 font-semibold mb-6 tracking-wide">
            Autonomous Incident Resolution
          </p>

          <div className="max-w-2xl mx-auto space-y-1 text-lg text-gray-400 mb-10 font-light">
            <p><span className="text-gray-300">Production broke.</span></p>
            <p><span className="text-indigo-400 font-semibold">Bob investigates.</span></p>
            <p><span className="text-gray-300">Aetheris repairs.</span></p>
            <p><span className="text-emerald-400 font-semibold">Safety gates decide.</span></p>
            <p className="text-gray-500">Every action is verifiable.</p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate('/dashboard')}
              className="btn-primary text-base py-3 px-8 flex items-center justify-center gap-2"
            >
              <Zap size={18} />
              Launch Demo
            </button>
            <a href="#how-it-works" className="btn-secondary text-base py-3 px-8 flex items-center justify-center gap-2">
              <GitBranch size={18} />
              See How It Works
            </a>
          </div>
        </div>
      </section>

      {/* ── Problem ─────────────────────────────────── */}
      <section className="py-16 px-6 border-t border-[#1f2937]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-mono text-red-400 uppercase tracking-widest">The Problem</span>
            <h2 className="text-3xl font-bold text-white mt-2">
              Production incidents cost developer hours — every time
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { n: '45min', label: 'Average time to identify root cause', color: 'text-red-400' },
              { n: '8 steps', label: 'Manual steps per incident resolution', color: 'text-orange-400' },
              { n: '3×', label: 'Higher error rate under incident pressure', color: 'text-yellow-400' },
            ].map(({ n, label, color }) => (
              <div key={n} className="card p-6 text-center">
                <div className={`text-4xl font-bold font-mono ${color} mb-2`}>{n}</div>
                <div className="text-sm text-gray-400">{label}</div>
              </div>
            ))}
          </div>
          <p className="text-center text-gray-500 text-sm mt-4 italic">
            * Metrics are illustrative of the workflow improvement domain. Demo measurements shown in application.
          </p>
        </div>
      </section>

      {/* ── How It Works ────────────────────────────── */}
      <section id="how-it-works" className="py-16 px-6 border-t border-[#1f2937]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-mono text-indigo-400 uppercase tracking-widest">How It Works</span>
            <h2 className="text-3xl font-bold text-white mt-2">
              Bounded autonomous repair with explicit stop conditions
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Left: workflow steps */}
            <div className="space-y-6">
              <WorkflowStep
                icon={AlertTriangle}
                label="1. Incident Detection"
                description="Incident is received with error trace, telemetry, and affected service context."
                accent="border-red-800/50 text-red-400 bg-red-950/30"
              />
              <WorkflowStep
                icon={Shield}
                label="2. Bob Diagnoses"
                description="Sentinel agent analyzes traces and telemetry. Root cause identified with evidence."
                accent="border-indigo-800/50 text-indigo-400 bg-indigo-950/30"
              />
              <WorkflowStep
                icon={GitBranch}
                label="3. Patch Generated"
                description="Constrained patch diff generated against known baseline. Patch type whitelisted."
                accent="border-purple-800/50 text-purple-400 bg-purple-950/30"
              />
              <WorkflowStep
                icon={CheckCircle}
                label="4. Tests + Audit"
                description="Test suite runs. Auditor reviews security, regression, and edge cases. Fail-closed on invalid output."
                accent="border-emerald-800/50 text-emerald-400 bg-emerald-950/30"
              />
              <WorkflowStep
                icon={Lock}
                label="5. Deterministic Gate → Canary"
                description="Code-only release gate authorizes (or blocks). Simulated canary validates. LLM never has final say."
                accent="border-yellow-800/50 text-yellow-400 bg-yellow-950/30"
              />
            </div>

            {/* Right: state machine visual */}
            <div className="card p-6">
              <div className="text-xs font-mono text-gray-500 mb-4">STATE MACHINE</div>
              <div className="space-y-2">
                {STATES.map((s, i) => (
                  <div key={s} className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      s === 'ROLLED_OUT' ? 'bg-emerald-500' :
                      s === 'INCIDENT_RECEIVED' ? 'bg-red-500' :
                      'bg-indigo-500'
                    }`} />
                    <span className="font-mono text-xs text-gray-400">{s}</span>
                    {i < STATES.length - 1 && (
                      <div className="text-gray-700 text-xs ml-auto">↓</div>
                    )}
                  </div>
                ))}
                <div className="mt-4 pt-4 border-t border-[#1f2937]">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
                    <span className="font-mono text-xs text-amber-400">REPAIR_RETRY (max 3)</span>
                  </div>
                  <div className="flex items-center gap-3 mt-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
                    <span className="font-mono text-xs text-red-400">QUARANTINED → Human Review</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Safety ──────────────────────────────────── */}
      <section className="py-16 px-6 border-t border-[#1f2937] bg-[#0d1117]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-mono text-emerald-400 uppercase tracking-widest">Safety Architecture</span>
            <h2 className="text-3xl font-bold text-white mt-2">
              The system knows when to <span className="text-red-400">stop</span>
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                title: 'Fail-Closed Auditor',
                desc: 'Invalid or missing auditor output → AUDIT_UNTRUSTED → no rollout. Never silently approved.',
                color: 'border-emerald-800/40 text-emerald-400',
              },
              {
                title: 'Deterministic Gate',
                desc: 'LLM output is never the final authorization. Code-only threshold checks control rollout.',
                color: 'border-indigo-800/40 text-indigo-400',
              },
              {
                title: '3-Attempt Hard Cap',
                desc: 'Maximum 3 autonomous repair attempts persisted in database. Exceeding cap → QUARANTINED.',
                color: 'border-amber-800/40 text-amber-400',
              },
            ].map(({ title, desc, color }) => (
              <div key={title} className={`card p-6 border ${color.split(' ')[0]}`}>
                <Lock size={20} className={`${color.split(' ')[1]} mb-3`} />
                <h3 className="font-semibold text-white mb-2">{title}</h3>
                <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────── */}
      <section className="py-20 px-6 border-t border-[#1f2937] text-center">
        <div className="max-w-xl mx-auto">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to see it run?</h2>
          <p className="text-gray-500 mb-8">
            Launch the demo. Choose a scenario. Watch Bob investigate, repair, and validate — or quarantine when unsafe.
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="btn-primary text-base py-3 px-10"
          >
            Launch Demo →
          </button>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────── */}
      <footer className="border-t border-[#1f2937] py-8 px-6 text-center">
        <p className="text-xs text-gray-600">
          AETHERIS AI — Built with IBM Bob IDE for IBM Bob Hackathon 2.0 · All demo data is synthetic · No real production data used
        </p>
      </footer>
    </div>
  )
}