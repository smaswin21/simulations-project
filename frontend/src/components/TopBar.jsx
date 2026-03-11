import ResourceBar from './shared/ResourceBar.jsx'

const VIEW_MODES = [
  { id: 'world', label: 'World', icon: '◉' },
  { id: 'mind', label: 'Mind', icon: '◎' },
  { id: 'fabric', label: 'Fabric', icon: '◈' },
]

export default function TopBar({
  viewMode, onViewModeChange,
  depotStock, depotMax,
  round, maxRounds,
  status, params, onParamsChange, onRun,
}) {
  const isStreaming = status === 'streaming'
  const canRun = status === 'idle' || status === 'done' || status === 'error' || status === 'paused'

  return (
    <div style={{
      borderBottom: '1px solid rgba(51,65,85,0.8)',
      background: 'rgba(2,6,23,0.6)',
      backdropFilter: 'blur(12px)',
      position: 'sticky', top: 0, zIndex: 50,
    }}>
      <div style={{
        maxWidth: 1280, margin: '0 auto',
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
      }}>
        {/* Logo + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ position: 'relative' }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'linear-gradient(135deg, #7c3aed, #4338ca)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700,
            }}>ST</div>
            {isStreaming && (
              <div className="animate-pulse" style={{
                position: 'absolute', top: -2, right: -2,
                width: 10, height: 10, borderRadius: '50%', background: '#ef4444',
              }} />
            )}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', letterSpacing: '-0.02em' }}>
              Simulation Theater
            </div>
            <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              TRAGEDY OF THE COMMONS
            </div>
          </div>
        </div>

        {/* View mode tabs */}
        <div style={{
          display: 'flex', gap: 2, background: 'rgba(15,23,42,0.8)',
          borderRadius: 8, padding: 2, border: '1px solid rgba(51,65,85,1)',
        }}>
          {VIEW_MODES.map((v) => (
            <button
              key={v.id}
              onClick={() => onViewModeChange(v.id)}
              style={{
                padding: '6px 12px', borderRadius: 6, fontSize: 11,
                fontWeight: 600, border: 'none', cursor: 'pointer',
                background: viewMode === v.id ? '#334155' : 'transparent',
                color: viewMode === v.id ? '#fff' : '#64748b',
                transition: 'all 150ms',
              }}
            >
              {v.icon} {v.label}
            </button>
          ))}
        </div>

        {/* Run controls + round info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Params */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <input
                type="checkbox"
                checked={params.memoryOn}
                onChange={(e) => onParamsChange({ ...params, memoryOn: e.target.checked })}
                disabled={isStreaming}
              />
              Memory
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              Rounds
              <input
                type="number" min={1} max={20}
                value={params.rounds}
                onChange={(e) => onParamsChange({ ...params, rounds: e.target.value })}
                disabled={isStreaming}
                style={{
                  width: 48, background: '#1e293b', color: '#f1f5f9',
                  border: '1px solid #334155', borderRadius: 4,
                  padding: '2px 4px', fontFamily: 'var(--font-mono)', fontSize: 11,
                }}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              Seed
              <input
                type="number"
                value={params.seed}
                placeholder="rand"
                onChange={(e) => onParamsChange({ ...params, seed: e.target.value })}
                disabled={isStreaming}
                style={{
                  width: 56, background: '#1e293b', color: '#f1f5f9',
                  border: '1px solid #334155', borderRadius: 4,
                  padding: '2px 4px', fontFamily: 'var(--font-mono)', fontSize: 11,
                }}
              />
            </label>
            <button
              onClick={onRun}
              disabled={!canRun}
              style={{
                padding: '4px 12px', borderRadius: 6, fontSize: 11,
                fontWeight: 700, border: '1px solid',
                cursor: canRun ? 'pointer' : 'not-allowed',
                background: canRun ? 'rgba(124,58,237,0.2)' : 'transparent',
                borderColor: canRun ? '#7c3aed' : '#334155',
                color: canRun ? '#c4b5fd' : '#475569',
              }}
            >
              {isStreaming ? 'Running…' : 'Run'}
            </button>
          </div>

          {/* Depot stock */}
          {depotStock != null && (
            <div style={{ minWidth: 140 }}>
              <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
                Commons Stock
              </div>
              <ResourceBar current={depotStock} max={depotMax} />
            </div>
          )}

          {/* Round counter */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 9, color: '#64748b', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Round
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
              {round ?? '—'}{maxRounds ? `/${maxRounds}` : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
