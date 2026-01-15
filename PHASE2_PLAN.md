# Phase 2: P1 UX Improvements — Implementation Plan

> **Status**: Ready for implementation  
> **Prerequisite**: Phase 1 completed ✅

---

## Overview

Transform the StatWizard interface from functional to intuitive by implementing three key improvements:

1. Variable Workspace Component
2. Improved Template Application
3. Better Error Messages

---

## Task 2.1: Variable Workspace Component

### Goal

Create a rich variable management interface that replaces basic dropdowns with a professional data science workspace.

### Files to Modify/Create

- **[NEW]** `frontend/src/app/components/VariableWorkspaceEnhanced.jsx`
- **[MODIFY]** `frontend/src/app/components/VariableWorkspace.jsx`
- **[MODIFY]** `frontend/src/app/pages/AnalysisDesign.jsx`

### Requirements

1. **Variable List with Statistics**
   - Show each column with: name, type badge (NUM/CAT/DATE), missing count, unique count
   - For numeric: min, max, mean
   - For categorical: top 3 values

2. **Search and Filter**
   - Text search by column name
   - Filter by type (numeric, categorical, datetime)
   - Filter by role (unused, target, group, covariate)

3. **Drag-and-Drop Assignment**
   - Drag variables to "Target", "Group", "Covariates" zones
   - Visual feedback during drag
   - Clear drop zones

4. **Quick Stats Preview**
   - On hover/click, show mini histogram or value distribution
   - Use existing column metadata from dataset

### Implementation Steps

```
1. Create VariableCard component with stats display
2. Add search/filter bar to VariableWorkspace
3. Implement drag-and-drop with react-dnd or native HTML5 drag
4. Connect to TestConfigModal config state
5. Test with 100+ column dataset
```

---

## Task 2.2: Improved Template Application

### Goal

Make protocol templates actually useful by auto-mapping variables intelligently.

### Files to Modify

- **[MODIFY]** `frontend/src/app/components/analysis/ProtocolTemplateSelector.jsx`
- **[MODIFY]** `backend/app/routers/analysis_router.py` (if needed)

### Requirements

1. **Smart Variable Suggestions**
   - When template selected, suggest variables based on:
     - Column names matching keywords (e.g., "group", "treatment", "outcome")
     - Column types matching requirements (numeric for outcome, categorical for group)

2. **Visual Mapping Interface**
   - Show template slots: "Target Variable → [dropdown]"
   - Highlight suggested matches in green
   - Allow manual override

3. **Validation Before Apply**
   - Check variable types match template requirements
   - Show warnings for mismatches (e.g., "Group variable should have 2-5 categories")

### Implementation Steps

```
1. Add variable suggestion logic to ProtocolTemplateSelector
2. Create VariableMappingRow component with suggestions
3. Add validation function for template requirements
4. Show validation errors/warnings before apply
5. Test with all existing templates
```

---

## Task 2.3: Better Error Messages

### Goal

Replace cryptic Python tracebacks with human-readable error explanations.

### Files to Modify

- **[MODIFY]** `frontend/src/app/pages/AnalysisDesign.jsx` (results display)
- **[MODIFY]** `backend/app/services/analysis_engine.py`
- **[NEW]** `frontend/src/app/utils/errorMessages.js`

### Requirements

1. **Error Message Mapping**

   ```javascript
   const errorMessages = {
     'ValueError: could not convert string to float': 
       'Переменная содержит текст вместо чисел. Проверьте, что выбрана числовая колонка.',
     'KeyError':
       'Указанная колонка не найдена в данных. Возможно, название изменилось.',
     'singular matrix':
       'Недостаточно вариации в данных для выполнения анализа.',
     // ... more mappings
   };
   ```

2. **Actionable Suggestions**
   - Each error should include "Что делать:" section
   - Link to relevant help/documentation if available

3. **Error Categories**
   - Data errors (wrong types, missing values)
   - Configuration errors (incompatible settings)
   - Statistical errors (assumptions violated)

### Implementation Steps

```
1. Create errorMessages.js with common error patterns
2. Add parseError() function to match and translate
3. Update AnalysisDesign to use translated errors
4. Add "suggestion" field to error display UI
5. Test with intentionally broken configurations
```

---

## Verification Plan

### After Each Task

1. Run `npm run lint` — zero errors
2. Run `npm run dev` — app starts without console errors
3. Manual test the specific feature

### End-to-End Test (After All Tasks)

1. Upload dataset with 50+ columns
2. Use Variable Workspace to assign target/group
3. Apply a template with suggested variables
4. Run analysis
5. If error occurs, verify human-readable message appears
6. Complete successful analysis run

---

## File References

| File | Purpose |
|------|---------|
| `REFACTORING_PLAN.md` | Master plan with all phases |
| `frontend/src/app/components/VariableWorkspace.jsx` | Current variable component |
| `frontend/src/app/components/analysis/ProtocolTemplateSelector.jsx` | Template selection UI |
| `frontend/src/app/components/TestConfigModal.jsx` | Test configuration (Phase 1 done) |
| `frontend/src/app/pages/AnalysisDesign.jsx` | Main analysis page |

---

## Success Criteria

- [ ] Variables searchable and filterable
- [ ] Drag-and-drop works for variable assignment
- [ ] Templates suggest matching variables
- [ ] Errors display in Russian with actionable suggestions
- [ ] ESLint passes with zero errors
- [ ] App runs without console errors
