import React from 'react'

const STATE_CONFIG = {
  IDLE:               { color: 'text-gray-500',   dot: 'bg-gray-600',   label: 'Idle' },
  INCIDENT_RECEIVED:  { color: 'text-red-400',    dot: 'bg-red-500',    label: 'Incident Received' },
  DIAGNOSING:         { color: 'text-blue-400',   dot: 'bg-blue-500 animate-pulse', label: 'Diagnosing' },
  PATCH_GENERATED:    { color: 'text-purple-400', dot: 'bg-purple-500', label: 'Patch Generated' },
  PATCH_TESTING:      { color: 'text-yellow-400', dot: 'bg-yellow-500 animate-pulse', label: 'Patch Testing' },
  AUDITING:           { color: 'text-orange-400', dot: 'bg-orange-500 animate-pulse', label: 'Auditing' },
  AUDIT_UNTRUSTED:    { color: 'text-red-400',    dot: 'bg-red-500',    label: 'Audit Untrusted' },
  CANARY_PENDING:     { color: 'text-cyan-400',   dot: 'bg-cyan-500',   label: 'Canary Pending' },
  CANARY_RUNNING:     { color: 'text-cyan-400',   dot: 'bg-cyan-500 animate-pulse', label: 'Canary Running' },
  ROLLED_OUT:         { color: 'text-emerald-400',dot: 'bg-emerald-500',label: 'Rolled Out ✓' },
  REPAIR_RETRY:       { color: 'text-amber-400',  dot: 'bg-amber-500',  label: 'Repair Retry' },
  QUARANTINED:        { color: 'text-red-500',    dot: 'bg-red-600',    label: 'Quarantined ⚠' },
}

export function StatePill({ state }) {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.IDLE
  return (
    <span className={`state-pill border-current/20 bg-current/5 ${cfg.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const map = {
    CRITICAL: 'badge-critical',
    HIGH:     'badge-high',
    MEDIUM:   'badge-medium',
    LOW:      'badge-low',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded border ${map[severity] || 'badge-info'}`}>
      {severity}
    </span>
  )
}

export function RiskBadge({ risk }) {
  const map = {
    LOW:      'badge-low',
    MEDIUM:   'badge-medium',
    HIGH:     'badge-high',
    CRITICAL: 'badge-critical',
    UNKNOWN:  'bg-gray-800 text-gray-400 border-gray-700',
  }
  return (
    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${map[risk] || 'badge-info'}`}>
      {risk}
    </span>
  )
}

export function CheckItem({ passed, name, detail }) {
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-[#1f2937] last:border-0">
      <span className={`text-xs font-mono mt-0.5 flex-shrink-0 ${passed ? 'text-emerald-400' : 'text-red-400'}`}>
        {passed ? '✓' : '✗'}
      </span>
      <div>
        <div className="text-xs text-gray-300 font-mono">{name}</div>
        {detail && <div className="text-xs text-gray-600 mt-0.5">{detail}</div>}
      </div>
    </div>
  )
}

export function MetricCard({ label, value, sub, color = 'text-white' }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold font-mono ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  )
}
