import React from 'react';

const TabsContext = React.createContext(null);

export function Tabs({
  value: valueProp,
  defaultValue,
  onValueChange,
  className = '',
  children,
  ...props
}) {
  const baseId = React.useId();
  const [uncontrolledValue, setUncontrolledValue] = React.useState(
    defaultValue ?? ''
  );

  const value = valueProp !== undefined ? valueProp : uncontrolledValue;
  const setValue = React.useCallback(
    (nextValue) => {
      if (valueProp === undefined) setUncontrolledValue(nextValue);
      onValueChange?.(nextValue);
    },
    [onValueChange, valueProp]
  );

  const ctx = React.useMemo(
    () => ({ value, setValue, baseId }),
    [value, setValue, baseId]
  );

  return (
    <TabsContext.Provider value={ctx}>
      <div className={`${className}`.trim()} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

export function TabsList({ className = '', ...props }) {
  return (
    <div
      role="tablist"
      className={`flex items-center gap-6 border-b border-[color:var(--border-color)] ${className}`.trim()}
      {...props}
    />
  );
}

export function TabsTrigger({
  value,
  className = '',
  children,
  onClick,
  ...props
}) {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error('TabsTrigger must be used within Tabs');

  const selected = ctx.value === value;
  const tabId = `${ctx.baseId}-tab-${value}`;
  const panelId = `${ctx.baseId}-panel-${value}`;

  return (
    <button
      type="button"
      role="tab"
      id={tabId}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      onClick={(e) => {
        ctx.setValue(value);
        onClick?.(e);
      }}
      className={`
        -mb-px border-b-2 px-1 py-4 text-sm font-semibold tracking-tight transition-colors
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--accent)]
        ${selected
          ? 'border-[color:var(--accent)] text-[color:var(--text-primary)]'
          : 'border-transparent text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)]'}
        ${className}
      `.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

export function TabsContent({ value, className = '', children, ...props }) {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error('TabsContent must be used within Tabs');

  const selected = ctx.value === value;
  const tabId = `${ctx.baseId}-tab-${value}`;
  const panelId = `${ctx.baseId}-panel-${value}`;

  if (!selected) return null;

  return (
    <div
      role="tabpanel"
      id={panelId}
      aria-labelledby={tabId}
      tabIndex={0}
      className={`${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  );
}
