const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * List recent simulation runs stored in MongoDB.
 *
 * @param {number} limit - max number of runs to return (default 20)
 * @returns {Promise<Array<{ run_id, timestamp, status, rounds_count, final_summary }>>}
 */
export async function listRuns(limit = 20) {
  const res = await fetch(`${BASE}/simulation/runs?limit=${limit}`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Replay a stored simulation run as an SSE stream.
 * Same contract as startStream() — returns { runId, eventSource }.
 * No async step needed; the EventSource connects immediately.
 *
 * @param {string} simulationId - MongoDB _id string from listRuns()
 * @returns {{ runId: string, eventSource: EventSource }}
 */
export function startReplay(simulationId) {
  const eventSource = new EventSource(`${BASE}/simulation/replay/${simulationId}`)
  return { runId: simulationId, eventSource }
}

/**
 * Start a streaming simulation run.
 *
 * Step 1: POST /simulation/run/stream → { run_id }
 * Step 2: Return an EventSource connected to GET /simulation/stream/{run_id}
 *
 * @param {Object} params
 * @param {boolean} params.memoryOn
 * @param {number}  params.rounds
 * @param {number|null} params.seed
 * @returns {Promise<{ runId: string, eventSource: EventSource }>}
 * @throws {Error} if the POST fails
 */
export async function startStream({ memoryOn = true, rounds = 10, seed = null }) {
  const res = await fetch(`${BASE}/simulation/run/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      memoryOn: !!memoryOn,
      rounds: Number(rounds) || 10,
      seed: seed != null && seed !== '' ? Number(seed) : null,
      scenario: 'simulations/tragedy_of_commons',
    }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }

  const { run_id: runId } = await res.json()
  const eventSource = new EventSource(`${BASE}/simulation/stream/${runId}`)
  return { runId, eventSource }
}
