import { useEffect } from 'react';

function isEditableTarget(target) {
  const el = target;
  if (!el) return false;
  const tag = String(el.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (el.isContentEditable) return true;
  const role = el.getAttribute?.('role');
  return role === 'textbox' || role === 'combobox';
}

function normalizeKey(key) {
  if (!key) return '';
  if (key === ' ') return 'space';
  if (key.length === 1) return key.toLowerCase();
  return key.toLowerCase();
}

function toShortcutString(e) {
  const parts = [];
  if (e.ctrlKey || e.metaKey) parts.push('mod');
  if (e.shiftKey) parts.push('shift');
  if (e.altKey) parts.push('alt');
  const k = normalizeKey(e.key);
  return parts.length > 0 ? `${parts.join('+')}+${k}` : k;
}

export function useKeyboardShortcuts(shortcuts, options = {}) {
  const enabled = options?.enabled !== false;

  useEffect(() => {
    if (!enabled) return;

    const handler = (e) => {
      if (e.defaultPrevented) return;

      const key = toShortcutString(e);
      const action = shortcuts?.[key];
      if (!action) return;

      if (key !== 'escape' && isEditableTarget(e.target)) return;

      e.preventDefault();
      action(e);
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, shortcuts]);
}

