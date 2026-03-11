import { LOCATION_CONFIG, ACTION_COLOR, jitter } from '../../utils/helpers.js'

// Stable colors for agents (indexed by order)
const AGENT_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f97316', '#a855f7',
  '#14b8a6', '#f59e0b', '#ec4899', '#6366f1', '#84cc16',
  '#06b6d4', '#e11d48', '#7c3aed', '#10b981', '#f43f5e',
  '#0ea5e9', '#d97706', '#65a30d',
]

export default function WorldView({ adaptedRound, prevAdaptedRound, focusedAgent, showTrails, onAgentClick }) {
  if (!adaptedRound) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#334155' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, opacity: 0.3, marginBottom: 12 }}>◉</div>
          <div style={{ fontSize: 13 }}>Run a simulation to see the world view</div>
        </div>
      </div>
    )
  }

  const { agents } = adaptedRound
  const prevAgents = prevAdaptedRound?.agents ?? []

  // Assign positions with jitter
  const positioned = agents.map((a, i) => {
    const loc = LOCATION_CONFIG[a.locationId]
    const baseX = loc?.x ?? 50
    const baseY = loc?.y ?? 50
    return {
      ...a,
      x: jitter(baseX, 6, i * 3 + adaptedRound.round),
      y: jitter(baseY, 5, i * 7 + adaptedRound.round + 1),
      color: AGENT_COLORS[i % AGENT_COLORS.length],
    }
  })

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      {/* Ambient dot grid */}
      <div style={{
        position: 'absolute', inset: 0, opacity: 0.03, pointerEvents: 'none',
        backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }} />

      {/* Location zones */}
      {Object.values(LOCATION_CONFIG).map((loc) => {
        const agentsHere = agents.filter((a) => a.locationId === loc.id)
        return (
          <div
            key={loc.id}
            style={{
              position: 'absolute', left: `${loc.x}%`, top: `${loc.y}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            {/* Glow */}
            <div style={{
              position: 'absolute', inset: -48, borderRadius: '50%', opacity: 0.1, pointerEvents: 'none',
              background: `radial-gradient(circle, ${loc.color}, transparent 70%)`,
            }} />
            <div style={{ position: 'relative', textAlign: 'center', marginBottom: 8 }}>
              <div style={{ fontSize: 22, marginBottom: 4 }}>{loc.icon}</div>
              <div style={{
                fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
                padding: '2px 8px', borderRadius: 9999,
                background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(71,85,105,0.5)',
                color: loc.color, whiteSpace: 'nowrap',
              }}>
                {loc.name}
              </div>
              <div style={{ fontSize: 9, color: '#475569', marginTop: 2 }}>{agentsHere.length} present</div>
            </div>
          </div>
        )
      })}

      {/* Trail lines */}
      {showTrails && prevAgents.length > 0 && (
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }}>
          {agents.map((a, i) => {
            const prev = prevAgents.find((p) => p.name === a.name)
            if (!prev || prev.locationId === a.locationId) return null
            const fromLoc = LOCATION_CONFIG[prev.locationId]
            const toLoc = LOCATION_CONFIG[a.locationId]
            if (!fromLoc || !toLoc) return null
            return (
              <line
                key={a.name}
                x1={`${fromLoc.x}%`} y1={`${fromLoc.y}%`}
                x2={`${toLoc.x}%`}  y2={`${toLoc.y}%`}
                stroke={AGENT_COLORS[i % AGENT_COLORS.length]} strokeWidth={1}
                opacity={0.15} strokeDasharray="4,4"
              />
            )
          })}
        </svg>
      )}

      {/* Agents */}
      {positioned.map((a) => {
        const isFocused = focusedAgent === a.name
        const isDefocused = focusedAgent && !isFocused
        const actionCol = ACTION_COLOR[a.action] ?? '#94a3b8'
        const isVoice = a.action === 'speak' || a.action === 'post'
        const isResource = a.action === 'graze' || a.action === 'share'

        return (
          <div
            key={a.name}
            style={{
              position: 'absolute', left: `${a.x}%`, top: `${a.y}%`,
              transform: 'translate(-50%, -50%)',
              zIndex: isFocused ? 30 : 10,
              opacity: isDefocused ? 0.3 : 1,
              transition: 'all 700ms ease-out',
            }}
          >
            <button
              onClick={() => onAgentClick(a.name)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}
            >
              {/* Pulse ring for resource actions */}
              {isResource && (
                <div className="animate-ping" style={{
                  position: 'absolute', inset: -12, borderRadius: '50%',
                  background: actionCol, opacity: 0.2, pointerEvents: 'none',
                }} />
              )}
              <div style={{
                width: 28, height: 28, borderRadius: '50%', border: `2px solid ${a.color}`,
                background: `${a.color}22`, display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: 9, fontWeight: 700, color: a.color,
                boxShadow: isFocused ? `0 0 16px ${a.color}44` : 'none',
                transition: 'transform 150ms',
              }}>
                {a.name[0]}
              </div>
              <div style={{ fontSize: 9, fontWeight: 600, marginTop: 2, color: a.color, whiteSpace: 'nowrap' }}>
                {a.name}
              </div>
              {a.resources > 0 && (
                <div style={{ fontSize: 8, color: 'rgba(251,191,36,0.8)', fontFamily: 'var(--font-mono)' }}>
                  🌿{a.resources}
                </div>
              )}
            </button>

            {/* Speech bubble */}
            {isVoice && (
              <div style={{
                position: 'absolute', left: 32, top: 0, width: 180, pointerEvents: 'none', zIndex: 20,
                padding: '6px 10px', borderRadius: 8, fontSize: 10, lineHeight: 1.5,
                background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(4px)',
                border: `1px solid ${actionCol}33`, color: '#cbd5e1',
              }}>
                {a.action.toUpperCase()} at {LOCATION_CONFIG[a.locationId]?.name ?? a.locationId}
              </div>
            )}

            {/* Action badge for graze/share */}
            {isResource && (
              <div style={{
                position: 'absolute', right: -4, top: -4, padding: '2px 6px',
                borderRadius: 4, fontSize: 8, fontWeight: 700,
                background: a.action === 'graze' ? 'rgba(120,53,15,0.8)' : 'rgba(6,78,59,0.8)',
                color: a.action === 'graze' ? '#fcd34d' : '#6ee7b7',
                border: `1px solid ${actionCol}66`,
              }}>
                {a.action.toUpperCase()}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
