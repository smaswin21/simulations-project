const SPEEDS = [
  { label: '1×', key: '1x' },
  { label: '2×', key: '2x' },
  { label: '4×', key: '4x' },
]

export default function PlaybackControls({
  currentIndex, totalRounds,
  status, speed,
  onStepBack, onTogglePlay, onStepForward,
  onSeekTo, onSpeedChange,
}) {
  const isPlaying = status === 'playing'
  const canPlay = totalRounds > 0 && status !== 'streaming'

  const btnBase = {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    borderRadius: 8, border: '1px solid rgba(51,65,85,0.5)',
    cursor: 'pointer', fontSize: 12, transition: 'all 150ms',
    background: 'rgba(30,41,59,1)', color: '#94a3b8',
  }

  return (
    <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
      {/* Step back */}
      <button onClick={onStepBack} disabled={!canPlay} style={{ ...btnBase, width: 32, height: 32 }}>◂</button>

      {/* Play / Pause */}
      <button
        onClick={onTogglePlay}
        disabled={!canPlay}
        style={{
          ...btnBase, width: 40, height: 40, borderRadius: 10, fontSize: 14, fontWeight: 700,
          background: isPlaying ? 'rgba(127,29,29,0.6)' : 'rgba(76,29,149,0.5)',
          borderColor: isPlaying ? 'rgba(185,28,28,0.5)' : 'rgba(109,40,217,0.5)',
          color: isPlaying ? '#fca5a5' : '#c4b5fd',
        }}
      >
        {isPlaying ? '⏸' : '▶'}
      </button>

      {/* Step forward */}
      <button onClick={onStepForward} disabled={!canPlay} style={{ ...btnBase, width: 32, height: 32 }}>▸</button>

      {/* Scrubber */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 3 }}>
        {Array.from({ length: totalRounds }).map((_, i) => (
          <button
            key={i}
            onClick={() => onSeekTo(i)}
            style={{
              flex: 1, height: 8, borderRadius: 9999, border: 'none',
              cursor: 'pointer', padding: 0,
              background: i === currentIndex ? '#8b5cf6' : i < currentIndex ? '#475569' : '#1e293b',
              transform: i === currentIndex ? 'scaleY(1.5)' : 'scaleY(1)',
              transition: 'all 150ms',
            }}
          />
        ))}
      </div>

      {/* Speed */}
      <div style={{ display: 'flex', gap: 3 }}>
        {SPEEDS.map((s) => (
          <button
            key={s.key}
            onClick={() => onSpeedChange(s.key)}
            style={{
              padding: '4px 8px', borderRadius: 4, border: 'none',
              fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700,
              cursor: 'pointer',
              background: speed === s.key ? '#334155' : 'transparent',
              color: speed === s.key ? '#fff' : '#64748b',
            }}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}
