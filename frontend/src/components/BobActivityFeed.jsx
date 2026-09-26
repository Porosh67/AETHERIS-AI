import React from 'react'

const EVENT_STYLES = {
  BOB_INFO:    { border: 'border-indigo-900/50', dot: 'bg-indigo-500',  text: 'text-indigo-300' },
  BOB_SUCCESS: { border: 'border-emerald-900/50',dot: 'bg-emerald-500', text: 'text-emerald-300' },
  BOB_WARNING: { border: 'border-amber-900/50',  dot: 'bg-amber-500',   text: 'text-amber-300' },
  BOB_ERROR:   { border: 'border-red-900/50',    dot: 'bg-red-500',     text: 'text-red-400' },
}

export default function BobActivityFeed({ events }) {
  const ref = React.useRef(null)

  React.useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [events])

  if (!events || events.length === 0) {
    return (
      <div className="card p-4 h-64 flex items-center justify-center">
        <span className="text-gray-600 text-sm font-mono">Waiting for Bob activity...</span>
      </div>
    )
  }

  return (
    <div ref={ref} className="card p-0 overflow-y-auto h-80 scroll-smooth">
      <div className="sticky top-0 bg-[#111827] px-4 py-2 border-b border-[#1f2937]">
        <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">BOB EXECUTION TRACE</span>
      </div>
      <div className="pt-4 px-3 pb-3 space-y-1">
        {events.map((evt) => {
          const style = EVENT_STYLES[evt.event_type] || EVENT_STYLES.BOB_INFO
          const time = new Date(evt.timestamp).toLocaleTimeString('en', { hour12: false })
          return (
            <div key={evt.id} className={`flex items-start gap-2.5 py-1.5 px-2 rounded border ${style.border} bg-black/20`}>
              <span className={`w-1.5 h-1.5 rounded-full ${style.dot} flex-shrink-0 mt-1.5`} />
              <div className="flex-1 min-w-0">
                <span className={`text-xs font-mono ${style.text}`}>{evt.message}</span>
                {evt.detail && (
                  <div className="text-xs text-gray-700 mt-0.5 truncate">{evt.detail}</div>
                )}
              </div>
              <span className="text-xs text-gray-700 font-mono flex-shrink-0">{time}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}