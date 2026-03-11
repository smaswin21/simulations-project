/**
 * ResourceBar — horizontal progress bar for depot/stock display.
 * Props: current (number), max (number, default 120)
 */
export default function ResourceBar({ current, max = 120 }) {
  const pct = Math.max(0, Math.min((current / max) * 100, 100))
  const color = pct > 50 ? '#22c55e' : pct > 25 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 9999,
        background: 'var(--color-surface-2)', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: 9999,
          width: `${pct}%`, background: color,
          transition: 'width 700ms ease',
        }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color, minWidth: 48 }}>
        {current}/{max}
      </span>
    </div>
  )
}
