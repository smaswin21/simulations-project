import { createContext, useContext, useReducer, useCallback } from 'react'
import { scenarios as mockScenarios } from '../data/mockData.js'

const SimContext = createContext(null)

const initialState = {
  scenarios: mockScenarios,
  activeScenarioId: mockScenarios[0].id,
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
          return { ...s, round: nextRound, isRunning }
        }),
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

  const activeScenario = state.scenarios.find(s => s.id === state.activeScenarioId)

  const value = {
    scenarios: state.scenarios,
    activeScenario,
    activeScenarioId: state.activeScenarioId,
    setScenario,
    updateParams,
    setRunning,
    advanceRound,
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
