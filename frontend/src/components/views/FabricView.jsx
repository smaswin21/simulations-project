/**
 * FabricView — SVG social interaction graph.
 * Shows co-location frequencies as weighted edges between agent nodes.
 */
const AGENT_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f97316', '#a855f7',
  '#14b8a6', '#f59e0b', '#ec4899', '#6366f1', '#84cc16',
  '#06b6d4', '#e11d48', '#7c3aed', '#10b981', '#f43f5e',
  '#0ea5e9', '#d97706', '#65a30d',
]

export default function FabricView({ rounds, currentIndex, focusedAgent, onAgentNodeClick }) {
  if (rounds.length === 0) {
    return (
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#334155' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, opacity: 0.3, marginBottom: 12 }}>◈</div>
          <div style={{ fontSize: 13 }}>Run a simulation to see the social fabric</div>
        </div>
      </div>
    )
  }

  // Collect agent names from first round
  const agentNames = rounds[0].agents.map((a) => a.name)

  // Build edge weights: co-location across rounds 0..currentIndex
  const edgeMap = {}
  rounds.slice(0, currentIndex + 1).forEach((r) => {
    // Group agents by location
    const locGroups = {}
    r.agents.forEach((a) => {
      if (!locGroups[a.locationId]) locGroups[a.locationId] = []
      locGroups[a.locationId].push(a.name)
    })
    Object.values(locGroups).forEach((group) => {
      for (let i = 0; i < group.length; i++) {
        for (let j = i + 1; j < group.length; j++) {
          const key = [group[i], group[j]].sort().join('--')
          edgeMap[key] = (edgeMap[key] ?? 0) + 1
        }
      }
    })
  })

  const edges = Object.entries(edgeMap).map(([key, weight]) => {
    const [a, b] = key.split('--')
    return { a, b, weight }
  })

  // Circle layout
  const fabricPos = {}
  agentNames.forEach((name, i) => {
    const angle = (2 * Math.PI * i) / agentNames.length - Math.PI / 2
    fabricPos[name] = {
      x: 50 + 32 * Math.cos(angle),
      y: 50 + 32 * Math.sin(angle),
    }
  })

  // Current round resources per agent
  const currentRound = rounds[currentIndex]
  const resourceMap = {}
  if (currentRound) {
    currentRound.agents.forEach((a) => { resourceMap[a.name] = a.resources })
  }

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <svg style={{ width: '100%', height: '100%' }}>
        {/* Edges */}
        {edges.map((e, i) => {
          const pa = fabricPos[e.a]
          const pb = fabricPos[e.b]
          if (!pa || !pb) return null
          return (
            <line
              key={i}
              x1={`${pa.x}%`} y1={`${pa.y}%`}
              x2={`${pb.x}%`} y2={`${pb.y}%`}
              stroke="#475569"
              strokeWidth={Math.min(e.weight * 0.8, 4)}
              opacity={0.4 + Math.min(e.weight * 0.08, 0.4)}
            />
          )
        })}

        {/* Nodes */}
        {agentNames.map((name, i) => {
          const pos = fabricPos[name]
          if (!pos) return null
          const resources = resourceMap[name] ?? 0
          const nodeR = 14 + resources * 0.6
          const color = AGENT_COLORS[i % AGENT_COLORS.length]
          return (
            <g key={name} style={{ cursor: 'pointer' }} onClick={() => onAgentNodeClick(name)}>
              <circle cx={`${pos.x}%`} cy={`${pos.y}%`} r={nodeR}
                fill={`${color}22`} stroke={color} strokeWidth={2} />
              <text x={`${pos.x}%`} y={`${pos.y}%`} textAnchor="middle" dominantBaseline="central"
                fill="white" fontSize={10} fontWeight={600} fontFamily="Sora, sans-serif">
                {name.slice(0, 3)}
              </text>
              <text x={`${pos.x}%`} y={`${pos.y + 5}%`} textAnchor="middle"
                fill="#94a3b8" fontSize={9} fontFamily="IBM Plex Mono, monospace">
                🌿{resources}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16,
        padding: '8px 12px', borderRadius: 8,
        background: 'rgba(2,6,23,0.8)', border: '1px solid rgba(51,65,85,0.6)',
        fontSize: 10, color: '#475569',
      }}>
        Edge thickness = co-location frequency · Node size = resources held · Click node for mind view
      </div>
    </div>
  )
}
