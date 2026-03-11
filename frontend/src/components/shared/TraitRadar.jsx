/**
 * TraitRadar — mini SVG pentagon radar chart for Big Five traits.
 * Props: traits ({ O, C, E, A, N } values 0–1), size (px, default 100)
 */
export default function TraitRadar({ traits, size = 100 }) {
  const labels = Object.keys(traits)
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.38
  const angleStep = (2 * Math.PI) / labels.length

  const dataPoints = labels.map((_, i) => {
    const a = angleStep * i - Math.PI / 2
    const val = Object.values(traits)[i]
    return `${cx + r * val * Math.cos(a)},${cy + r * val * Math.sin(a)}`
  }).join(' ')

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Grid rings */}
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon
          key={ring}
          points={labels.map((_, i) => {
            const a = angleStep * i - Math.PI / 2
            return `${cx + r * ring * Math.cos(a)},${cy + r * ring * Math.sin(a)}`
          }).join(' ')}
          fill="none"
          stroke="#334155"
          strokeWidth={0.5}
        />
      ))}
      {/* Data polygon */}
      <polygon
        points={dataPoints}
        fill="rgba(139,92,246,0.2)"
        stroke="#8b5cf6"
        strokeWidth={1.5}
      />
      {/* Axis labels */}
      {labels.map((label, i) => {
        const a = angleStep * i - Math.PI / 2
        const lx = cx + (r + 12) * Math.cos(a)
        const ly = cy + (r + 12) * Math.sin(a)
        return (
          <text
            key={label}
            x={lx}
            y={ly}
            textAnchor="middle"
            dominantBaseline="central"
            fill="#94a3b8"
            fontSize={9}
            fontWeight={600}
            fontFamily="monospace"
          >
            {label}
          </text>
        )
      })}
    </svg>
  )
}
