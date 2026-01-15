# Phase 3: P2 Feature Completion — Implementation Plan

> **Status**: Ready for implementation  
> **Prerequisites**: Phase 1 ✅, Phase 2 ✅

---

## Overview

Complete the feature set by adding:

1. Publication-ready export for statistical plots
2. Protocol save/load functionality

---

## Task 3.1: Publication-Ready Plots

### Goal

Enable users to export high-quality plots suitable for scientific publications (journals, posters).

### Files to Modify/Create

- **[MODIFY]** `frontend/src/app/components/VisualizePlot.jsx`
- **[MODIFY]** `frontend/src/app/components/ClusteredHeatmap.jsx`
- **[MODIFY]** `frontend/src/app/components/InteractionPlot.jsx`
- **[NEW]** `frontend/src/app/utils/exportPlot.js`
- **[MODIFY]** `backend/app/services/plotting_service.py` (if exists)

### Requirements

1. **Export Formats**
   - PNG (300 DPI) for web/presentations
   - SVG for vector graphics
   - PDF for print publications (optional)

2. **Export Settings Panel**

   ```jsx
   <ExportSettings>
     <SizePreset>
       - Journal Figure (3.5" x 3")
       - Half Page (7" x 5")
       - Full Page (7" x 10")
       - Poster (12" x 10")
       - Custom
     </SizePreset>
     <DPI>150 / 300 / 600</DPI>
     <FontSize>8 / 10 / 12 / 14</FontSize>
     <Background>White / Transparent</Background>
     <Title>Optional title text</Title>
   </ExportSettings>
   ```

3. **Plot Styling for Publications**
   - Clean white background (no grid by default)
   - Legible font sizes
   - Proper axis labels and legends
   - APA/AMA style formatting option

### Implementation Steps

```
1. Create exportPlot.js utility with SVG-to-PNG conversion
2. Add export button to each visualization component
3. Create ExportSettingsModal component
4. Apply publication-quality defaults (fonts, sizes)
5. Test with different chart types
6. Verify exported files open correctly
```

---

## Task 3.2: Protocol Templates Save/Load

### Goal

Allow users to save their custom protocol configurations for reuse.

### Files to Modify/Create

- **[MODIFY]** `frontend/src/app/pages/AnalysisDesign.jsx`
- **[MODIFY]** `frontend/src/app/components/analysis/ProtocolBuilder.jsx`
- **[NEW]** `frontend/src/app/components/SaveProtocolModal.jsx`
- **[MODIFY]** `backend/app/routers/analysis_router.py`
- **[NEW]** `backend/app/models/custom_protocol.py` (if using DB)

### Requirements

1. **Save Protocol**
   - Button in ProtocolBuilder: "💾 Сохранить протокол"
   - Modal with: Name, Description, Tags (optional)
   - Save to localStorage (MVP) or backend API

2. **Load Protocol**
   - "📂 Мои протоколы" button
   - List of saved protocols with: Name, Date, Description
   - Preview of steps before applying
   - Delete option

3. **Protocol Format**

   ```json
   {
     "id": "uuid",
     "name": "My Analysis Protocol",
     "description": "...",
     "created_at": "2026-01-15T...",
     "steps": [
       { "method": "t_test_ind", "config": {...} },
       { "method": "mixed_model", "config": {...} }
     ]
   }
   ```

4. **Import/Export**
   - Export protocol as JSON file
   - Import from JSON file
   - Share via URL (optional)

### Implementation Steps

```
1. Create protocol serialization utilities
2. Implement localStorage save/load (MVP)
3. Create SaveProtocolModal with form
4. Create LoadProtocolModal with list
5. Add buttons to ProtocolBuilder
6. Test save/load cycle
7. (Optional) Add backend persistence API
```

---

## Verification Plan

### After Each Task

1. Run `npm run lint` — zero errors
2. Run `npm run dev` — app starts without console errors
3. Manual test the specific feature

### End-to-End Test

1. Design a multi-step protocol
2. Save the protocol
3. Clear the current protocol
4. Load the saved protocol — verify steps restored
5. Run analysis, export plot as PNG (300 DPI)
6. Verify exported image quality and dimensions

---

## File References

| File | Purpose |
|------|---------|
| `frontend/src/app/components/VisualizePlot.jsx` | Generic chart visualization |
| `frontend/src/app/components/ClusteredHeatmap.jsx` | Correlation heatmap |
| `frontend/src/app/components/analysis/ProtocolBuilder.jsx` | Protocol step list |
| `frontend/src/app/pages/AnalysisDesign.jsx` | Main analysis page |

---

## Success Criteria

- [ ] Export button present on all chart components
- [ ] Export settings allow DPI and size selection
- [ ] Exported PNG is publication quality (300+ DPI)
- [ ] Protocol can be saved with name/description
- [ ] Saved protocol appears in "My Protocols" list
- [ ] Protocol can be loaded and restores all steps
- [ ] ESLint passes with zero errors
