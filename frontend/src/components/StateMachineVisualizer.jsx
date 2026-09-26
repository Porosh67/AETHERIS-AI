import React from 'react'

const ALL_STATES = [
  'IDLE', 'INCIDENT_RECEIVED', 'DIAGNOSING', 'PATCH_GENERATED',
  'PATCH_TESTING', 'AUDITING', 'CANARY_PENDING', 'CANARY_RUNNING', 'ROLLED_OUT',
]

const STATE_COLORS = {
  IDLE:              'bg-gray-800 text-gray-500 border-gray-700',
  INCIDENT_RECEIVED: 'bg-red-900/50 text-red-400 border-red-800/50',
  DIAGNOSING:        'bg-blue-900/50 text-blue-400 border-blue-800/50',
  PATCH_GENERATED:   'bg-purple-900/50 text-purple-400 border-purple-800/50',
  PATCH_TESTING:     'bg-yellow-900/50 text-yellow-400 border-yellow-800/50',
  AUDITING:          'bg-orange-900/50 text-orange-400 border-orange-800/50',
  CANARY_PENDING:    'bg-cyan-900/50 text-cyan-400 border-cyan-800/50',
  CANARY_RUNNING:    'bg-cyan-900/50 text-cyan-400 border-cyan-800/50',
  ROLLED_OUT:        'bg-emerald-900/50 text-emerald-400 border-emerald-800/50',
  REPAIR_RETRY:      'bg-amber-900/50 text-amber-400 border-amber-800/50',
  QUARANTINED:       'bg-red-900/80 text-red-400 border-red-700/80',
  AUDIT_UNTRUSTED:   'bg-red-900/50 text-red-400 border-red-800/50',
}

export default function StateMachineVisualizer({ currentState, transitions = [] }) {
  const visited = new Set(transitions.flatMap(t => [t.from_state, t.to_state]))
  const isTerminal = ['ROLLED_OUT', 'QUARANTINED'].includes(currentState)

  return (
    <div className="card p-4">
      <div className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">State Machine</div>

      {/* Main flow */}
      <div className="flex flex-wrap gap-2 items-center mb-4">
        {ALL_STATES.map((state, i) => {
          const isCurrent = state === currentState
          const wasVisited = visited.has(state)
          const base = STATE_COLORS[state] || 'bg-gray-800 text-gray-500 border-gray-700'
          return (
            <React.Fragment key={state}>
              <div className={`
                px-2.5 py-1 rounded border text-xs font-mono transition-all
                ${isCurrent ? `${base} ring-1 ring-current ring-offset-1 ring-offset-[#111827] font-bold` : ''}
                ${!isCurrent && wasVisited ? `${base} opacity-70` : ''}
                ${!isCurrent && !wasVisited ? 'bg-gray-900 text-gray-700 border-gray-800' : ''}
              `}>
                {isCurrent && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5 animate-pulse" />}
                {state}
              </div>
              {i < ALL_STATES.length - 1 && (
                <span className="text-gray-700 text-xs">→</span>
              )}
            </React.Fragment>
          )
        })}
      </div>

      {/* Special states */}
      <div className="flex gap-3">
        {['REPAIR_RETRY', 'QUARANTINED', 'AUDIT_UNTRUSTED'].map(state => {
          const isCurrent = state === currentState
          const base = STATE_COLORS[state]
          return (
            <div key={state} className={`
              px-2 py-1 rounded border text-xs font-mono
              ${isCurrent ? `${base} ring-1 ring-current` : 'bg-gray-900 text-gray-700 border-gray-800'}
            `}>
              {isCurrent && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse" />}
              {state}
            </div>
          )
        })}
      </div>

      {/* Transition log */}
      {transitions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[#1f2937]">
          <div className="text-xs text-gray-600 font-mono mb-2">TRANSITION LOG</div>
          <div className="space-y-1 max-h-28 overflow-y-auto">
            {transitions.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs font-mono text-gray-600">
                <span className="text-gray-700">{new Date(t.timestamp).toLocaleTimeString('en',{hour12:false})}</span>
                <span className="text-gray-500">{t.from_state}</span>
                <span className="text-gray-700">→</span>
                <span className={
                  t.to_state === 'ROLLED_OUT' ? 'text-emerald-500' :
                  t.to_state === 'QUARANTINED' ? 'text-red-500' :
                  'text-indigo-500'
                }>{t.to_state}</span>
                {t.reason && <span className="text-gray-700 truncate">· {t.reason}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
