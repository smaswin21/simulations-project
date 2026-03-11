/**
 * ActivityFeed — right panel with action log and agent holdings.
 *
 * Props:
 *   round       (number)
 *   actionLog   (Array<{ agent, locationId, action, detail, resources, color }>)
 *   focusedAgent (string|null)
 *   onAgentClick (fn(name) => void)
 */
export default function ActivityFeed({ round, actionLog, focusedAgent, onAgentClick }) {
  // Sort a copy by resources descending for holdings section
  const sorted = [...actionLog].sort((a, b) => b.resources - a.resources)
  const maxResources = Math.max(...sorted.map((a) => a.resources), 1)

  return (
    <div style={{
      width: 288, flexShrink: 0, display: 'flex', flexDirection: 'column',
      borderRadius: 16, border: '1px solid rgba(51,65,85,0.6)',
      background: 'rgba(2,6,23,0.4)', backdropFilter: 'blur(8px)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(51,65,85,0.6)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          Live Feed · Round {round ?? '—'}
        </div>
      </div>

      {/* Action log */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {actionLog.length === 0 && (
          <div style={{ color: '#475569', fontSize: 11, textAlign: 'center', paddingTop: 24 }}>
            No data yet — run a simulation
          </div>
        )}
        {actionLog.map((entry, i) => {
          const isHighlighted = focusedAgent === entry.agent
          return (
            <div
              key={i}
              onClick={() => onAgentClick(entry.agent)}
              style={{
                borderRadius: 8, padding: 10, cursor: 'pointer',
                border: `1px solid ${isHighlighted ? 'rgba(71,85,105,1)' : 'transparent'}`,
                background: isHighlighted ? 'rgba(30,41,59,0.6)' : 'rgba(15,23,42,0.3)',
                transition: 'all 150ms',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                {/* Avatar dot */}
                <div style={{
                  width: 16, height: 16, borderRadius: '50%', border: `1px solid ${entry.color}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 7, fontWeight: 700, color: entry.color,
                }}>
                  {entry.agent[0]}
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: entry.color }}>{entry.agent}</span>
                <span style={{
                  marginLeft: 'auto', fontSize: 9, fontFamily: 'var(--font-mono)',
                  padding: '2px 6px', borderRadius: 4,
                  background: `${entry.color}22`, color: entry.color,
                }}>
                  {entry.action.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.5, paddingLeft: 24 }}>
                {entry.detail.length > 80 ? entry.detail.slice(0, 80) + '…' : entry.detail}
              </div>
              <div style={{ fontSize: 9, color: '#475569', paddingLeft: 24, marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                {entry.resources > 0 && `🌿 ${entry.resources}`}
              </div>
            </div>
          )
        })}
      </div>

      {/* Holdings */}
      <div style={{ borderTop: '1px solid rgba(51,65,85,0.6)', padding: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
          Holdings
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {sorted.map((a) => (
            <div
              key={a.agent}
              onClick={() => onAgentClick(a.agent)}
              style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
            >
              <span style={{ fontSize: 10, fontWeight: 600, width: 64, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: a.color }}>
                {a.agent}
              </span>
              <div style={{ flex: 1, height: 6, borderRadius: 9999, background: '#1e293b', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 9999,
                  width: `${Math.min((a.resources / maxResources) * 100, 100)}%`,
                  background: a.color, opacity: 0.7,
                  transition: 'width 500ms',
                }} />
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#64748b', width: 16, textAlign: 'right' }}>
                {a.resources}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
