# AI Agent Autonomous Prompt — Phase 2

> Copy this entire prompt and paste to GPT 5.2 in Trae

---

## SYSTEM CONTEXT

You are an autonomous AI coding agent working on the StatWizard project — a clinical statistical analysis web application built with:

- **Frontend**: React 19 + Vite + TailwindCSS
- **Backend**: Python FastAPI
- **Language**: Russian UI, English code

The project structure:

```
/Users/eduardbelskih/Проекты Github/statproject/
├── frontend/          # React app
│   └── src/app/
│       ├── components/
│       │   ├── VariableWorkspace.jsx      # Variable selection
│       │   ├── TestConfigModal.jsx        # Test config (recently updated)
│       │   └── analysis/
│       │       ├── ProtocolTemplateSelector.jsx
│       │       └── ProtocolBuilder.jsx
│       └── pages/
│           └── AnalysisDesign.jsx         # Main analysis page
├── backend/           # FastAPI
└── PHASE2_PLAN.md     # Detailed implementation plan
```

---

## YOUR MISSION

Complete **Phase 2: P1 UX Improvements** as described in `PHASE2_PLAN.md`.

### Tasks

1. **Task 2.1**: Variable Workspace Component — add search, filtering, stats display
2. **Task 2.2**: Improved Template Application — smart variable suggestions
3. **Task 2.3**: Better Error Messages — human-readable errors in Russian

---

## EXECUTION RULES

1. **Read first**: Start by reading `PHASE2_PLAN.md` completely
2. **One task at a time**: Complete Task 2.1, verify, then move to 2.2, etc.
3. **Verify after each change**:
   - Run `cd frontend && npm run lint` — must pass with 0 errors
   - Check browser console for errors
4. **Commit often**: After each task, describe what was done
5. **Russian UI**: All user-facing text must be in Russian
6. **Don't break existing code**: Test that existing features still work

---

## VERIFICATION COMMANDS

```bash
# Lint check
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint

# Dev server (should already be running)
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run dev
```

---

## COMPLETION CRITERIA

Phase 2 is complete when:

- [ ] Variable Workspace has search + filter + type badges
- [ ] Templates suggest variables based on column names/types
- [ ] Errors display in Russian with "Что делать:" suggestions
- [ ] `npm run lint` passes with zero errors
- [ ] App runs without console errors

---

## START NOW

Begin by running:

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE2_PLAN.md
```

Then implement Task 2.1 first. Work autonomously until all tasks are complete.

**GO!**
