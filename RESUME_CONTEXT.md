# StatWizard: Project Snapshot 2026-01-06

## Current Status
We have completed **Phase 25** (Correlation Clustering & Heatmaps). The logic is fully functional in both backend and frontend.

## Goals for Today (Phase 26)
We need to implement **Repeated Measures ANOVA** and **Friedman Test** using the `pingouin` library.

### Technical Task List:
1.  **Backend**: Open `backend/app/stats/engine.py`. Replace stubs for `_handle_rm_anova` and `_handle_friedman_test` (around lines 950-960) with full implementations.
2.  **Frontend**: Open `frontend/src/app/pages/Analyze.jsx`. Add UI options for these tests in the Settings modal (Sphericity correction, Effect size).
3.  **Verification**: Write and run `verify_rm_anova.py`.

## Key Files:
- `/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend/app/stats/engine.py` (Main logic)
- `/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/frontend/src/app/pages/Analyze.jsx` (Analyis UI)

## Dialogue Start (Copy & Paste):
"Привет! Продолжаем разработку StatWizard. Проект находится в папке `/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/`. Прочитай файл `RESUME_CONTEXT.md` и переходи к реализации **Phase 26** (RM-ANOVA и Friedman) в файле `engine.py`. Библиотека `pingouin` уже установлена."
