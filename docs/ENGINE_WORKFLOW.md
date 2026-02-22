# Workflow: Python vs R Engine

This document explains how the shared pipeline works with two statistical engines.

```mermaid
flowchart TD
    A["Upload / Clean Data"] --> B["Study Design Inference"]
    B --> C["LLM Plan (Protocol)"]
    C --> D{"Stats Engine"}
    D -->|Python| E["Python Stats Engine"]
    D -->|R| F["R Engine (Rscript)"]
    E --> G["Unified Results Schema"]
    F --> G
    G --> H["Tables / Plots / Report"]
    H --> I["DOCX / PDF"]
```

Notes:
- The protocol is shared for both engines.
- R engine computes statistics; Python remains the canonical formatter for plots and reports.
- Engine selection is configured per run (globals or step-level override).
