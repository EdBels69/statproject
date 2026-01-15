import React from 'react';

const Input = React.forwardRef(function Input(
  { className = '', type = 'text', ...props },
  ref
) {
  return (
    <input
      ref={ref}
      type={type}
      className={`h-9 w-full border-0 border-b border-b-[color:var(--border-color)] bg-transparent px-0 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] focus-visible:border-b-[color:var(--accent)] focus-visible:outline-none ${className}`.trim()}
      {...props}
    />
  );
});

export default Input;
