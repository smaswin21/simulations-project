import { useSim } from '../context/SimContext.jsx'

function ParamsPanel() {
  const { activeScenario, updateParams } = useSim()

  if (!activeScenario) return null

  const { params } = activeScenario

  return (
    <div className="params-panel retro-panel">
      <div className="retro-label">Parameters</div>
      <div className="retro-divider" />

      <div className="params-panel__row">
        <span className="params-panel__label">Agents</span>
        <span className="params-panel__value">{params.numAgents}</span>
      </div>

      <div className="params-panel__row">
        <span className="params-panel__label">Memory</span>
        <div
          className={`retro-toggle ${params.memoryOn ? 'retro-toggle--on' : ''}`}
          onClick={() => updateParams({ memoryOn: !params.memoryOn })}
        >
          <div className="retro-toggle__track">
            <div className="retro-toggle__thumb" />
          </div>
          <span>{params.memoryOn ? 'ON' : 'OFF'}</span>
        </div>
      </div>

      <div className="params-panel__row">
        <span className="params-panel__label">Rounds</span>
        <span className="params-panel__value">{params.rounds}</span>
      </div>

      <div className="params-panel__row">
        <span className="params-panel__label">Speed</span>
        <input
          type="range"
          className="retro-slider"
          min="1"
          max="3"
          value={params.speed}
          onChange={(e) => updateParams({ speed: parseInt(e.target.value) })}
        />
      </div>
    </div>
  )
}

export default ParamsPanel
