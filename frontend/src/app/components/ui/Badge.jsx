export default function Badge({ variant = 'neutral', className = '', children, ...props }) {
  const base = 'inline-flex items-center gap-2 rounded-[2px] border px-2 py-1 text-[10px] font-semibold tracking-[0.18em] uppercase';
  const variants = {
    neutral: 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)]',
    accent: 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]',
    success: 'border-[color:var(--success)] bg-[color:var(--white)] text-[color:var(--text-primary)]',
    error: 'border-[color:var(--error)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
  };

  const cls = `${base} ${variants[variant] || variants.neutral} ${className}`.trim();
  return (
    <span className={cls} {...props}>
      {children}
    </span>
  );
}
