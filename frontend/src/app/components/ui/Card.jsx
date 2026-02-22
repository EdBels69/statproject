import React from 'react';

export function Card({ className = '', ...props }) {
  return (
    <div
      className={`card text-[var(--black)] ${className}`.trim()}
      {...props}
    />
  );
}

export function CardHeader({ className = '', ...props }) {
  return (
    <div
      className={`px-5 pt-5 ${className}`.trim()}
      {...props}
    />
  );
}

export function CardTitle({ className = '', ...props }) {
  return (
    <div
      className={`text-base font-semibold tracking-tight ${className}`.trim()}
      {...props}
    />
  );
}

export function CardDescription({ className = '', ...props }) {
  return (
    <div
      className={`mt-1 text-sm text-[var(--gray-600)] ${className}`.trim()}
      {...props}
    />
  );
}

export function CardContent({ className = '', ...props }) {
  return (
    <div
      className={`px-5 pb-5 ${className}`.trim()}
      {...props}
    />
  );
}

export function CardFooter({ className = '', ...props }) {
  return (
    <div
      className={`px-5 pb-5 pt-0 ${className}`.trim()}
      {...props}
    />
  );
}
