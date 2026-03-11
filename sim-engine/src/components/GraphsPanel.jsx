import { useSim } from '../context/SimContext.jsx'
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

const CHART_COLORS = {
  thriving: '#22C55E',
  strained: '#EAB308',
  struggling: '#EF4444',
  depleted: '#6B7280',
  resource: '#06B6D4',
  gini: '#D946EF',
}

const tooltipStyle = {
  backgroundColor: '#0F0F23',
  border: '2px solid #4A4A6A',
  fontFamily: "'Press Start 2P', monospace",
  fontSize: '6px',
  color: '#F5F5F5',
}

function GraphsPanel() {
  const { activeScenario } = useSim()

  if (!activeScenario) return null

  const { metrics, round } = activeScenario
  const statusData = metrics.statusOverTime.slice(0, round)
  const giniData = metrics.giniCoefficient.slice(0, round).map((val, i) => ({
    round: i + 1,
    gini: val,
  }))

  return (
    <div className="graphs-panel retro-panel">
      <div className="retro-label">Analytics</div>
      <div className="retro-divider" />

      {/* Resource Status Over Time */}
      <div className="graphs-panel__chart">
        <div className="graphs-panel__chart-title">Resource Status</div>
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={statusData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
            <XAxis
              dataKey="round"
              tick={{ fontSize: 6, fontFamily: "'Press Start 2P'", fill: '#6B7280' }}
              stroke="#4A4A6A"
            />
            <YAxis
              tick={{ fontSize: 6, fontFamily: "'Press Start 2P'", fill: '#6B7280' }}
              stroke="#4A4A6A"
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="stepAfter" dataKey="thriving" stackId="1" fill={CHART_COLORS.thriving} stroke={CHART_COLORS.thriving} fillOpacity={0.6} />
            <Area type="stepAfter" dataKey="strained" stackId="1" fill={CHART_COLORS.strained} stroke={CHART_COLORS.strained} fillOpacity={0.6} />
            <Area type="stepAfter" dataKey="struggling" stackId="1" fill={CHART_COLORS.struggling} stroke={CHART_COLORS.struggling} fillOpacity={0.6} />
            <Area type="stepAfter" dataKey="depleted" stackId="1" fill={CHART_COLORS.depleted} stroke={CHART_COLORS.depleted} fillOpacity={0.6} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Gini Coefficient Over Time */}
      <div className="graphs-panel__chart">
        <div className="graphs-panel__chart-title">Inequality (Gini)</div>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={giniData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
            <XAxis
              dataKey="round"
              tick={{ fontSize: 6, fontFamily: "'Press Start 2P'", fill: '#6B7280' }}
              stroke="#4A4A6A"
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 6, fontFamily: "'Press Start 2P'", fill: '#6B7280' }}
              stroke="#4A4A6A"
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Line
              type="stepAfter"
              dataKey="gini"
              stroke={CHART_COLORS.gini}
              strokeWidth={2}
              dot={{ fill: CHART_COLORS.gini, r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default GraphsPanel
