import { ACTION_COLOR } from './helpers.js'

/**
 * Map one round payload from the FastAPI backend to the internal UI shape.
 *
 * FastAPI round payload shape:
 * {
 *   round: number,
 *   max_rounds: number,
 *   world_state: { round, locations, inventories, depot_stock, event_message? },
 *   agents: [{ id, name, location, gridPos, status, grazingUnits, action }],
 *   metrics_so_far: { gini[], cooperation_rate[], resource_stock[] }
 * }
 *
 * @param {Object} apiRound
 * @returns {Object} Normalized round data for UI components
 */
export function adaptRound(apiRound) {
  const worldState = apiRound.world_state ?? {}
  const metrics = apiRound.metrics_so_far ?? {}
  const resourceStockArr = metrics.resource_stock ?? []

  // Latest depot stock: prefer world_state.depot_stock, fall back to last resource_stock entry
  const depotStock =
    worldState.depot_stock != null
      ? worldState.depot_stock
      : resourceStockArr.length > 0
      ? resourceStockArr[resourceStockArr.length - 1]
      : 120

  const agents = (apiRound.agents ?? []).map((a) => ({
    name:       a.name,
    locationId: a.location,                        // already kebab-case from backend
    gridPos:    a.gridPos ?? [0, 0],
    status:     a.status ?? 'strained',
    resources:  a.grazingUnits ?? 0,              // renamed from grazingUnits
    action:     (a.action ?? 'wait').toLowerCase(),
  }))

  return {
    round:        apiRound.round ?? 0,
    maxRounds:    apiRound.max_rounds ?? 10,
    depotStock,
    depotMax:     120,                            // matches config.yaml initial_supply
    eventMessage: worldState.event_message ?? null,
    agents,
    metricHistory: {
      gini:             metrics.gini ?? [],
      cooperationRate:  metrics.cooperation_rate ?? [],
      resourceStock:    resourceStockArr,
    },
  }
}

/**
 * Build action log entries for the ActivityFeed from a single adapted round.
 *
 * @param {Object} adaptedRound - Result of adaptRound()
 * @returns {Array<{ agent, locationId, action, detail, resources, color }>}
 */
export function buildActionLog(adaptedRound) {
  if (!adaptedRound) return []

  return adaptedRound.agents.map((a) => {
    let detail = ''
    const locName = a.locationId
      .split('-')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')

    switch (a.action) {
      case 'graze':
        detail = `Grazed at ${locName}`
        break
      case 'share':
        detail = `Shared resources at ${locName}`
        break
      case 'speak':
        detail = `Spoke at ${locName}`
        break
      case 'move':
        detail = `Moved to ${locName}`
        break
      default:
        detail = a.action.charAt(0).toUpperCase() + a.action.slice(1)
    }

    return {
      agent:      a.name,
      locationId: a.locationId,
      action:     a.action,
      detail,
      resources:  a.resources,
      color:      ACTION_COLOR[a.action] ?? '#94a3b8',
    }
  })
}
