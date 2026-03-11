import { useCallback, useEffect, useRef } from 'react'
import { useSim } from '../context/SimContext.jsx'
import { runSimulation } from '../api/simulation.js'

export function useSimulation() {
  const {
    activeScenario,
    advanceRound,
    setRunning,
    isLoading,
    setLoading,
    setError,
    setSimulationData,
  } = useSim()
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

  const togglePlayback = useCallback(async () => {
    if (!activeScenario || isLoading) return

    const hasRealData = Array.isArray(activeScenario._rounds) && activeScenario._rounds.length > 0
    const needsFetch = activeScenario.round === 0 && !hasRealData

    if (needsFetch) {
      // First play — fetch real data from backend
      setLoading(true)
      try {
        const { params } = activeScenario
        const scenarioId = activeScenario.id
        const data = await runSimulation({
          memoryOn: params.memoryOn,
          rounds: params.rounds,
          seed: params.seed ?? null,
        })
        if (scenarioId !== activeScenario.id) return  // stale: user switched scenario
        setSimulationData(data)
        setRunning(true)
      } catch (err) {
        setError(err.message || 'Simulation failed')
      } finally {
        setLoading(false)
      }
      return
    }

    // Already have data — pause or resume
    if (activeScenario.round >= activeScenario.maxRounds) return
    setRunning(!activeScenario.isRunning)
  }, [activeScenario, isLoading, setLoading, setError, setSimulationData, setRunning, advanceRound])

  return {
    isRunning: activeScenario?.isRunning || false,
    currentRound: activeScenario?.round || 0,
    maxRounds: activeScenario?.maxRounds || 0,
    isLoading,
    togglePlayback,
  }
}

export default useSimulation
