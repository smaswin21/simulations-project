import { useState } from 'react'
import { useSimulation } from '../hooks/useSimulation.js'
import TopBar from './TopBar.jsx'
import EventBanner from './EventBanner.jsx'
import PlaybackControls from './PlaybackControls.jsx'
import ActivityFeed from './ActivityFeed.jsx'
import WorldView from './views/WorldView.jsx'
import MindView from './views/MindView.jsx'
import FabricView from './views/FabricView.jsx'

export default function SimulationTheater() {
  const sim = useSimulation()
  const [viewMode, setViewMode] = useState('world')
  const [focusedAgent, setFocusedAgent] = useState(null)
  const [showTrails, setShowTrails] = useState(true)

  const { currentRound, rounds, currentIndex } = sim

  const prevRound = currentIndex > 0 ? rounds[currentIndex - 1] : null

  function handleAgentClick(name) {
    setFocusedAgent((prev) => (prev === name ? null : name))
  }

  function handleAgentNodeClick(name) {
    setFocusedAgent(name)
    setViewMode('mind')
  }

  function handleTogglePlay() {
    if (sim.status === 'playing') sim.pause()
    else sim.play()
  }

  return (
    <div style={{ minHeight: '100vh', fontFamily: 'var(--font-ui)' }}>
      <TopBar
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        depotStock={currentRound?.depotStock ?? null}
        depotMax={currentRound?.depotMax ?? 120}
        round={currentRound?.round ?? null}
        maxRounds={currentRound?.maxRounds ?? null}
        status={sim.status}
        params={sim.params}
        onParamsChange={sim.setParams}
        onRun={sim.runSimulation}
      />

      <div style={{
        maxWidth: 1280, margin: '0 auto', padding: 16,
        display: 'flex', gap: 16,
        height: 'calc(100vh - 56px)',
      }}>
        {/* Left: main viewport */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <EventBanner message={currentRound?.eventMessage ?? null} />

          {/* View area */}
          <div style={{
            flex: 1, borderRadius: 16, border: '1px solid rgba(51,65,85,0.6)',
            background: 'rgba(2,6,23,0.4)', backdropFilter: 'blur(8px)',
            overflow: 'hidden', position: 'relative',
          }}>
            {viewMode === 'world' && (
              <WorldView
                adaptedRound={currentRound}
                prevAdaptedRound={prevRound}
                focusedAgent={focusedAgent}
                showTrails={showTrails}
                onAgentClick={handleAgentClick}
              />
            )}
            {viewMode === 'mind' && (
              <MindView
                focusedAgent={focusedAgent}
                onAgentClick={handleAgentClick}
                rounds={rounds}
                currentIndex={currentIndex}
              />
            )}
            {viewMode === 'fabric' && (
              <FabricView
                rounds={rounds}
                currentIndex={currentIndex}
                focusedAgent={focusedAgent}
                onAgentNodeClick={handleAgentNodeClick}
              />
            )}
          </div>

          <PlaybackControls
            currentIndex={currentIndex}
            totalRounds={rounds.length}
            status={sim.status}
            speed={sim.speed}
            onStepBack={sim.stepBack}
            onTogglePlay={handleTogglePlay}
            onStepForward={sim.stepForward}
            onSeekTo={sim.seekTo}
            onSpeedChange={sim.setSpeed}
          />
        </div>

        {/* Right: activity feed */}
        <ActivityFeed
          round={currentRound?.round ?? null}
          actionLog={sim.actionLog}
          focusedAgent={focusedAgent}
          onAgentClick={handleAgentClick}
        />
      </div>
    </div>
  )
}
