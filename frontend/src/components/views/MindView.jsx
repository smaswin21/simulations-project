import TraitRadar from '../shared/TraitRadar.jsx'
import { ACTION_COLOR, LOCATION_CONFIG } from '../../utils/helpers.js'

// Placeholder traits (the backend does not stream Big Five per round)
const PLACEHOLDER_TRAITS = { O: 0.5, C: 0.5, E: 0.5, A: 0.5, N: 0.5 }

export default function MindView({ focusedAgent, onAgentClick, rounds, currentIndex }) {
  // Collect unique agent names from the first round we have
  const firstRound = rounds[0]
  const agentNames = firstRound ? firstRound.agents.map((a, i) => ({ name: a.name, idx: i })) : []

  if (!focusedAgent) {
    return (
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', color: '#64748b', padding: 20,
      }}>
        <div style={{ fontSize: 40, opacity: 0.3, marginBottom: 12 }}>◎</div>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 16 }}>Select an agent to view their mind</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
          {agentNames.map(({ name, idx }) => (
            <button
              key={name}
              onClick={() => onAgentClick(name)}
              style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 11,
                fontWeight: 600, border: '1px solid rgba(51,65,85,0.5)',
                background: 'transparent', cursor: 'pointer',
                color: AGENT_COLORS[idx % AGENT_COLORS.length],
              }}
            >
              {name}
            </button>
          ))}
        </div>
      </div>
    )
  }

  const agentIdx = agentNames.findIndex((a) => a.name === focusedAgent)
  const color = AGENT_COLORS[agentIdx % AGENT_COLORS.length] ?? '#94a3b8'

  // Build action history up to currentIndex
  const history = rounds.slice(0, currentIndex + 1).map((r) => {
    const entry = r.agents.find((a) => a.name === focusedAgent)
    return entry ? { round: r.round, ...entry } : null
  }).filter(Boolean)

  const latest = history[history.length - 1]

  return (
    <div style={{ position: 'absolute', inset: 0, overflowY: 'auto', padding: 20 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 12, border: `2px solid ${color}`,
            background: `${color}15`, display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: 20, fontWeight: 700,
          }}>
            {focusedAgent[0]}
          </div>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>{focusedAgent}</h2>
            <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
              {latest && (
                <>
                  <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: '#1e293b', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                    Status: {latest.status}
                  </span>
                  <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(120,53,15,0.5)', color: '#fcd34d', fontFamily: 'var(--font-mono)' }}>
                    🌿 {latest.resources}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Personality radar */}
          <div style={{ borderRadius: 12, background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(51,65,85,0.6)', padding: 16 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
              Personality Profile
            </div>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <TraitRadar traits={PLACEHOLDER_TRAITS} size={140} />
            </div>
            <div style={{ fontSize: 9, color: '#475569', textAlign: 'center', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
              Trait data available from agent profiles
            </div>
          </div>

          {/* Action summary */}
          <div style={{ borderRadius: 12, background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(51,65,85,0.6)', padding: 16 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
              Action Summary
            </div>
            {/* Count actions by type */}
            {(() => {
              const counts = {}
              history.forEach((h) => { counts[h.action] = (counts[h.action] ?? 0) + 1 })
              return Object.entries(counts).map(([action, count]) => (
                <div key={action} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: ACTION_COLOR[action] ?? '#94a3b8', flexShrink: 0 }} />
                  <span style={{ fontSize: 11, color: '#cbd5e1', textTransform: 'capitalize' }}>{action}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: '#64748b' }}>×{count}</span>
                </div>
              ))
            })()}
          </div>
        </div>

        {/* Action timeline */}
        <div style={{ borderRadius: 12, background: 'rgba(15,23,42,0.5)', border: '1px solid rgba(51,65,85,0.6)', padding: 16 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>
            Action Timeline
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {history.map((h) => (
              <div key={h.round} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#475569', width: 24, flexShrink: 0, paddingTop: 2 }}>
                  R{h.round}
                </div>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: ACTION_COLOR[h.action] ?? '#94a3b8', flexShrink: 0, marginTop: 4 }} />
                <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.5 }}>
                  <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', marginRight: 6, color: ACTION_COLOR[h.action] ?? '#94a3b8' }}>
                    {h.action.toUpperCase()}
                  </span>
                  at {LOCATION_CONFIG[h.locationId]?.name ?? h.locationId}
                  {h.resources > 0 && ` — 🌿 ${h.resources}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
