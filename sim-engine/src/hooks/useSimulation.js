import { useEffect, useRef } from 'react'
import { useSim } from '../context/SimContext.jsx'

export function useSimulation() {
  const { activeScenario, advanceRound, setRunning } = useSim()
  const intervalRef = useRef(null)

  const speedMs = {
    1: 2000,
    2: 1000,
    3: 500,
  }

  useEffect(() => {
    if (activeScenario?.isRunning) {
      const ms = speedMs[activeScenario.params.speed] || 2000
      intervalRef.current = setInterval(() => {
        advanceRound()
      }, ms)
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [activeScenario?.isRunning, activeScenario?.params.speed, advanceRound])

  const togglePlayback = () => {
    if (activeScenario) {
      if (activeScenario.round >= activeScenario.maxRounds) {
        return // Already at max round
      }
      setRunning(!activeScenario.isRunning)
    }
  }

  return {
    isRunning: activeScenario?.isRunning || false,
    currentRound: activeScenario?.round || 0,
    maxRounds: activeScenario?.maxRounds || 0,
    togglePlayback,
  }
}

export default useSimulation
