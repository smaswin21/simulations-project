// ---------------------------------------------------------------------------
// spriteGenerator.js – Procedural 16×16 pixel-art farmer sprites
// ---------------------------------------------------------------------------
// Each agent (1-18) gets a visually distinct farmer built from deterministic
// palette choices driven by their ID.  Two exported helpers let the animator
// obtain both idle-bob frames.
// ---------------------------------------------------------------------------

// ---- colour palettes (RGBA 0-255) -----------------------------------------

const SKIN_TONES = [
  [255, 219, 172, 255], // light peach
  [210, 161, 109, 255], // medium tan
  [182, 152, 100, 255], // olive
  [120, 75, 50, 255],   // dark brown
]

const HAIR_COLORS = [
  [101, 67, 33, 255],   // brown
  [30, 30, 30, 255],    // black
  [240, 210, 130, 255], // blonde
  [180, 50, 30, 255],   // red
  [170, 170, 170, 255], // gray
  [140, 60, 40, 255],   // auburn
]

const SHIRT_COLORS = [
  [59, 130, 246, 255],  // blue   #3B82F6
  [239, 68, 68, 255],   // red    #EF4444
  [34, 197, 94, 255],   // green  #22C55E
  [234, 179, 8, 255],   // yellow #EAB308
  [6, 182, 212, 255],   // cyan   #06B6D4
  [249, 115, 22, 255],  // orange #F97316
]

// Hat styles: 0 = straw (golden), 1 = bandana (red), 2 = none
const HAT_COLORS = [
  [218, 185, 110, 255], // straw / golden
  [200, 50, 50, 255],   // bandana / red
  null,                  // no hat
]

// Fixed colours
const PANTS_COLOR   = [92, 64, 51, 255]    // dark brown  #5C4033
const BOOTS_COLOR   = [42, 31, 20, 255]    // near-black  #2A1F14
const OUTLINE_COLOR = [26, 26, 46, 255]    // very dark   #1A1A2E
const EYE_COLOR     = [255, 255, 255, 255] // white       #FFFFFF
const STAFF_COLOR   = [139, 69, 19, 255]   // brown       #8B4513
const FORK_COLOR    = [107, 114, 128, 255] // gray        #6B7280

// ---- deterministic hash ---------------------------------------------------

/**
 * Simple integer hash (Robert Jenkins' 32-bit mix).
 * Deterministic: same input → same output, always.
 */
function mix(n) {
  n = ((n + 0x7ED55D16) + (n << 12)) & 0xFFFFFFFF
  n = ((n ^ 0xC761C23C) ^ (n >>> 19)) & 0xFFFFFFFF
  n = ((n + 0x165667B1) + (n << 5))  & 0xFFFFFFFF
  n = ((n + 0xD3A2646C) ^ (n << 9))  & 0xFFFFFFFF
  n = ((n + 0xFD7046C5) + (n << 3))  & 0xFFFFFFFF
  n = ((n ^ 0xB55A4F09) ^ (n >>> 16)) & 0xFFFFFFFF
  return n >>> 0 // ensure unsigned
}

/**
 * Derive palette indices from an integer agent ID.
 * Always returns the same result for the same id.
 */
export function hashSeed(id) {
  const n = Math.abs(Math.floor(id))
  // Use different mix rounds for each attribute to maximise spread
  const a = mix(n)
  const b = mix(n + 1000)
  const c = mix(n + 2000)
  const d = mix(n + 3000)
  const e = mix(n + 4000)
  return {
    skinIdx:  a % SKIN_TONES.length,
    hairIdx:  b % HAIR_COLORS.length,
    shirtIdx: c % SHIRT_COLORS.length,
    hatIdx:   d % HAT_COLORS.length,
    toolIdx:  e % 3, // 0 = staff, 1 = pitchfork, 2 = none
  }
}

// ---- 16×16 farmer template ------------------------------------------------
// Slot tags:
//   0 = transparent   1 = skin    2 = hair     3 = shirt
//   4 = hat           5 = pants   6 = boots    7 = outline
//   8 = tool          9 = eye
//
// The farmer faces forward, is ~8px wide, centred.  Tool on the right side.
// Rows  0-1  hat        Rows  2-3  hair
// Rows  4-5  face/eyes  Rows  6-9  shirt/arms/tool
// Rows 10-12 pants      Rows 13-15 boots

/* prettier-ignore */
const FARMER_TEMPLATE = [
  //0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
  [0, 0, 0, 0, 0, 7, 4, 4, 4, 4, 7, 0, 0, 0, 0, 0], // row 0  hat top
  [0, 0, 0, 0, 7, 4, 4, 4, 4, 4, 4, 7, 0, 0, 0, 0], // row 1  hat brim
  [0, 0, 0, 0, 7, 2, 2, 2, 2, 2, 2, 7, 0, 0, 0, 0], // row 2  hair top
  [0, 0, 0, 0, 7, 2, 2, 2, 2, 2, 2, 7, 0, 0, 0, 0], // row 3  hair sides
  [0, 0, 0, 0, 7, 1, 1, 1, 1, 1, 1, 7, 0, 0, 0, 0], // row 4  face top
  [0, 0, 0, 0, 7, 1, 9, 1, 1, 9, 1, 7, 0, 0, 0, 0], // row 5  eyes
  [0, 0, 0, 0, 0, 7, 1, 1, 1, 1, 7, 0, 0, 0, 0, 0], // row 6  chin
  [0, 0, 0, 0, 7, 3, 3, 3, 3, 3, 3, 7, 8, 0, 0, 0], // row 7  shirt top + tool
  [0, 0, 0, 7, 1, 3, 3, 3, 3, 3, 3, 1, 8, 0, 0, 0], // row 8  shirt + arms
  [0, 0, 0, 0, 7, 3, 3, 3, 3, 3, 3, 7, 8, 0, 0, 0], // row 9  shirt bottom + tool
  [0, 0, 0, 0, 7, 5, 5, 5, 5, 5, 5, 7, 8, 0, 0, 0], // row 10 pants top + tool
  [0, 0, 0, 0, 0, 7, 5, 5, 5, 5, 7, 0, 0, 0, 0, 0], // row 11 pants mid
  [0, 0, 0, 0, 0, 7, 5, 5, 5, 5, 7, 0, 0, 0, 0, 0], // row 12 pants bottom
  [0, 0, 0, 0, 0, 7, 6, 6, 6, 6, 7, 0, 0, 0, 0, 0], // row 13 boots top
  [0, 0, 0, 0, 0, 7, 6, 6, 6, 6, 7, 0, 0, 0, 0, 0], // row 14 boots mid
  [0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0], // row 15 soles
]

// ---- colour resolver ------------------------------------------------------

function resolveColor(slot, palette) {
  switch (slot) {
    case 0:  return null                   // transparent
    case 1:  return palette.skin
    case 2:  return palette.hair
    case 3:  return palette.shirt
    case 4:  return palette.hat            // may be null → transparent
    case 5:  return PANTS_COLOR
    case 6:  return BOOTS_COLOR
    case 7:  return OUTLINE_COLOR
    case 8:  return palette.tool           // may be null → transparent
    case 9:  return EYE_COLOR
    default: return null
  }
}

// ---- sprite generation ----------------------------------------------------

function buildPalette(seed) {
  const h = hashSeed(seed)
  return {
    skin:  SKIN_TONES[h.skinIdx],
    hair:  HAIR_COLORS[h.hairIdx],
    shirt: SHIRT_COLORS[h.shirtIdx],
    hat:   HAT_COLORS[h.hatIdx],          // null when hatIdx === 2
    tool:  h.toolIdx === 0 ? STAFF_COLOR
         : h.toolIdx === 1 ? FORK_COLOR
         : null,                           // 2 = no tool
  }
}

function rgba(c) {
  return `rgba(${c[0]},${c[1]},${c[2]},${c[3] / 255})`
}

function renderTemplate(ctx, palette, yOffset) {
  ctx.clearRect(0, 0, 16, 16)

  for (let row = 0; row < 16; row++) {
    const destY = row + yOffset
    if (destY < 0 || destY >= 16) continue

    for (let col = 0; col < 16; col++) {
      const slot = FARMER_TEMPLATE[row][col]
      if (slot === 0) continue

      const color = resolveColor(slot, palette)
      if (!color) continue // null = transparent (no hat / no tool)

      ctx.fillStyle = rgba(color)
      ctx.fillRect(col, destY, 1, 1)
    }
  }
}

/**
 * Generate a 16×16 canvas sprite for the given seed (agent ID).
 * @param  {number} seed  Agent ID (1-18 typically)
 * @return {{ canvas: HTMLCanvasElement, palette: object }}
 */
export function generateSprite(seed) {
  const palette = buildPalette(seed)
  const canvas  = document.createElement('canvas')
  canvas.width  = 16
  canvas.height = 16
  const ctx = canvas.getContext('2d')
  renderTemplate(ctx, palette, 0)
  return { canvas, palette }
}

/**
 * Generate a single idle-bob frame.
 *   frameIdx 0 → normal position
 *   frameIdx 1 → shifted UP 1 px (row 0 lost, row 15 transparent)
 * @param  {number} seed      Agent ID
 * @param  {number} frameIdx  0 or 1
 * @return {HTMLCanvasElement}
 */
export function generateSpriteFrame(seed, frameIdx) {
  const palette = buildPalette(seed)
  const canvas  = document.createElement('canvas')
  canvas.width  = 16
  canvas.height = 16
  const ctx = canvas.getContext('2d')
  const yOffset = frameIdx === 1 ? -1 : 0
  renderTemplate(ctx, palette, yOffset)
  return canvas
}
