export default function ChartFallback({ label }) {
  return (
    <div
      style={{
        height: 360,
        borderRadius: '2px',
        border: '1px solid var(--border-color)',
        background: 'var(--bg-tertiary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontSize: '12px',
      }}
      className="animate-pulse"
    >
      {label}
    </div>
  );
}
