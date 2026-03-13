import { useState, useEffect } from 'react'
import ResourceBar from './shared/ResourceBar.jsx'
import { listRuns } from '../api/simulation.js'

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
  onLoadRun,
}) {
  const isStreaming = status === 'streaming'
  const canRun = status === 'idle' || status === 'done' || status === 'error' || status === 'paused'

  // Past runs for the load dropdown
  const [pastRuns, setPastRuns] = useState([])
  const [showRunPicker, setShowRunPicker] = useState(false)

  useEffect(() => {
    if (showRunPicker && pastRuns.length === 0) {
      listRuns(20)
        .then(setPastRuns)
        .catch(() => {})
    }
  }, [showRunPicker, pastRuns.length])

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

            {/* Load past run */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowRunPicker((v) => !v)}
                disabled={isStreaming}
                style={{
                  padding: '4px 10px', borderRadius: 6, fontSize: 11,
                  fontWeight: 600, border: '1px solid #334155',
                  cursor: isStreaming ? 'not-allowed' : 'pointer',
                  background: showRunPicker ? 'rgba(51,65,85,0.4)' : 'transparent',
                  color: isStreaming ? '#475569' : '#94a3b8',
                }}
              >
                Load
              </button>
              {showRunPicker && (
                <div style={{
                  position: 'absolute', top: '100%', right: 0, marginTop: 4,
                  background: '#0f172a', border: '1px solid #334155',
                  borderRadius: 8, minWidth: 280, maxHeight: 320,
                  overflowY: 'auto', zIndex: 100, boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
                }}>
                  {pastRuns.length === 0 ? (
                    <div style={{ padding: '12px 16px', fontSize: 11, color: '#64748b' }}>
                      No completed runs found
                    </div>
                  ) : (
                    pastRuns.map((run) => {
                      const ts = run.timestamp
                        ? new Date(run.timestamp).toLocaleString()
                        : 'Unknown time'
                      const rounds = run.rounds_count ?? '?'
                      const gini = run.final_summary?.ablation_metrics?.gini_final
                      return (
                        <button
                          key={run.run_id}
                          onClick={() => {
                            setShowRunPicker(false)
                            onLoadRun(run.run_id)
                          }}
                          style={{
                            display: 'block', width: '100%', textAlign: 'left',
                            padding: '10px 16px', background: 'transparent',
                            border: 'none', borderBottom: '1px solid #1e293b',
                            cursor: 'pointer', color: '#e2e8f0',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(51,65,85,0.4)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                          <div style={{ fontSize: 11, fontWeight: 600 }}>{ts}</div>
                          <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                            {rounds} rounds{gini != null ? ` · Gini ${gini.toFixed(3)}` : ''}
                            {' · '}{run.status}
                          </div>
                        </button>
                      )
                    })
                  )}
                </div>
              )}
            </div>
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
