export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  children,
  ...props
}) {
  const base = 'inline-flex items-center justify-center select-none whitespace-nowrap rounded-[2px] border px-4 font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)] disabled:cursor-not-allowed disabled:border-[color:var(--border-color)] disabled:bg-[color:var(--bg-secondary)] disabled:text-[color:var(--text-muted)]';
  const sizes = {
    sm: 'h-8 text-xs',
    md: 'h-9 text-sm',
    lg: 'h-10 text-sm'
  };
  const variants = {
    primary: 'border-[color:var(--accent)] bg-[color:var(--accent)] text-[color:var(--white)] hover:border-[color:var(--accent-hover)] hover:bg-[color:var(--accent-hover)]',
    secondary: 'border-[color:var(--text-primary)] bg-[color:var(--text-primary)] text-[color:var(--white)] hover:opacity-90',
    ghost: 'border-[color:var(--border-color)] bg-transparent text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'
  };

  const cls = `${base} ${sizes[size] || sizes.md} ${variants[variant] || variants.primary} ${className}`.trim();
  return (
    <button className={cls} disabled={disabled} {...props}>
      {children}
    </button>
  );
}
