// Location config for Tragedy of the Commons (maps API location IDs → display data)
export const LOCATION_CONFIG = {
  'village-square': {
    id: 'village-square',
    name: 'Village Square',
    icon: '🏛',
    color: '#6366f1',
    desc: 'Community gathering point',
    x: 22,   // % position on the world map
    y: 28,
  },
  'common-pasture': {
    id: 'common-pasture',
    name: 'Common Pasture',
    icon: '🌿',
    color: '#22c55e',
    desc: 'Shared grazing resource',
    x: 72,
    y: 25,
  },
  'notice-board': {
    id: 'notice-board',
    name: 'Notice Board',
    icon: '📋',
    color: '#f59e0b',
    desc: 'Public announcements',
    x: 47,
    y: 70,
  },
}

// Action type → highlight color (supports both lowercase and uppercase)
export const ACTION_COLOR = {
  speak:  '#60a5fa',
  move:   '#a78bfa',
  graze:  '#f59e0b',
  share:  '#34d399',
  post:   '#fb923c',
  wait:   '#94a3b8',
  SPEAK:  '#60a5fa',
  MOVE:   '#a78bfa',
  GRAZE:  '#f59e0b',
  SHARE:  '#34d399',
  POST:   '#fb923c',
  WAIT:   '#94a3b8',
}

// Stable colors for agents (indexed by order)
export const AGENT_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f97316', '#a855f7',
  '#14b8a6', '#f59e0b', '#ec4899', '#6366f1', '#84cc16',
  '#06b6d4', '#e11d48', '#7c3aed', '#10b981', '#f43f5e',
  '#0ea5e9', '#d97706', '#65a30d',
]

// Small deterministic offset so agents at the same location don't overlap
export function jitter(base, range, seed) {
  return base + ((seed * 7919) % (range * 2)) - range
}

// Convert 0–1 trait value to a human label
export function traitLabel(val) {
  return val >= 0.7 ? 'High' : val <= 0.3 ? 'Low' : 'Mid'
}

// Convert a location string from the API to a display label
// Handles both kebab-case IDs ("village-square") and sentence case ("Village Square")
export function locationDisplayName(locationId) {
  const cfg = LOCATION_CONFIG[locationId]
  if (cfg) return cfg.name
  // Fallback: title-case the ID
  return locationId
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}
