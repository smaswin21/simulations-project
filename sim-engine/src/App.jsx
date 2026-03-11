import { useState, useEffect } from 'react'
import { SimProvider, useSim } from './context/SimContext.jsx'
import NavBar from './components/NavBar.jsx'
import WorldGrid from './components/WorldGrid.jsx'
import Sidebar from './components/Sidebar.jsx'
import StatusBar from './components/StatusBar.jsx'
import './styles/app.css'
import './styles/statusbar.css'

function AppContent() {
  const { activeScenarioId } = useSim()
  const [flicker, setFlicker] = useState(false)
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    // Skip flicker on initial mount
    if (!initialized) {
      setInitialized(true)
      return
    }
    setFlicker(true)
    const timer = setTimeout(() => setFlicker(false), 150)
    return () => clearTimeout(timer)
  }, [activeScenarioId])

  return (
    <div className={`app ${flicker ? 'app--flicker' : ''}`}>
      <NavBar />
      <main className="app__main">
        <div className="app__content">
          <WorldGrid />
        </div>
        <Sidebar />
      </main>
      <StatusBar />
    </div>
  )
}

function App() {
  return (
    <SimProvider>
      <AppContent />
    </SimProvider>
  )
}

export default App
