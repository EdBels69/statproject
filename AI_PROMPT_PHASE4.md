# AI Agent Autonomous Prompt — Phase 4 (Final Polish)

> Copy this entire prompt and paste to your AI coding agent

---

## SYSTEM CONTEXT

You are an autonomous AI coding agent working on the StatWizard project — a clinical statistical analysis web application.

**Stack:**

- **Frontend**: React 19 + Vite + TailwindCSS
- **Backend**: Python FastAPI
- **Language**: Russian UI, English code

**Current Status:**

- ✅ Phase 1: Method ID mappings, searchable dropdowns
- ✅ Phase 2: Variable Workspace, smart templates, error messages
- ✅ Phase 3: Publication plots, protocol save/load
- 🎯 Phase 4: FINAL POLISH (animations, shortcuts, accessibility)

**Project Root:** `/Users/eduardbelskih/Проекты Github/statproject/`

---

## YOUR MISSION

Complete **Phase 4: P3 Polish** as described in `PHASE4_PLAN.md`.

### Tasks

1. **Task 4.1**: Micro-Animations — protocol steps, modals, buttons
2. **Task 4.2**: Keyboard Shortcuts — Ctrl+Enter, Ctrl+S, ?, Escape
3. **Task 4.3**: Undo/Redo (optional) — protocol history
4. **Task 4.4**: Accessibility — focus, ARIA, contrast

---

## EXECUTION RULES

1. **Read first**: Start by reading `PHASE4_PLAN.md` completely
2. **Prioritize**: Tasks 4.1 and 4.2 are most important
3. **Verify after each change**:

   ```bash
   cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
   ```

4. **Russian UI**: All user-facing text in Russian
5. **Test manually**: Keyboard navigation, animations

---

## KEY FILES TO MODIFY

```
frontend/src/app/
├── pages/AnalysisDesign.jsx           # Shortcuts integration
├── components/
│   ├── analysis/ProtocolBuilder.jsx   # Animations, undo/redo UI
│   ├── TestConfigModal.jsx            # Modal animations
│   ├── VariableWorkspace.jsx          # List animations
│   └── SaveProtocolModal.jsx          # Modal animations
├── hooks/
│   ├── useKeyboardShortcuts.js        # [NEW]
│   └── useUndoRedo.js                 # [NEW, optional]
└── index.css                          # Animation keyframes
```

---

## ANIMATION EXAMPLES

```css
/* Add to index.css */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.animate-fade-in { animation: fadeIn 0.2s ease-out; }
.animate-slide-up { animation: slideUp 0.2s ease-out; }
```

---

## KEYBOARD SHORTCUTS MAP

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + Enter` | Execute protocol |
| `Ctrl/Cmd + S` | Save protocol |
| `Ctrl/Cmd + O` | Open protocol library |
| `Escape` | Close any modal |
| `?` | Show shortcuts help |

---

## VERIFICATION COMMANDS

```bash
# Lint check
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
```

---

## COMPLETION CRITERIA

Phase 4 is complete when:

- [ ] Protocol steps have add/remove animations
- [ ] Modals fade in/out smoothly
- [ ] Buttons have hover/active feedback
- [ ] `Ctrl+Enter` runs protocol
- [ ] `Ctrl+S` saves protocol
- [ ] `Escape` closes modals
- [ ] `?` shows shortcuts help
- [ ] ESLint passes with zero errors

---

## START NOW

Begin by running:

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE4_PLAN.md
```

Then implement Task 4.1 first. Work autonomously until all tasks are complete.

**GO! This is the FINAL PHASE! 🚀**
