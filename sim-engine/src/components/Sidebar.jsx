import ParamsPanel from './ParamsPanel.jsx'
import GraphsPanel from './GraphsPanel.jsx'
import '../styles/sidebar.css'

function Sidebar() {
  return (
    <aside className="sidebar">
      <ParamsPanel />
      <GraphsPanel />
    </aside>
  )
}

export default Sidebar
