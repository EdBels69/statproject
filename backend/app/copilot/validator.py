from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

import pandas as pd


REQUIRED_FIELDS_BY_METHOD: Dict[str, List[str]] = {
    "mixed_effects": ["outcome", "time", "group", "subject"],
    "clustered_correlation": ["variables"],
    "responders": ["outcome_columns", "group"],
    "t_test_one": ["outcome"],
    "bayes_t_test_one": ["outcome"],
    "t_test_ind": ["outcome", "group"],
    "t_test_welch": ["outcome", "group"],
    "mann_whitney": ["outcome", "group"],
    "anova": ["outcome", "group"],
    "anova_welch": ["outcome", "group"],
    "kruskal": ["outcome", "group"],
    "chi_square": ["outcome", "group"],
    "fisher_exact": ["outcome", "group"],
    "bayes_t_test_ind": ["outcome", "group"],
    "bayes_t_test_rel": ["outcome", "group"],
    "bayes_correlation": ["outcome", "group"],
    "linear_regression": ["outcome", "predictors"],
    "logistic_regression": ["outcome", "predictors"],
    "bayes_linear_regression": ["outcome", "predictors"],
    "survival_km": ["outcome", "event"],
    "time_series_analysis": ["outcome"],
    "ancova": ["outcome", "group", "covariates"],
    "pca": ["variables"],
    "efa": ["variables"],
    "kmeans": ["variables"],
    "hierarchical_clustering": ["variables"],
    "cronbach_alpha": ["variables"],
    "shapiro_wilk": ["outcome"],
    "bland_altman": ["method_1", "method_2"],
    "icc": ["outcome", "subject_col", "rater_col"],
    "cohens_kappa": ["outcome", "group"],
    "mcnemar": ["outcome", "group"],
    "point_biserial": ["outcome", "group"],
    "cochran_q": ["outcome_cols"],
    "partial_correlation": ["outcome", "group", "covariates"],
    "rm_anova": ["outcome_cols", "subject_col"],
    "friedman": ["outcome_cols"],
}

GROUP_BASED_METHODS: Set[str] = {
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "anova",
    "anova_welch",
    "kruskal",
    "chi_square",
    "fisher_exact",
    "bayes_t_test_ind",
    "ancova",
    "point_biserial",
    "mcnemar",
    "cohens_kappa",
}

NUMERIC_OUTCOME_METHODS: Set[str] = {
    "mixed_effects",
    "responders",
    "t_test_one",
    "bayes_t_test_one",
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "anova",
    "anova_welch",
    "kruskal",
    "linear_regression",
    "logistic_regression",
    "bayes_linear_regression",
    "bayes_t_test_ind",
    "bayes_t_test_rel",
    "bayes_correlation",
    "survival_km",
    "time_series_analysis",
    "ancova",
    "pca",
    "efa",
    "kmeans",
    "hierarchical_clustering",
    "cronbach_alpha",
    "shapiro_wilk",
    "bland_altman",
    "icc",
    "point_biserial",
    "cochran_q",
    "partial_correlation",
    "rm_anova",
    "friedman",
}

LIST_COLUMN_KEYS: Set[str] = {
    "predictors",
    "covariates",
    "variables",
    "outcome_cols",
    "outcome_columns",
    "targets",
    "pairs",
}

SINGLE_COLUMN_KEYS: Set[str] = {
    "outcome",
    "target",
    "group",
    "group1",
    "group2",
    "time",
    "time_col",
    "subject",
    "subject_col",
    "event",
    "rater",
    "rater_col",
    "method_1",
    "method_2",
    "baseline",
    "follow",
    "split_by",
    "before",
    "after",
}


def _dtype_is_numeric(df: Any, col: str) -> bool:
    try:
        kind = str(df[col].dtype).lower()
    except Exception:
        return False
    return any(token in kind for token in ["int", "float", "double", "number", "bool"])


def _extract_columns(config: Mapping[str, Any]) -> Set[str]:
    cols: Set[str] = set()
    if not isinstance(config, Mapping):
        return cols
    for key in SINGLE_COLUMN_KEYS:
        val = config.get(key)
        if isinstance(val, str) and val.strip():
            cols.add(val.strip())
    for key in LIST_COLUMN_KEYS:
        val = config.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    cols.add(item.strip())
        elif key == "pairs" and isinstance(val, list):
            for pair in val:
                if isinstance(pair, list):
                    for item in pair:
                        if isinstance(item, str) and item.strip():
                            cols.add(item.strip())
    return cols


def _missing_required_keys(method: str, config: Mapping[str, Any]) -> List[str]:
    required = REQUIRED_FIELDS_BY_METHOD.get(method, [])
    missing: List[str] = []
    for key in required:
        val = config.get(key)
        if key in LIST_COLUMN_KEYS:
            if not isinstance(val, list) or not val:
                missing.append(key)
        else:
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(key)
    return missing


def _complete_rows(df: Any, cols: Iterable[str]) -> Optional[int]:
    cols_list = [str(c) for c in cols if isinstance(c, str) and c]
    if not cols_list:
        try:
            return int(len(df))
        except Exception:
            return None
    try:
        return int(len(df.dropna(subset=cols_list)))
    except Exception:
        return None


def validate_protocol_step(step: Mapping[str, Any], df: Any, *, alpha: float = 0.05) -> Dict[str, Any]:
    step_id = str(step.get("id") or "").strip() if isinstance(step, Mapping) else ""
    method = str(step.get("method") or "").strip().lower() if isinstance(step, Mapping) else ""
    config = step.get("config") if isinstance(step, Mapping) and isinstance(step.get("config"), dict) else {}

    errors: List[str] = []
    warnings: List[str] = []
    checks: List[Dict[str, Any]] = []

    if not step_id:
        errors.append("Step id is required.")
    if not method:
        errors.append("Method is required.")

    try:
        alpha_f = float(alpha)
    except Exception:
        alpha_f = 0.05
    if alpha_f <= 0.0 or alpha_f >= 1.0:
        warnings.append(f"Alpha={alpha_f} is outside common bounds (0,1).")

    missing_keys = _missing_required_keys(method, config)
    if missing_keys:
        errors.append(f"Missing required config keys: {', '.join(sorted(missing_keys))}.")
    checks.append({"check": "required_keys", "missing": missing_keys})

    referenced_cols = sorted(_extract_columns(config))
    available_cols = set([str(c) for c in getattr(df, "columns", [])])
    missing_cols = sorted([c for c in referenced_cols if c not in available_cols])
    if missing_cols:
        errors.append(f"Columns not found: {', '.join(missing_cols)}.")
    checks.append(
        {
            "check": "column_existence",
            "referenced": referenced_cols,
            "missing": missing_cols,
        }
    )

    if method in NUMERIC_OUTCOME_METHODS:
        numeric_targets: List[str] = []
        for key in ["outcome", "target", "method_1", "method_2", "baseline", "follow"]:
            val = config.get(key)
            if isinstance(val, str) and val.strip():
                numeric_targets.append(val.strip())
        for key in ["variables", "outcome_cols", "outcome_columns", "targets"]:
            val = config.get(key)
            if isinstance(val, list):
                numeric_targets.extend([str(x).strip() for x in val if isinstance(x, str) and str(x).strip()])
        numeric_targets = sorted(list(set(numeric_targets)))

        non_numeric = [col for col in numeric_targets if col in available_cols and not _dtype_is_numeric(df, col)]
        if non_numeric:
            errors.append(f"Numeric columns required, but non-numeric detected: {', '.join(non_numeric)}.")
        checks.append(
            {
                "check": "numeric_columns",
                "targets": numeric_targets,
                "non_numeric": non_numeric,
            }
        )

    if method in GROUP_BASED_METHODS:
        group_col = config.get("group") or config.get("group_col")
        if isinstance(group_col, str) and group_col in available_cols:
            try:
                group_n = int(df[group_col].dropna().nunique())
            except Exception:
                group_n = 0
            if group_n < 2:
                errors.append(f"Group column '{group_col}' must contain at least 2 levels.")
            checks.append(
                {
                    "check": "group_levels",
                    "group_col": group_col,
                    "n_levels": group_n,
                }
            )

    if method in {"pca", "efa", "kmeans", "hierarchical_clustering"}:
        vars_raw = config.get("variables")
        vars_list = (
            [str(v).strip() for v in vars_raw if isinstance(v, str) and str(v).strip()]
            if isinstance(vars_raw, list)
            else []
        )
        vars_unique = sorted(list(set(vars_list)))
        min_vars = 3 if method == "efa" else 2
        if len(vars_unique) < min_vars:
            errors.append(
                f"Method '{method}' requires at least {min_vars} variables (received {len(vars_unique)})."
            )
        checks.append(
            {
                "check": "variable_count",
                "method": method,
                "variables": vars_unique,
                "min_required": min_vars,
            }
        )

    if method == "bland_altman":
        method_1 = config.get("method_1")
        method_2 = config.get("method_2")
        if (
            isinstance(method_1, str)
            and isinstance(method_2, str)
            and method_1.strip()
            and method_2.strip()
            and method_1.strip() == method_2.strip()
        ):
            errors.append("Bland-Altman requires two distinct measurement columns (method_1 != method_2).")
        checks.append(
            {
                "check": "bland_altman_columns",
                "method_1": method_1,
                "method_2": method_2,
            }
        )

    if method == "time_series_analysis":
        time_col = config.get("time") or config.get("time_col")
        if not isinstance(time_col, str) or time_col not in available_cols:
            warnings.append(
                "time_series_analysis should define a valid time/time_col; chronology interpretation may be unreliable."
            )
            checks.append({"check": "time_series_time_column", "time_col": time_col, "valid": False})
        else:
            series = df[time_col].dropna()
            n_unique_time = int(series.nunique()) if len(series) else 0
            if n_unique_time < 3:
                errors.append(
                    f"time_series_analysis requires at least 3 unique time points in '{time_col}' (found {n_unique_time})."
                )

            parsed = pd.to_datetime(series, errors="coerce")
            parse_ratio = float(parsed.notna().mean()) if len(parsed) else 0.0
            min_year: Optional[int] = None
            max_year: Optional[int] = None
            if parse_ratio >= 0.8:
                years = parsed.dropna().dt.year
                if len(years):
                    min_year = int(years.min())
                    max_year = int(years.max())
                    current_year = datetime.utcnow().year
                    if min_year <= 1971 and max_year <= 1985:
                        warnings.append(
                            "Time column is mostly in 1970-1985 range; verify date parsing to avoid Unix-epoch artifacts."
                        )
                    elif min_year < 1990 or max_year > (current_year + 5):
                        warnings.append(
                            f"Time column year range looks unusual ({min_year}-{max_year}); verify chronology and source dates."
                        )
            elif _dtype_is_numeric(df, time_col):
                warnings.append(
                    "Time column appears numeric/non-date; use explicit calendar dates to avoid ambiguous time-series interpretation."
                )

            checks.append(
                {
                    "check": "time_series_time_quality",
                    "time_col": time_col,
                    "n_unique_time": n_unique_time,
                    "datetime_parse_ratio": parse_ratio,
                    "min_year": min_year,
                    "max_year": max_year,
                }
            )

    complete_n = _complete_rows(df, referenced_cols)
    min_n = 2
    if method in {"linear_regression", "logistic_regression", "bayes_linear_regression"}:
        min_n = 8
    elif method in {"pca", "efa", "kmeans", "hierarchical_clustering"}:
        min_n = 5
    elif method in {"cochran_q", "friedman", "rm_anova"}:
        min_n = 4

    if isinstance(complete_n, int):
        if complete_n < min_n:
            errors.append(f"Insufficient complete rows: {complete_n} (< {min_n}) for method '{method}'.")
    checks.append({"check": "complete_rows", "n_complete": complete_n, "min_required": min_n})

    status = "passed" if not errors else "failed"
    return {
        "step_id": step_id or None,
        "method": method or None,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def build_protocol_validation_report(
    *,
    steps: List[Mapping[str, Any]],
    step_reports: List[Dict[str, Any]],
    validator_enabled: bool,
    validator_strict: bool,
    alpha: float,
    global_errors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    rows = [item for item in (step_reports or []) if isinstance(item, dict)]
    g_errors = [item for item in (global_errors or []) if isinstance(item, dict)]
    failed_steps = [row for row in rows if str(row.get("status") or "").lower() != "passed"]
    status = "passed" if (validator_enabled and not failed_steps and not g_errors) else "failed"
    if not validator_enabled:
        status = "skipped"

    return {
        "schema": "clinimetria.protocol_validation",
        "version": 1,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "enabled": bool(validator_enabled),
        "strict": bool(validator_strict),
        "alpha": float(alpha),
        "status": status,
        "summary": {
            "steps_total": int(len(steps or [])),
            "steps_checked": int(len(rows)),
            "steps_failed": int(len(failed_steps)),
            "global_errors": int(len(g_errors)),
        },
        "global_errors": g_errors,
        "steps": rows,
    }
