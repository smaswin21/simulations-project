import { useSim } from '../context/SimContext.jsx'
import { useSimulation } from '../hooks/useSimulation.js'

function StatusBar() {
  const { activeScenario } = useSim()
  const { isRunning, togglePlayback } = useSimulation()

  if (!activeScenario) return null

  const { round, maxRounds, stats } = activeScenario

  return (
    <div className="status-bar">
      <button
        className={`retro-btn status-bar__play ${isRunning ? 'retro-btn--active' : ''}`}
        onClick={togglePlayback}
      >
        {isRunning ? '❚❚' : '▶'}
      </button>
      <div className="status-bar__item">
        <span className="status-bar__label">Round</span>
        <span className="status-bar__value">{round}/{maxRounds}</span>
      </div>
      <div className="status-bar__item">
        <span className="status-bar__icon status-bar__icon--alive">♥</span>
        <span className="status-bar__value">{stats.thriving} Thriving</span>
      </div>
      <div className="status-bar__item">
        <span className="status-bar__icon status-bar__icon--dead">☠</span>
        <span className="status-bar__value">{stats.depleted} Depleted</span>
      </div>
      <div className="status-bar__item">
        <span className="status-bar__icon status-bar__icon--resource">+</span>
        <span className="status-bar__value">{stats.totalGrazed}/{stats.stockRemaining} Grazed</span>
      </div>
    </div>
  )
}

export default StatusBar
