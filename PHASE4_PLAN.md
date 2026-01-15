# Phase 4: P3 Polish — Implementation Plan

> **Status**: Ready for implementation  
> **Prerequisites**: Phase 1 ✅, Phase 2 ✅, Phase 3 ✅

---

## Overview

Final polish phase for production readiness:

1. Micro-animations and transitions
2. Keyboard shortcuts
3. Undo/Redo functionality
4. Loading states and skeletons
5. Accessibility improvements

---

## Task 4.1: Micro-Animations

### Goal

Add subtle animations that make the UI feel alive and responsive.

### Files to Modify

- **[MODIFY]** `frontend/src/app/components/analysis/ProtocolBuilder.jsx`
- **[MODIFY]** `frontend/src/app/components/VariableWorkspace.jsx`
- **[MODIFY]** `frontend/src/app/components/TestConfigModal.jsx`
- **[MODIFY]** `frontend/src/index.css` or Tailwind config

### Requirements

1. **Protocol Step Animations**
   - Fade-in on add
   - Slide-out on remove
   - Smooth reorder animation

2. **Modal Animations**
   - Fade + scale on open/close
   - Backdrop fade

3. **Button Feedback**
   - Subtle scale on press (active:scale-95)
   - Hover transitions

4. **Loading States**
   - Skeleton loaders for data
   - Spinner for actions

### Implementation Notes

```css
/* Example Tailwind utilities */
.animate-fade-in { animation: fadeIn 0.2s ease-out; }
.animate-slide-up { animation: slideUp 0.2s ease-out; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { transform: translateY(10px); opacity: 0; } }
```

---

## Task 4.2: Keyboard Shortcuts

### Goal

Enable power users to work faster with keyboard.

### Files to Create/Modify

- **[NEW]** `frontend/src/app/hooks/useKeyboardShortcuts.js`
- **[MODIFY]** `frontend/src/app/pages/AnalysisDesign.jsx`
- **[NEW]** `frontend/src/app/components/KeyboardShortcutsHelp.jsx`

### Requirements

1. **Global Shortcuts**
   - `Ctrl/Cmd + Enter` — Execute protocol
   - `Ctrl/Cmd + S` — Save protocol
   - `Ctrl/Cmd + O` — Open protocol library
   - `Ctrl/Cmd + Z` — Undo (if implemented)
   - `Escape` — Close modals
   - `?` — Show shortcuts help

2. **Visual Hints**
   - Show shortcuts in button tooltips
   - Shortcuts help modal (press `?`)

### Implementation Notes

```javascript
// useKeyboardShortcuts.js
export function useKeyboardShortcuts(shortcuts) {
  useEffect(() => {
    const handler = (e) => {
      const key = `${e.ctrlKey || e.metaKey ? 'mod+' : ''}${e.key}`;
      if (shortcuts[key]) {
        e.preventDefault();
        shortcuts[key]();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shortcuts]);
}
```

---

## Task 4.3: Undo/Redo (Optional)

### Goal

Allow users to undo mistakes in protocol building.

### Files to Create/Modify

- **[NEW]** `frontend/src/app/hooks/useUndoRedo.js`
- **[MODIFY]** `frontend/src/app/pages/AnalysisDesign.jsx`

### Requirements

1. **Protocol History**
   - Track protocol state changes
   - Max 20 undo steps
   - Clear on dataset change

2. **UI Controls**
   - Undo/Redo buttons in ProtocolBuilder header
   - Keyboard: `Ctrl+Z` / `Ctrl+Shift+Z`

### Implementation Notes

```javascript
// Simple undo/redo hook
function useUndoRedo(initial) {
  const [history, setHistory] = useState([initial]);
  const [index, setIndex] = useState(0);
  
  const current = history[index];
  const canUndo = index > 0;
  const canRedo = index < history.length - 1;
  
  const set = (value) => {
    const newHistory = history.slice(0, index + 1);
    setHistory([...newHistory, value].slice(-20));
    setIndex(newHistory.length);
  };
  
  return { current, set, undo, redo, canUndo, canRedo };
}
```

---

## Task 4.4: Accessibility (A11y)

### Goal

Ensure the app is usable with screen readers and keyboard-only navigation.

### Requirements

1. **Focus Management**
   - Focus trap in modals
   - Visible focus indicators
   - Logical tab order

2. **ARIA Labels**
   - Role attributes on interactive elements
   - aria-label for icon-only buttons
   - aria-live for dynamic content

3. **Color Contrast**
   - WCAG AA compliant (4.5:1 for text)
   - Don't rely on color alone

---

## Verification Plan

### After Each Task

1. Run `npm run lint` — zero errors
2. Test keyboard navigation manually
3. Test with screen reader (VoiceOver on Mac)

### Final Checklist

- [ ] Animations feel smooth, not jarring
- [ ] All shortcuts work on Mac and Windows
- [ ] Modals can be closed with Escape
- [ ] Tab navigation is logical
- [ ] No console errors

---

## Success Criteria

- [ ] Protocol steps animate on add/remove
- [ ] Modals have open/close animations
- [ ] `Ctrl/Cmd + Enter` runs protocol
- [ ] `?` opens shortcuts help
- [ ] Focus is visible on all interactive elements
- [ ] ESLint passes with zero errors
