import { useCallback, useMemo, useState } from 'react';

export function useUndoRedo(initialValue, options = {}) {
  const limit = Number.isFinite(options?.limit) ? Math.max(1, options.limit) : 20;

  const [state, setState] = useState(() => ({
    history: [initialValue],
    index: 0
  }));

  const present = state.history[state.index];
  const canUndo = state.index > 0;
  const canRedo = state.index < state.history.length - 1;

  const set = useCallback((nextValueOrUpdater) => {
    setState((s) => {
      const current = s.history[s.index];
      const next = typeof nextValueOrUpdater === 'function'
        ? nextValueOrUpdater(current)
        : nextValueOrUpdater;

      if (Object.is(next, current)) return s;

      const base = s.history.slice(0, s.index + 1);
      const nextHistory = [...base, next];
      const overflow = Math.max(0, nextHistory.length - limit);
      const trimmed = overflow > 0 ? nextHistory.slice(overflow) : nextHistory;
      return { history: trimmed, index: trimmed.length - 1 };
    });
  }, [limit]);

  const undo = useCallback(() => {
    setState((s) => {
      if (s.index <= 0) return s;
      return { ...s, index: s.index - 1 };
    });
  }, []);

  const redo = useCallback(() => {
    setState((s) => {
      if (s.index >= s.history.length - 1) return s;
      return { ...s, index: s.index + 1 };
    });
  }, []);

  const reset = useCallback((value) => {
    setState({ history: [value], index: 0 });
  }, []);

  return useMemo(() => ({
    present,
    set,
    undo,
    redo,
    reset,
    canUndo,
    canRedo
  }), [canRedo, canUndo, present, redo, reset, set, undo]);
}

