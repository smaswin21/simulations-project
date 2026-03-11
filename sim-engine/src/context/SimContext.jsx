import { createContext, useContext, useReducer, useCallback } from 'react'
import { scenarios as mockScenarios } from '../data/mockData.js'

const SimContext = createContext(null)

const initialState = {
  scenarios: mockScenarios,
  activeScenarioId: mockScenarios[0].id,
  isLoading: false,
  error: null,
}

function simReducer(state, action) {
  switch (action.type) {
    case 'SET_SCENARIO':
      return { ...state, activeScenarioId: action.payload }

    case 'UPDATE_PARAMS': {
      return {
        ...state,
        scenarios: state.scenarios.map(s =>
          s.id === state.activeScenarioId
            ? { ...s, params: { ...s.params, ...action.payload } }
            : s
        ),
      }
    }

    case 'SET_RUNNING': {
      return {
        ...state,
        scenarios: state.scenarios.map(s =>
          s.id === state.activeScenarioId
            ? { ...s, isRunning: action.payload }
            : s
        ),
      }
    }

    case 'ADVANCE_ROUND': {
      return {
        ...state,
        scenarios: state.scenarios.map(s => {
          if (s.id !== state.activeScenarioId) return s
          const nextRound = Math.min(s.round + 1, s.maxRounds)
          const isRunning = nextRound < s.maxRounds ? s.isRunning : false
          const roundData = s._rounds?.[nextRound - 1]
          return {
            ...s,
            round: nextRound,
            isRunning,
            ...(roundData ? {
              agents: roundData.agents ?? s.agents,
              stats: roundData.stats ?? s.stats,
            } : {}),
          }
        }),
      }
    }

    case 'SET_LOADING':
      return { ...state, isLoading: action.payload, ...(action.payload ? { error: null } : {}) }

    case 'SET_ERROR':
      return { ...state, isLoading: false, error: action.payload }

    case 'SET_SIMULATION_DATA': {
      const { rounds, summary } = action.payload
      if (!rounds?.length) {
        return { ...state, isLoading: false, error: 'Simulation returned no rounds.' }
      }
      const resourceExtraction = rounds.map(r => r.metrics?.resourceExtraction ?? 0)
      const statusOverTime = rounds.map(r => ({
        round: r.round,
        ...(r.metrics?.statusOverTime ?? { thriving: 0, strained: 0, struggling: 0, depleted: 0 }),
      }))
      const resourceStock = rounds.map(r => r.metrics?.resourceStock ?? 0)
      const giniCoefficient = rounds.map(r => r.metrics?.giniCoefficient ?? 0)
      const lastRound = rounds[rounds.length - 1] ?? {}
      return {
        ...state,
        isLoading: false,
        error: null,
        scenarios: state.scenarios.map(s =>
          s.id === state.activeScenarioId
            ? {
                ...s,
                round: 0,
                maxRounds: rounds.length,
                isRunning: false,
                agents: lastRound.agents ?? s.agents,
                metrics: { resourceExtraction, statusOverTime, resourceStock, giniCoefficient },
                stats: lastRound.stats ?? s.stats,
                summary,
                _rounds: rounds,
              }
            : s
        ),
      }
    }

    default:
      return state
  }
}

export function SimProvider({ children }) {
  const [state, dispatch] = useReducer(simReducer, initialState)

  const setScenario = useCallback((id) => {
    dispatch({ type: 'SET_SCENARIO', payload: id })
  }, [])

  const updateParams = useCallback((params) => {
    dispatch({ type: 'UPDATE_PARAMS', payload: params })
  }, [])

  const setRunning = useCallback((running) => {
    dispatch({ type: 'SET_RUNNING', payload: running })
  }, [])

  const advanceRound = useCallback(() => {
    dispatch({ type: 'ADVANCE_ROUND' })
  }, [])

  const setLoading = useCallback((loading) => dispatch({ type: 'SET_LOADING', payload: loading }), [])
  const setError = useCallback((msg) => dispatch({ type: 'SET_ERROR', payload: msg }), [])
  const setSimulationData = useCallback((data) => dispatch({ type: 'SET_SIMULATION_DATA', payload: data }), [])

  const activeScenario = state.scenarios.find(s => s.id === state.activeScenarioId)

  const value = {
    scenarios: state.scenarios,
    activeScenario,
    activeScenarioId: state.activeScenarioId,
    setScenario,
    updateParams,
    setRunning,
    advanceRound,
    isLoading: state.isLoading,
    error: state.error,
    setLoading,
    setError,
    setSimulationData,
  }

  return <SimContext.Provider value={value}>{children}</SimContext.Provider>
}

export function useSim() {
  const context = useContext(SimContext)
  if (!context) {
    throw new Error('useSim must be used within a SimProvider')
  }
  return context
}

export default SimContext
