# AI-Driven Development Workflow ("Gemini First")

## Core Philosophy
Use the smartest model (**Gemini 1.5 Pro / "Antigravity"**) for high-leverage decisions (Architecture, Planning, Review) and standard models (**GLM/Roo**) for executing defined tasks.

---

## 🤖 The Roles

### 1. 🧠 Antigravity (Gemini 3 Pro) — **Tech Lead & Architect**
*   **Responsibility**:
    *   Analyzing complex features ("Protocol Sorcerer", "Mixed Models").
    *   Writing the **Implementation Plan** (5 steps + verification).
    *   **Reviewing Code**: Checking logic, architecture, and "smells".
    *   Solving "Hard" Bugs that stump others.
*   **Why**: Huge context window, higher reasoning capability.
*   **Trigger**: `@antigravity plan` or `@antigravity review`.

### 2. 🔨 Roo Code (GLM/Flash) — **Builder / Junior Dev**
*   **Responsibility**:
    *   Writing code based strictly on Antigravity's plan.
    *   Running terminal commands (installing deps, running tests).
    *   Fixing simple syntax/lint errors.
*   **Why**: Fast, integrated with IDE terminal, good for "typing".
*   **Trigger**: `@roo implement`.

### 3. 🛡️ CI/CD (GitHub Actions) — **The Gatekeeper**
*   **Responsibility**:
    *   Blindly running `npm build` and `pytest`.
    *   Blocking merges if *anything* is red.
*   **Why**: Robots don't lie.

---

## 🔄 The Cycle (Automated via n8n)

1.  **You**: Create Issue "Add Survival Analysis".
    *   *Comment*: `@antigravity plan`
2.  **Antigravity**: Reads entire repo context. Posts a checklist:
    *   [ ] Create `modules/stats/survival.py`.
    *   [ ] Add `lifelines` dependency.
    *   [ ] Verify with `tests/test_survival.py`.
3.  **You**: *Comment*: `@roo implement`
4.  **Roo**:
    *   Reads the checklist.
    *   Writes code.
    *   Commits & Pushes.
5.  **GitHub CI**: ❌ Fails (Red).
6.  **Roo**: Fixes typo. Pushes.
7.  **GitHub CI**: ✅ Passes (Green).
8.  **You**: *Comment*: `@antigravity review`
9.  **Antigravity**: "Logic looks good, but you missed the Cox Proportional Hazard assumption check. Fix it."
10. **Roo**: Fixes.
11. **You**: Merge.

---

## ⚠️ "Regression Insurance"
No PR is merged unless **GitHub Actions** is Green. This prevents the "fixed one thing, broke another" loop.
