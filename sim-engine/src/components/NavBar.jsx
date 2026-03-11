import { useSim } from '../context/SimContext.jsx'
import '../styles/navbar.css'

function NavBar() {
  const { scenarios, activeScenarioId, setScenario } = useSim()

  return (
    <nav className="navbar">
      <div className="navbar__title">
        <span className="navbar__title-star">★</span>
        {' SIM ENGINE '}
        <span className="navbar__title-star">★</span>
      </div>
      <div className="navbar__tabs">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            className={`retro-btn ${scenario.id === activeScenarioId ? 'retro-btn--active' : ''}`}
            onClick={() => setScenario(scenario.id)}
          >
            {scenario.name}
          </button>
        ))}
      </div>
    </nav>
  )
}

export default NavBar
