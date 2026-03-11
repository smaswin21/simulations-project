// ---------------------------------------------------------------------------
// spriteEffects.js – Action effect overlays for 16×16 farmer sprites
// ---------------------------------------------------------------------------
// Pure functions that draw small visual effects ON TOP of an existing sprite.
// They only write pixels onto the provided canvas context — no canvas creation.
// ---------------------------------------------------------------------------

// ---- effect colours -------------------------------------------------------

const GREEN_SPARKLE = '#22C55E'
const YELLOW_GLOW   = '#EAB308'
const WHITE_BUBBLE  = '#FFFFFF'

// ---- helper ---------------------------------------------------------------

/** Draw a single pixel at (x, y) in the given colour. */
function px(ctx, x, y, color) {
  ctx.fillStyle = color
  ctx.fillRect(x, y, 1, 1)
}

// ---- graze effect ---------------------------------------------------------
// Green sparkle dots above the head area. 2 frames.

function drawGrazeEffect(ctx, frameIdx) {
  if (frameIdx === 0) {
    px(ctx, 5, 1, GREEN_SPARKLE)
    px(ctx, 8, 0, GREEN_SPARKLE)
    px(ctx, 10, 2, GREEN_SPARKLE)
  } else if (frameIdx === 1) {
    px(ctx, 6, 0, GREEN_SPARKLE)
    px(ctx, 9, 1, GREEN_SPARKLE)
    px(ctx, 7, 2, GREEN_SPARKLE)
  }
}

// ---- share effect ---------------------------------------------------------
// Yellow expanding rectangle border around the shirt area. 2 frames.
// Drawn as individual pixels to avoid sub-pixel issues at 1px scale.

function drawShareRect(ctx, x0, y0, x1, y1) {
  // top edge
  for (let x = x0; x <= x1; x++) px(ctx, x, y0, YELLOW_GLOW)
  // bottom edge
  for (let x = x0; x <= x1; x++) px(ctx, x, y1, YELLOW_GLOW)
  // left edge (exclude corners already drawn)
  for (let y = y0 + 1; y < y1; y++) px(ctx, x0, y, YELLOW_GLOW)
  // right edge (exclude corners already drawn)
  for (let y = y0 + 1; y < y1; y++) px(ctx, x1, y, YELLOW_GLOW)
}

function drawShareEffect(ctx, frameIdx) {
  if (frameIdx === 0) {
    drawShareRect(ctx, 4, 6, 11, 9)
  } else if (frameIdx === 1) {
    drawShareRect(ctx, 3, 5, 12, 10)
  }
}

// ---- speak effect ---------------------------------------------------------
// Tiny speech bubble to the right of the head. 3 frames.

function drawSpeakEffect(ctx, frameIdx) {
  if (frameIdx === 0 || frameIdx === 1) {
    // 3×2 white filled rectangle at (12, 3)
    for (let dx = 0; dx < 3; dx++) {
      for (let dy = 0; dy < 2; dy++) {
        px(ctx, 12 + dx, 3 + dy, WHITE_BUBBLE)
      }
    }
    // 1px connector pointing toward the face
    px(ctx, 11, 4, WHITE_BUBBLE)
  }
  // frameIdx === 2 → nothing drawn (bubble gone)
}

// ---- dispatcher -----------------------------------------------------------

/**
 * Draw an action effect overlay onto a 16×16 sprite context.
 *
 * @param  {CanvasRenderingContext2D} ctx       Target context (already has sprite)
 * @param  {string}                  action    'graze' | 'share' | 'speak'
 * @param  {number}                  frameIdx  Current animation frame index
 * @return {{ maxFrames: number }}              Total frames for this effect
 */
export function drawEffect(ctx, action, frameIdx) {
  if (action === 'graze') {
    drawGrazeEffect(ctx, frameIdx)
    return { maxFrames: 2 }
  }
  if (action === 'share') {
    drawShareEffect(ctx, frameIdx)
    return { maxFrames: 2 }
  }
  if (action === 'speak') {
    drawSpeakEffect(ctx, frameIdx)
    return { maxFrames: 3 }
  }
  return { maxFrames: 0 }
}
