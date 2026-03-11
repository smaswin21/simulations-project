const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
