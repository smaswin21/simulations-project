import { useState, useRef, useCallback, useEffect } from 'react'
import { startStream, startReplay } from '../api/simulation.js'
import { adaptRound, buildActionLog } from '../utils/adapter.js'

const SPEED_MS = { '1x': 3000, '2x': 1500, '4x': 750 }

/**
 * useSimulation — owns all simulation state and SSE lifecycle.
 *
 * Status transitions:
 *   idle → streaming → done (normal flow after streaming completes)
 *   idle → streaming → error (on network failure)
 *   done/paused → playing (user presses play)
 *   playing → paused (user presses pause)
 *   * → idle (user runs a new simulation)
 */
export function useSimulation() {
  // Accumulated adapted rounds (one per SSE event)
  const [rounds, setRounds] = useState([])
  // Index into rounds[] that the UI is currently showing
  const [currentIndex, setCurrentIndex] = useState(0)
  // 'idle' | 'streaming' | 'playing' | 'paused' | 'done' | 'error'
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  // Run parameters (controlled by TopBar)
  const [params, setParams] = useState({ memoryOn: true, rounds: 10, seed: '' })
  // Playback speed
  const [speed, setSpeed] = useState('2x')

  const eventSourceRef = useRef(null)
  const playTimerRef = useRef(null)

  // ── Cleanup helpers ──────────────────────────────────────────────────
  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  const clearPlayTimer = useCallback(() => {
    if (playTimerRef.current) {
      clearInterval(playTimerRef.current)
      playTimerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeEventSource()
      clearPlayTimer()
    }
  }, [closeEventSource, clearPlayTimer])

  // ── Start a new simulation run ───────────────────────────────────────
  const runSimulation = useCallback(async () => {
    closeEventSource()
    clearPlayTimer()
    setRounds([])
    setCurrentIndex(0)
    setSummary(null)
    setError(null)
    setStatus('streaming')

    try {
      const { eventSource } = await startStream({
        memoryOn: params.memoryOn,
        rounds: Number(params.rounds) || 10,
        seed: params.seed !== '' ? Number(params.seed) : null,
      })
      eventSourceRef.current = eventSource

      eventSource.onmessage = (evt) => {
        let data
        try {
          data = JSON.parse(evt.data)
        } catch {
          return
        }

        if (data.status === 'complete') {
          setSummary(data.summary)
          setStatus('done')
          closeEventSource()
          return
        }

        if (data.status === 'error') {
          setError(data.error || 'Unknown error from server')
          setStatus('error')
          closeEventSource()
          return
        }

        // Normal round payload — adapt and append
        const adapted = adaptRound(data)
        setRounds((prev) => {
          const next = [...prev, adapted]
          // Auto-advance to show the latest round while streaming
          setCurrentIndex(next.length - 1)
          return next
        })
      }

      eventSource.onerror = () => {
        setError('SSE connection lost')
        setStatus('error')
        closeEventSource()
      }
    } catch (err) {
      setError(err.message || 'Failed to start simulation')
      setStatus('error')
    }
  }, [params, closeEventSource, clearPlayTimer])

  // ── Replay a stored run from MongoDB ────────────────────────────────
  const loadRun = useCallback((simulationId) => {
    closeEventSource()
    clearPlayTimer()
    setRounds([])
    setCurrentIndex(0)
    setSummary(null)
    setError(null)
    setStatus('streaming')

    const { eventSource } = startReplay(simulationId)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (evt) => {
      let data
      try {
        data = JSON.parse(evt.data)
      } catch {
        return
      }

      if (data.status === 'complete') {
        setSummary(data.summary)
        setStatus('done')
        closeEventSource()
        return
      }

      if (data.status === 'error') {
        setError(data.error || 'Unknown error from server')
        setStatus('error')
        closeEventSource()
        return
      }

      // Normal round payload — adapt and append
      const adapted = adaptRound(data)
      setRounds((prev) => {
        const next = [...prev, adapted]
        setCurrentIndex(next.length - 1)
        return next
      })
    }

    eventSource.onerror = () => {
      setError('SSE connection lost')
      setStatus('error')
      closeEventSource()
    }
  }, [closeEventSource, clearPlayTimer])

  // ── Playback controls ────────────────────────────────────────────────
  const play = useCallback(() => {
    if (rounds.length === 0) return
    clearPlayTimer()
    setStatus('playing')
    playTimerRef.current = setInterval(() => {
      setCurrentIndex((i) => {
        if (i >= rounds.length - 1) {
          clearPlayTimer()
          setStatus('done')
          return i
        }
        return i + 1
      })
    }, SPEED_MS[speed] ?? 1500)
  }, [rounds.length, speed, clearPlayTimer])

  const pause = useCallback(() => {
    clearPlayTimer()
    setStatus('paused')
  }, [clearPlayTimer])

  const stepBack = useCallback(() => {
    clearPlayTimer()
    setStatus('paused')
    setCurrentIndex((i) => Math.max(0, i - 1))
  }, [clearPlayTimer])

  const stepForward = useCallback(() => {
    clearPlayTimer()
    setStatus('paused')
    setCurrentIndex((i) => Math.min(rounds.length - 1, i + 1))
  }, [rounds.length, clearPlayTimer])

  const seekTo = useCallback(
    (index) => {
      clearPlayTimer()
      setStatus('paused')
      setCurrentIndex(Math.max(0, Math.min(index, rounds.length - 1)))
    },
    [rounds.length, clearPlayTimer]
  )

  // ── Derived values ───────────────────────────────────────────────────
  const currentRound = rounds[currentIndex] ?? null
  const actionLog = currentRound ? buildActionLog(currentRound) : []

  return {
    // State
    rounds,
    currentRound,
    currentIndex,
    actionLog,
    status,
    error,
    summary,
    params,
    speed,
    // Actions
    setParams,
    setSpeed,
    runSimulation,
    loadRun,
    play,
    pause,
    stepBack,
    stepForward,
    seekTo,
  }
}
