import React from 'react';

export function Table({ className = '', ...props }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={`${className}`.trim()} {...props} />
    </div>
  );
}

export function TableHeader({ className = '', ...props }) {
  return <thead className={`${className}`.trim()} {...props} />;
}

export function TableBody({ className = '', ...props }) {
  return <tbody className={`${className}`.trim()} {...props} />;
}

export function TableFooter({ className = '', ...props }) {
  return <tfoot className={`${className}`.trim()} {...props} />;
}

export function TableRow({ className = '', ...props }) {
  return <tr className={`${className}`.trim()} {...props} />;
}

export function TableHead({ className = '', ...props }) {
  return <th className={`${className}`.trim()} {...props} />;
}

export function TableCell({ className = '', ...props }) {
  return <td className={`${className}`.trim()} {...props} />;
}

export function TableCaption({ className = '', ...props }) {
  return (
    <caption
      className={`mt-3 text-left text-xs text-[var(--gray-600)] ${className}`.trim()}
      {...props}
    />
  );
}
