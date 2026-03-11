import { useSim } from '../context/SimContext.jsx'
import AgentSprite from './AgentSprite.jsx'
import '../styles/world.css'

const MARKER_COLORS = {
  civic: 'var(--nes-blue)',
  resource: 'var(--nes-green)',
  home: 'var(--nes-orange)',
}

function WorldGrid() {
  const { activeScenario } = useSim()

  if (!activeScenario) return null

  const { gridSize, markers, agents } = activeScenario
  const [cols, rows] = gridSize

  // Build a lookup of agents by grid position
  const agentMap = {}
  agents.forEach((agent) => {
    const key = `${agent.gridPos[0]}-${agent.gridPos[1]}`
    agentMap[key] = agent
  })

  // Build a lookup of markers by grid position
  const markerMap = {}
  markers.forEach((marker) => {
    const key = `${marker.col}-${marker.row}`
    markerMap[key] = marker
  })

  // Render all cells in the unified grid
  const cells = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const key = `${c}-${r}`
      const agent = agentMap[key]
      const marker = markerMap[key]

      cells.push(
        <div key={key} className="grid-cell">
          {marker && (
            <span
              className="grid-cell__marker"
              style={{ color: MARKER_COLORS[marker.type] || 'var(--nes-gray)' }}
            >
              {marker.name}
            </span>
          )}
          {agent && <AgentSprite agent={agent} />}
        </div>
      )
    }
  }

  return (
    <div className="world-grid">
      <div
        className="world-grid__unified retro-panel retro-panel--highlight"
        style={{
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
        }}
      >
        {cells}
      </div>
    </div>
  )
}

export default WorldGrid
