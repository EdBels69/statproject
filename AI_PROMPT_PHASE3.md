# AI Agent Autonomous Prompt — Phase 3

> Copy this entire prompt and paste to your AI coding agent

---

## SYSTEM CONTEXT

You are an autonomous AI coding agent working on the StatWizard project — a clinical statistical analysis web application.

**Stack:**

- **Frontend**: React 19 + Vite + TailwindCSS
- **Backend**: Python FastAPI (for API calls if needed)
- **Language**: Russian UI, English code

**Current Status:**

- ✅ Phase 1: Method ID mappings, searchable dropdowns
- ✅ Phase 2: Variable Workspace, smart templates, error messages
- 🎯 Phase 3: Publication plots, protocol save/load

**Project Root:** `/Users/eduardbelskih/Проекты Github/statproject/`

---

## YOUR MISSION

Complete **Phase 3: P2 Feature Completion** as described in `PHASE3_PLAN.md`.

### Tasks

1. **Task 3.1**: Publication-Ready Plots — export PNG/SVG with DPI/size settings
2. **Task 3.2**: Protocol Templates Save/Load — localStorage persistence + modals

---

## EXECUTION RULES

1. **Read first**: Start by reading `PHASE3_PLAN.md` completely
2. **One task at a time**: Complete Task 3.1, verify, then move to 3.2
3. **Verify after each change**:

   ```bash
   cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
   ```

   Must pass with 0 errors
4. **Russian UI**: All user-facing text must be in Russian
5. **Don't break existing code**: Test that existing features still work

---

## KEY FILES TO MODIFY

```
frontend/src/app/components/
├── VisualizePlot.jsx         # Add export button
├── ClusteredHeatmap.jsx      # Add export button
├── InteractionPlot.jsx       # Add export button
└── analysis/
    └── ProtocolBuilder.jsx   # Add save/load buttons

frontend/src/app/
├── pages/AnalysisDesign.jsx  # Protocol state management
└── utils/
    └── exportPlot.js         # [NEW] Export utilities
```

---

## VERIFICATION COMMANDS

```bash
# Lint check
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint

# Dev server is already running at localhost:5173
```

---

## COMPLETION CRITERIA

Phase 3 is complete when:

- [ ] Export button on VisualizePlot, ClusteredHeatmap, InteractionPlot
- [ ] ExportSettingsModal with DPI, size presets
- [ ] Exported PNG at 300 DPI
- [ ] "Сохранить протокол" button in ProtocolBuilder
- [ ] SaveProtocolModal with name/description
- [ ] "Мои протоколы" list showing saved protocols
- [ ] Load restores protocol steps correctly
- [ ] `npm run lint` passes with zero errors

---

## START NOW

Begin by running:

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE3_PLAN.md
```

Then implement Task 3.1 first. Work autonomously until all tasks are complete.

**GO!**
