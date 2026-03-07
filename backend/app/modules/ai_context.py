import json
import os
from typing import Any, Dict, Optional, List

import pandas as pd

from app.modules.semantics import rebuild_and_save_semantics, load_semantics
from app.modules.study_design import load_study_design, rebuild_and_save_study_design


MAX_AI_COLUMNS_DEFAULT = 200
MAX_PROTOCOL_STEPS_HARD_CAP = 20000
MAX_VARIABLES_PER_STEP_HARD_CAP = 200
MAX_PREDICTORS_HARD_CAP = 200


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _infer_kind(dtype_str: str, name: str, unique: Optional[int] = None, total: Optional[int] = None) -> str:
    name_l = str(name or "").strip().lower()
    dtype = str(dtype_str or "").lower()
    if any(k in dtype for k in ["int", "float", "double", "number"]):
        if unique is not None and total:
            ratio = float(unique) / float(max(1, total))
        else:
            ratio = None
        looks_like_group = any(
            k in name_l
            for k in [
                "group",
                "групп",
                "treat",
                "arm",
                "cohort",
                "category",
                "категор",
                "рандом",
            ]
        )
        if unique is not None and ratio is not None:
            if (unique <= 12 and ratio <= 0.2) or (looks_like_group and unique <= 50):
                return "categorical"
        return "numeric"
    if "date" in dtype or "time" in dtype:
        return "datetime"
    if "bool" in dtype:
        return "categorical"
    if "category" in dtype:
        return "categorical"
    return "categorical" if "object" in dtype or "string" in dtype else "text"


def _extract_unit_hint(name: str) -> Optional[str]:
    raw = str(name or "")
    if not raw:
        return None
    for left, right in (("(", ")"), ("[", "]"), ("{", "}")):
        if left in raw and right in raw:
            try:
                unit = raw.split(left, 1)[1].split(right, 1)[0].strip()
                if unit and len(unit) <= 24:
                    return unit
            except Exception:
                continue
    return None


def build_ai_context(
    *,
    dataset_id: str,
    base_dir: str,
    df: Optional[pd.DataFrame] = None,
    scan_report: Optional[Dict[str, Any]] = None,
    semantics: Optional[Dict[str, Any]] = None,
    max_columns: int = MAX_AI_COLUMNS_DEFAULT,
) -> Dict[str, Any]:
    dataset_id = str(dataset_id)
    base_dir = str(base_dir)

    if scan_report is None:
        scan_report = _load_json(os.path.join(base_dir, dataset_id, "processed", "scan_report.json")) or {}

    if semantics is None:
        semantics = load_semantics(base_dir, dataset_id)
        if semantics is None:
            semantics = rebuild_and_save_semantics(
                dataset_id=dataset_id,
                base_dir=base_dir,
                scan_report=scan_report,
                source="auto",
            )

    study_design = load_study_design(base_dir, dataset_id)
    if study_design is None:
        study_design = rebuild_and_save_study_design(
            dataset_id=dataset_id,
            base_dir=base_dir,
            scan_report=scan_report,
            semantics=semantics,
            source="auto",
        )

    dtypes = _load_json(os.path.join(base_dir, dataset_id, "processed", "dtypes.json")) or {}

    columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else {}
    if not isinstance(columns_meta, dict):
        columns_meta = {}

    total_rows = None
    if isinstance(scan_report, dict):
        missing_report = scan_report.get("missing_report")
        if isinstance(missing_report, dict):
            try:
                total_rows = int(missing_report.get("total_rows") or 0)
            except Exception:
                total_rows = None

    if total_rows is None and df is not None:
        try:
            total_rows = int(len(df.index))
        except Exception:
            total_rows = None

    columns_out: List[Dict[str, Any]] = []
    numeric_cols: List[str] = []
    categorical_cols: List[str] = []

    col_names = list(columns_meta.keys())
    if not col_names and df is not None:
        col_names = [str(c) for c in df.columns]

    for col in col_names[:max_columns]:
        meta = columns_meta.get(col) if isinstance(columns_meta, dict) else None
        meta = meta if isinstance(meta, dict) else {}
        dtype_str = str(meta.get("type") or dtypes.get(col) or "")
        unique_count = meta.get("unique_count")
        missing_count = meta.get("missing_count")
        mean = meta.get("mean")
        median = meta.get("median")
        min_val = meta.get("min")
        max_val = meta.get("max")
        normality = meta.get("normality") if isinstance(meta.get("normality"), dict) else None
        example_val = meta.get("example")
        top_values = meta.get("top_values") if isinstance(meta.get("top_values"), list) else None
        categories = meta.get("categories") if isinstance(meta.get("categories"), list) else None

        if dtype_str == "" and df is not None and col in df.columns:
            dtype_str = str(df[col].dtype)

        kind = _infer_kind(dtype_str, col, unique_count if isinstance(unique_count, int) else None, total_rows)

        role = None
        if isinstance(semantics, dict):
            cols = semantics.get("columns")
            if isinstance(cols, dict):
                role = cols.get(col, {}).get("role")

        col_item = {
            "name": str(col),
            "dtype": dtype_str,
            "kind": kind,
            "missing": missing_count,
            "unique": unique_count,
            "role": role,
        }

        stats = {}
        for key, val in (
            ("mean", mean),
            ("median", median),
            ("min", min_val),
            ("max", max_val),
        ):
            if isinstance(val, (int, float)):
                stats[key] = float(val)
        if isinstance(normality, dict) and "p_value" in normality:
            stats["normality_p"] = normality.get("p_value")
        if stats:
            col_item["stats"] = stats

        unit_hint = _extract_unit_hint(col)
        if unit_hint:
            col_item["unit_hint"] = unit_hint

        if example_val is not None:
            if isinstance(example_val, str):
                example_val = example_val.strip()
                if len(example_val) > 40:
                    example_val = example_val[:37] + "..."
            col_item["example"] = example_val

        if isinstance(top_values, list) and top_values:
            trimmed = []
            for item in top_values[:3]:
                if not isinstance(item, dict):
                    continue
                val = item.get("value")
                cnt = item.get("count")
                if isinstance(val, str) and len(val) > 30:
                    val = val[:27] + "..."
                trimmed.append({"value": val, "count": cnt})
            if trimmed:
                col_item["top_values"] = trimmed

        if isinstance(categories, list) and 0 < len(categories) <= 6:
            cleaned = []
            for item in categories:
                v = str(item)
                if len(v) > 30:
                    v = v[:27] + "..."
                cleaned.append(v)
            if cleaned:
                col_item["categories"] = cleaned

        columns_out.append(col_item)

        if kind == "numeric":
            numeric_cols.append(str(col))
        elif kind == "categorical":
            categorical_cols.append(str(col))

    summary = {
        "n_rows": total_rows,
        "n_cols": len(col_names) if col_names else None,
        "columns_scanned": len(columns_out),
    }

    design = None
    if isinstance(semantics, dict):
        design = semantics.get("design") if isinstance(semantics.get("design"), dict) else None

    context = {
        "summary": summary,
        "columns": columns_out,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "design": design,
        "study_design": {
            "design": study_design.get("design") if isinstance(study_design, dict) else None,
            "analysis_policy": study_design.get("analysis_policy") if isinstance(study_design, dict) else None,
        },
    }

    return context


def safe_plan_constraints(preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prefs = preferences if isinstance(preferences, dict) else {}
    analysis_mode = str(prefs.get("analysis_mode") or prefs.get("mode") or "").strip().lower()
    is_exploratory = analysis_mode in {"exploratory", "maximal", "broad"}

    def _pick_int(key: str, default: int, min_v: int, max_v: int, allow_off: bool = False) -> int:
        raw = prefs.get(key)
        if allow_off and isinstance(raw, str):
            raw_l = raw.strip().lower()
            if raw_l in {"off", "none", "unlimited", "no_limit", "max"}:
                return max_v
        try:
            val = int(raw)
        except Exception:
            val = default
        if allow_off and val <= 0:
            return max_v
        return max(min_v, min(max_v, val))

    return {
        "max_steps": _pick_int(
            "max_steps",
            40 if is_exploratory else 20,
            5,
            MAX_PROTOCOL_STEPS_HARD_CAP,
            allow_off=True,
        ),
        "max_variables_per_step": _pick_int("max_variables_per_step", 8, 2, MAX_VARIABLES_PER_STEP_HARD_CAP),
        "max_predictors": _pick_int("max_predictors", 6, 1, MAX_PREDICTORS_HARD_CAP),
    }


def enforce_protocol_constraints(protocol: List[Dict[str, Any]], constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(protocol, list):
        return []
    max_steps = int(constraints.get("max_steps") or 20)
    max_vars = int(constraints.get("max_variables_per_step") or 8)
    max_preds = int(constraints.get("max_predictors") or 6)
    if max_steps <= 0:
        max_steps = MAX_PROTOCOL_STEPS_HARD_CAP
    max_steps = min(max_steps, MAX_PROTOCOL_STEPS_HARD_CAP)
    max_vars = max(1, min(max_vars, MAX_VARIABLES_PER_STEP_HARD_CAP))
    max_preds = max(1, min(max_preds, MAX_PREDICTORS_HARD_CAP))

    out: List[Dict[str, Any]] = []
    for step in protocol[:max_steps]:
        if not isinstance(step, dict):
            continue
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        cfg = dict(cfg)

        if isinstance(cfg.get("variables"), list) and max_vars:
            cfg["variables"] = cfg.get("variables")[:max_vars]
        if isinstance(cfg.get("outcome_columns"), list) and max_vars:
            cfg["outcome_columns"] = cfg.get("outcome_columns")[:max_vars]
        if isinstance(cfg.get("predictors"), list) and max_preds:
            cfg["predictors"] = cfg.get("predictors")[:max_preds]

        step = dict(step)
        step["config"] = cfg
        out.append(step)

    return out


def generate_prompt_brief(dataset_meta: Dict[str, Any], preferences: Optional[Dict[str, Any]] = None) -> str:
    prefs = preferences if isinstance(preferences, dict) else {}
    summary = dataset_meta.get("summary") if isinstance(dataset_meta, dict) else {}
    design = dataset_meta.get("study_design", {}).get("design") if isinstance(dataset_meta, dict) else None
    policy = dataset_meta.get("study_design", {}).get("analysis_policy") if isinstance(dataset_meta, dict) else None

    def _norm_list(value: Any, limit: int = 12) -> List[str]:
        if isinstance(value, list):
            items = [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
            return items[:limit]
        if isinstance(value, (str, int, float)):
            s = str(value).strip()
            return [s] if s else []
        return []

    analysis_mode = str(prefs.get("analysis_mode") or "exploratory").strip().lower()
    group_col = None
    time_col = None
    subject_col = None
    design_type = None
    outcomes = []
    cat_outcomes = []
    endpoint_groups = []

    if isinstance(design, dict):
        group_col = design.get("group_column")
        time_col = design.get("time_column")
        subject_col = design.get("subject_column")
        design_type = design.get("design_type")
        outcomes = _norm_list(design.get("outcomes"), limit=20)
        cat_outcomes = _norm_list(design.get("categorical_outcomes"), limit=12)
        endpoint_groups = design.get("endpoint_groups") if isinstance(design.get("endpoint_groups"), list) else []

    alpha = None
    multiplicity = None
    post_hoc = None
    bootstrap_ci = None
    bootstrap_samples = None
    if isinstance(policy, dict):
        alpha = policy.get("alpha")
        multiplicity = policy.get("multiplicity_correction")
        post_hoc = policy.get("post_hoc")
        bootstrap_ci = policy.get("bootstrap_ci")
        bootstrap_samples = policy.get("bootstrap_samples")

    lines: List[str] = []
    lines.append("Цель: сформировать максимально полный статистический отчёт по датасету (exploratory), с акцентом на клинический дизайн и интерпретацию.")
    lines.append("")
    lines.append("Контекст данных:")
    if isinstance(summary, dict):
        n_rows = summary.get("n_rows")
        n_cols = summary.get("n_cols")
        if n_rows or n_cols:
            lines.append(f"- Размер: {n_rows or '?'} строк, {n_cols or '?'} столбцов.")
    if design_type:
        lines.append(f"- Тип дизайна: {design_type}.")
    if group_col:
        lines.append(f"- Группировка: {group_col}.")
    if time_col:
        lines.append(f"- Время/визит: {time_col}.")
    if subject_col:
        lines.append(f"- ID субъекта: {subject_col}.")

    if outcomes:
        lines.append(f"- Числовые исходы (топ): {', '.join(outcomes)}.")
    if cat_outcomes:
        lines.append(f"- Категориальные исходы (топ): {', '.join(cat_outcomes)}.")

    if endpoint_groups:
        lines.append("- Endpoint-группы по визитам:")
        for item in endpoint_groups[:8]:
            if not isinstance(item, dict):
                continue
            ep = item.get("endpoint") or "endpoint"
            tps = _norm_list(item.get("timepoints"), limit=10)
            if tps:
                lines.append(f"  - {ep}: {', '.join(tps)}")

    lines.append("")
    lines.append("Задачи анализа:")
    if analysis_mode == "focused":
        lines.append("- Фокусный анализ ключевых исходов и сравнений групп.")
    else:
        lines.append("- Максимально широкий анализ: описательная статистика, сравнение групп, корреляции, регрессии, кластерные методы.")
        lines.append("- Проверка повторных измерений (если есть визиты) и анализ динамики.")
    lines.append("- Множественные сравнения учитывать и корректировать.")
    if alpha is not None:
        lines.append(f"- Уровень значимости: α={alpha}.")
    if multiplicity:
        lines.append(f"- Поправка множественности: {multiplicity}.")
    if post_hoc:
        lines.append(f"- Post-hoc: {post_hoc}.")
    if bootstrap_ci is not None:
        enabled = bool(bootstrap_ci)
        if enabled:
            lines.append(
                f"- Bootstrap для CI: включен (samples={bootstrap_samples if bootstrap_samples is not None else 1000})."
            )
        else:
            lines.append("- Bootstrap для CI: выключен.")

    lines.append("")
    lines.append("Гипотезы/фокус (заполни вручную):")
    lines.append("- Основная гипотеза: ...")
    lines.append("- Дополнительные гипотезы: ...")
    lines.append("- Какие конечные точки самые важные: ...")

    return "\n".join(lines).strip()
