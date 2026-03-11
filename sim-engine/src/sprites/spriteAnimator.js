// ---------------------------------------------------------------------------
// spriteAnimator.js – React hook for animating a single agent sprite
// ---------------------------------------------------------------------------
// Manages the requestAnimationFrame loop that drives idle-bob and action
// effect overlays on a 16×16 canvas.
// ---------------------------------------------------------------------------

import { useEffect, useRef } from 'react'
import { generateSpriteFrame } from './spriteGenerator.js'
import { drawEffect } from './spriteEffects.js'

/**
 * Custom hook that drives the sprite animation loop for one agent.
 *
 * @param {React.RefObject<HTMLCanvasElement>} canvasRef  Ref to a 16×16 canvas
 * @param {number}  seed    Agent ID used to generate the sprite
 * @param {string|null} action  Current action ('graze','share','speak','move', or null)
 * @param {string}  status  Agent status ('thriving','strained','struggling','depleted')
 */
export function useSpriteAnimation(canvasRef, seed, action, status) {
  // Pre-generated idle frames (array of two HTMLCanvasElement)
  const idleFramesRef = useRef(null)

  // Mutable animation state kept in a ref to avoid re-renders
  const animState = useRef({
    currentFrame: 0,
    lastIdleSwap: 0,
    effectFrame: 0,
    lastEffectSwap: 0,
  })

  // Track the rAF handle so we can cancel it
  const rafRef = useRef(null)

  // --- Pre-generate idle frames when seed changes --------------------------
  useEffect(() => {
    idleFramesRef.current = [
      generateSpriteFrame(seed, 0),
      generateSpriteFrame(seed, 1),
    ]
  }, [seed])

  // --- Reset effect frame when action changes ------------------------------
  useEffect(() => {
    animState.current.effectFrame = 0
    animState.current.lastEffectSwap = performance.now()
  }, [action])

  // --- Main animation loop -------------------------------------------------
  useEffect(() => {
    // If depleted, draw frame 0 at half opacity once and bail out
    if (status === 'depleted') {
      const canvas = canvasRef.current
      if (!canvas || !idleFramesRef.current) return

      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, 16, 16)
      ctx.globalAlpha = 0.5
      ctx.drawImage(idleFramesRef.current[0], 0, 0)
      ctx.globalAlpha = 1.0

      // No rAF loop — return a no-op cleanup
      return
    }

    // Initialise timestamps so the first tick doesn't immediately swap
    const now = performance.now()
    animState.current.lastIdleSwap = now
    animState.current.lastEffectSwap = now

    function tick(timestamp) {
      const state = animState.current
      const canvas = canvasRef.current
      const frames = idleFramesRef.current

      // Guard: canvas or frames not ready yet
      if (!canvas || !frames) {
        rafRef.current = requestAnimationFrame(tick)
        return
      }

      // --- idle bob (toggle every 500 ms) ---
      if (timestamp - state.lastIdleSwap >= 500) {
        state.currentFrame = state.currentFrame === 0 ? 1 : 0
        state.lastIdleSwap = timestamp
      }

      // --- effect frame (advance every 200 ms) ---
      if (timestamp - state.lastEffectSwap >= 200) {
        state.effectFrame += 1
        state.lastEffectSwap = timestamp
        // maxFrames is checked below after we know the action
      }

      const ctx = canvas.getContext('2d')

      // Clear canvas
      ctx.clearRect(0, 0, 16, 16)

      // Draw current idle frame
      ctx.drawImage(frames[state.currentFrame], 0, 0)

      // Draw action effect overlay (skip 'move' — that's handled by position)
      if (action && action !== 'move') {
        const { maxFrames } = drawEffect(ctx, action, state.effectFrame)
        // Wrap effect frame if it exceeded maxFrames
        if (maxFrames > 0 && state.effectFrame >= maxFrames) {
          state.effectFrame = 0
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)

    // Cleanup: cancel animation frame on unmount or dependency change
    return () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [canvasRef, status, action])
}
