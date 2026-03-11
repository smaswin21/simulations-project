/**
 * EventBanner — amber alert bar shown when a scripted event fires.
 * Props: message (string|null)
 */
export default function EventBanner({ message }) {
  if (!message) return null

  return (
    <div style={{
      marginBottom: 12, padding: '8px 16px',
      borderRadius: 8,
      background: 'rgba(120,53,15,0.5)',
      border: '1px solid rgba(146,64,14,0.4)',
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <span style={{ color: '#fbbf24', fontSize: 14 }}>⚡</span>
      <span style={{ fontSize: 11, fontWeight: 500, color: '#fcd34d' }}>{message}</span>
    </div>
  )
}
