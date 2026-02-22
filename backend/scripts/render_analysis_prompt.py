#!/usr/bin/env python3
"""
Render a structured analysis prompt from a JSON spec.

Usage:
  python3 backend/scripts/render_analysis_prompt.py \
    --spec docs/prompt_templates/covid_glycemia_spec.example.json \
    --template docs/prompt_templates/ANALYSIS_PROMPT_TEMPLATE.md \
    --out docs/exports/covid_prompt_rendered.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = PROJECT_ROOT / "docs" / "prompt_templates" / "ANALYSIS_PROMPT_TEMPLATE.md"


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _lines_numbered(items: Iterable[str]) -> str:
    out = [str(x).strip() for x in items if str(x).strip()]
    if not out:
        return "1) (не задано)"
    return "\n".join(f"{idx + 1}) {item}" for idx, item in enumerate(out))


def _lines_bulleted(items: Iterable[str]) -> str:
    out = [str(x).strip() for x in items if str(x).strip()]
    if not out:
        return "- (не задано)"
    return "\n".join(f"- {item}" for item in out)


def _format_variable_block(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "- (не задано)"
    lines: List[str] = []
    for item in items:
        if isinstance(item, str):
            t = item.strip()
            if t:
                lines.append(f"- {t}")
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        source = str(item.get("source", "")).strip()
        vtype = str(item.get("type", "")).strip()
        notes = str(item.get("notes", "")).strip()
        if not name and not source:
            continue
        label = f"`{name}`" if name else "`(unnamed)`"
        if source and source != name:
            label += f" <= `{source}`"
        if vtype:
            label += f" [{vtype}]"
        if notes:
            label += f" — {notes}"
        lines.append(f"- {label}")
    return "\n".join(lines) if lines else "- (не задано)"


def _format_outcome_block(outcome: Any) -> str:
    if not isinstance(outcome, dict):
        return "- (не задано)"
    name = str(outcome.get("name", "")).strip() or "(не задано)"
    src = outcome.get("source_columns")
    mapping = outcome.get("mapping_rules")
    lines = [f"- Outcome: `{name}`"]
    if isinstance(src, list) and src:
        src_line = ", ".join(f"`{str(x).strip()}`" for x in src if str(x).strip())
        lines.append(f"- Source columns: {src_line}")
    if isinstance(mapping, list) and mapping:
        lines.append("- Mapping rules:")
        lines.extend(f"  - {str(x).strip()}" for x in mapping if str(x).strip())
    return "\n".join(lines)


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def render_prompt(spec: Dict[str, Any], template_text: str) -> str:
    dataset = spec.get("dataset") if isinstance(spec.get("dataset"), dict) else {}

    payload: Dict[str, str] = {
        "dataset_title": str(dataset.get("title", "Dataset")).strip(),
        "dataset_path": str(dataset.get("path", "")).strip(),
        "dataset_sheet": str(dataset.get("sheet", "Лист1")).strip(),
        "model_id": str(spec.get("model_id", "google/gemini-2.5-flash")).strip(),
        "language": str(spec.get("language", "ru")).strip(),
        "research_goal": str(spec.get("research_goal", "(не задано)")).strip(),
        "research_questions_block": _lines_numbered(spec.get("research_questions", [])),
        "outcome_block": _format_outcome_block(spec.get("outcome")),
        "exposures_block": _format_variable_block(spec.get("exposures")),
        "covariates_block": _format_variable_block(spec.get("covariates")),
        "comorbidities_block": _format_variable_block(spec.get("comorbidities")),
        "treatments_block": _format_variable_block(spec.get("treatments")),
        "analysis_steps_block": _lines_numbered(spec.get("analysis_steps", [])),
        "models_block": _lines_bulleted(spec.get("models", [])),
        "sensitivity_block": _lines_bulleted(spec.get("sensitivity", [])),
        "plots_block": _lines_bulleted(spec.get("plots", [])),
        "required_outputs_block": _lines_bulleted(spec.get("required_outputs", [])),
        "style_constraints_block": _lines_bulleted(spec.get("style_constraints", [])),
    }
    return template_text.format_map(SafeDict(payload)).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a structured analysis prompt from JSON spec.")
    parser.add_argument("--spec", type=Path, required=True, help="Path to JSON spec.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Path to template file.")
    parser.add_argument("--out", type=Path, required=True, help="Output prompt file path.")
    args = parser.parse_args()

    spec_path = args.spec if args.spec.is_absolute() else (PROJECT_ROOT / args.spec)
    template_path = args.template if args.template.is_absolute() else (PROJECT_ROOT / args.template)
    out_path = args.out if args.out.is_absolute() else (PROJECT_ROOT / args.out)

    spec = _load_json(spec_path)
    template_text = template_path.read_text(encoding="utf-8")
    prompt = render_prompt(spec, template_text)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt, encoding="utf-8")
    print(json.dumps({"ok": True, "spec": str(spec_path), "template": str(template_path), "out": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

