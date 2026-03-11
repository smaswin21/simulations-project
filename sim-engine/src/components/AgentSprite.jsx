import { useState, useRef } from 'react'
import { useSpriteAnimation } from '../sprites/spriteAnimator.js'

function AgentSprite({ agent }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const canvasRef = useRef(null)

  useSpriteAnimation(canvasRef, agent.id, agent.action, agent.status)

  return (
    <div
      className={`agent-sprite agent-sprite--${agent.status}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <canvas
        ref={canvasRef}
        width={16}
        height={16}
        style={{ width: '32px', height: '32px', imageRendering: 'pixelated' }}
      />
      {showTooltip && (
        <div className="retro-tooltip" style={{ bottom: '110%', left: '50%', transform: 'translateX(-50%)' }}>
          <div>{agent.name}</div>
          <div style={{ color: 'var(--nes-cyan)', marginTop: '2px' }}>
            {agent.status.toUpperCase()}
          </div>
          <div style={{ color: 'var(--nes-green)', marginTop: '2px' }}>
            GRAZE: {agent.grazingUnits}
          </div>
        </div>
      )}
    </div>
  )
}

export default AgentSprite
