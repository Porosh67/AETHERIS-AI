import React, { useState } from 'react'
import { CheckItem, RiskBadge } from './StatusComponents'
import { Copy, Check, Zap, Clock } from 'lucide-react'

export function PatchView({ patch }) {
  const [copied, setCopied] = useState(false)
  if (!patch) return null
  const content = patch.content || {}
  const diff = content.diff || ''

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(diff)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Patch Diff</span>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-600">Attempt {patch.attempt_num}</span>
          <span className="text-xs font-mono bg-purple-900/30 text-purple-400 border border-purple-800/30 px-2 py-0.5 rounded">
            {content.patch_type || 'UNKNOWN'}
          </span>
          {diff && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-xs font-mono text-gray-500 hover:text-gray-300 border border-[#1f2937] hover:border-[#374151] rounded px-2 py-0.5 transition-colors"
            >
              {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              {copied ? 'Copied' : 'Copy Patch'}
            </button>
          )}
        </div>
      </div>

      {content.description && (
        <p className="text-sm text-gray-300 mb-3">{content.description}</p>
      )}

      {content.file && (
        <div className="text-xs font-mono text-gray-500 mb-2">📄 {content.file}</div>
      )}

      {/* GitHub-style diff: colored line backgrounds, not just text color */}
      {diff && (
        <div className="text-xs font-mono bg-black/40 border border-[#1f2937] rounded overflow-x-auto max-h-64 overflow-y-auto">
          {diff.split('\n').map((line, i) => {
            const isAdd = line.startsWith('+') && !line.startsWith('+++')
            const isDel = line.startsWith('-') && !line.startsWith('---')
            const isHunk = line.startsWith('@')
            return (
              <div
                key={i}
                className={`px-3 py-0.5 whitespace-pre border-l-2 ${
                  isAdd ? 'bg-emerald-950/40 border-emerald-600 text-emerald-400' :
                  isDel ? 'bg-red-950/40 border-red-600 text-red-400' :
                  isHunk ? 'bg-cyan-950/30 border-cyan-700 text-cyan-400' :
                  'border-transparent text-gray-500'
                }`}
              >
                {line || ' '}
              </div>
            )
          })}
        </div>
      )}

      <div className="mt-3 flex items-center gap-3 text-xs text-gray-600 font-mono flex-wrap">
        <span>hash: {patch.patch_hash?.slice(0, 16)}...</span>
        {content.lines_changed && <span>Δ {content.lines_changed} lines</span>}
        {content.risk_surface && <span className="text-yellow-600">risk: {content.risk_surface}</span>}
      </div>

      {/* Execution metrics */}
      {(patch.latency_ms != null || patch.model_used) && (
        <div className="mt-3 pt-3 border-t border-[#1f2937] flex items-center gap-4 text-xs font-mono text-gray-500">
          {patch.latency_ms != null && (
            <span className="flex items-center gap-1">
              <Clock size={11} /> {patch.latency_ms}ms
            </span>
          )}
          {patch.model_used && (
            <span className="flex items-center gap-1">
              <Zap size={11} /> {patch.model_used}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export function TestResultsView({ tests }) {
  if (!tests || !tests.total) return null
  const cases = tests.test_cases || []
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Test Results</span>
        <span className={`text-xs font-mono font-bold ${tests.pass_rate >= 0.95 ? 'text-emerald-400' : 'text-red-400'}`}>
          {tests.passed}/{tests.total} ({(tests.pass_rate * 100).toFixed(0)}%)
        </span>
      </div>
      <div className="w-full bg-gray-900 rounded-full h-1.5 mb-3">
        <div
          className={`h-1.5 rounded-full ${tests.pass_rate >= 0.95 ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={{ width: `${(tests.pass_rate * 100).toFixed(0)}%` }}
        />
      </div>
      <div className="max-h-56 overflow-y-auto pt-1 space-y-0.5">
        {cases.map((tc, i) => (
          <div key={i} className="flex items-center gap-2 py-0.5">
            <span className={`text-xs ${tc.passed ? 'text-emerald-500' : 'text-red-500'}`}>{tc.passed ? '✓' : '✗'}</span>
            <span className="text-xs font-mono text-gray-400 truncate">{tc.name}</span>
            <span className="text-xs text-gray-700 ml-auto">{tc.duration_ms?.toFixed(0)}ms</span>
          </div>
        ))}
      </div>
      <div className="mt-2 text-xs text-gray-600 font-mono">Total: {tests.duration_ms?.toFixed(0)}ms</div>
    </div>
  )
}

export function AuditView({ audit }) {
  if (!audit) return null
  return (
    <div className={`card p-4 ${!audit.trusted ? 'border-red-800/50' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Auditor Findings</span>
        <span className={`text-xs font-mono font-bold ${
          !audit.trusted ? 'text-red-400' :
          audit.recommendation === 'APPROVE' ? 'text-emerald-400' :
          'text-red-400'
        }`}>
          {!audit.trusted ? '⚠ AUDIT_UNTRUSTED' : audit.recommendation}
        </span>
      </div>

      {!audit.trusted && audit.untrust_reason && (
        <div className="text-xs text-red-400 bg-red-950/30 border border-red-800/30 rounded p-2 mb-3">
          Fail-closed: {audit.untrust_reason}
        </div>
      )}

      {audit.trusted && (
        <>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div>
              <div className="text-xs text-gray-600 mb-1">Security Risk</div>
              <RiskBadge risk={audit.security_risk} />
            </div>
            <div>
              <div className="text-xs text-gray-600 mb-1">Regression Risk</div>
              <RiskBadge risk={audit.regression_risk} />
            </div>
          </div>
          {audit.findings_summary && (
            <p className="text-xs text-gray-400 mb-3 leading-relaxed">{audit.findings_summary}</p>
          )}
          {audit.edge_cases?.length > 0 && (
            <div>
              <div className="text-xs text-gray-600 mb-1">Edge Cases</div>
              {audit.edge_cases.map((ec, i) => (
                <div key={i} className="text-xs text-gray-500 font-mono">· {ec}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export function GateView({ gate }) {
  if (!gate) return null
  const checks = gate.checks || []
  return (
    <div className={`card p-4 ${gate.passed ? 'border-emerald-800/30' : 'border-red-800/40'}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Release Gate</span>
        <span className={`text-xs font-mono font-bold ${gate.passed ? 'text-emerald-400' : 'text-red-400'}`}>
          {gate.passed ? '✓ PASSED' : '✗ BLOCKED'}
        </span>
      </div>
      <div className="text-xs text-gray-600 mb-2 italic">LLM output is NOT the authorization — deterministic checks only</div>
      <div>
        {checks.map((c, i) => (
          <CheckItem key={i} passed={c.passed} name={c.name} detail={c.detail} />
        ))}
      </div>
    </div>
  )
}

export function CanaryView({ canary }) {
  if (!canary) return null
  const m = canary.metrics || {}
  return (
    <div className={`card p-4 ${canary.passed ? 'border-emerald-800/30' : 'border-red-800/40'}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Canary</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-600 italic">[SIMULATED]</span>
          <span className={`text-xs font-mono font-bold ${canary.passed ? 'text-emerald-400' : 'text-red-400'}`}>
            {canary.passed ? '✓ HEALTHY' : '✗ DEGRADED'}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-gray-600">Error Rate</div>
          <div className={`text-lg font-mono font-bold ${m.error_rate > 0.02 ? 'text-red-400' : 'text-emerald-400'}`}>
            {m.error_rate != null ? (m.error_rate * 100).toFixed(2) + '%' : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-600">p99 Latency</div>
          <div className={`text-lg font-mono font-bold ${m.p99_latency_ms > 500 ? 'text-red-400' : 'text-emerald-400'}`}>
            {m.p99_latency_ms != null ? m.p99_latency_ms.toFixed(0) + 'ms' : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-600">Health Polls</div>
          <div className="text-lg font-mono font-bold text-gray-300">
            {m.healthy_polls ?? '—'}/{m.health_polls ?? '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-600">Traffic</div>
          <div className="text-lg font-mono font-bold text-gray-300">{m.traffic_percent ?? '—'}%</div>
        </div>
      </div>
      {canary.reason && (
        <p className="text-xs text-gray-500 mt-3 italic">{canary.reason}</p>
      )}
    </div>
  )
}

export function EvidenceView({ evidence, onVerify, verifying }) {
  if (!evidence) return null
  return (
    <div className={`card p-4 ${
      evidence.verified === true ? 'border-emerald-800/40' :
      evidence.verified === false ? 'border-red-800/40' :
      ''
    }`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Cryptographic Evidence</span>
        {evidence.verified != null && (
          <span className={`text-xs font-mono font-bold ${evidence.verified ? 'text-emerald-400' : 'text-red-400'}`}>
            {evidence.verified ? '✓ VERIFIED' : '✗ INVALID'}
          </span>
        )}
      </div>

      <div className="space-y-1.5 mb-4">
        <div className="flex gap-2 text-xs">
          <span className="text-gray-600 w-28 flex-shrink-0">Incident</span>
          <span className="font-mono text-gray-300">{evidence.incident_id}</span>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-gray-600 w-28 flex-shrink-0">Final State</span>
          <span className={`font-mono font-bold ${
            evidence.final_state === 'ROLLED_OUT' ? 'text-emerald-400' : 'text-red-400'
          }`}>{evidence.final_state}</span>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-gray-600 w-28 flex-shrink-0">Attempts</span>
          <span className="font-mono text-gray-300">{evidence.attempt_count}</span>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-gray-600 w-28 flex-shrink-0">Signing Key</span>
          <span className="font-mono text-gray-500">{evidence.signing_key_id}</span>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-gray-600 w-28 flex-shrink-0">Signature</span>
          <span className="font-mono text-gray-500 break-all">
            {evidence.signature?.slice(0, 32)}...
          </span>
        </div>
        {evidence.patch_hash && (
          <div className="flex gap-2 text-xs">
            <span className="text-gray-600 w-28 flex-shrink-0">Patch Hash</span>
            <span className="font-mono text-gray-500">{evidence.patch_hash.slice(0, 32)}...</span>
          </div>
        )}
      </div>

      <button
        onClick={onVerify}
        disabled={verifying}
        className="btn-secondary text-xs py-2 w-full font-mono"
      >
        {verifying ? 'Verifying...' : '▶ VERIFY EVIDENCE'}
      </button>

      <p className="text-xs text-gray-700 mt-2 text-center italic">
        HMAC-SHA256 verification — UI shows VALID only if server confirms signature match
      </p>
    </div>
  )
}