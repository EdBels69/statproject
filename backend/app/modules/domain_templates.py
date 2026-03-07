"""
domain_templates.py — Pre-built protocol templates for common clinical study types.

Provides 5 ready-to-use analysis protocols:
  1. rct_two_arm — Randomized Controlled Trial: 2-arm comparison
  2. before_after — Pre-post / within-subject design
  3. cross_sectional — Survey / observational study
  4. longitudinal — Repeated measures over time
  5. responder_analysis — Responder enrichment analysis

Each template is a function that accepts variable names and returns a complete
protocol dict compatible with ProtocolEngine.execute_protocol().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TEMPLATES: Dict[str, Dict[str, Any]] = {}


def _register(key: str, *, title_ru: str, title_en: str, description_ru: str, description_en: str, tags: List[str]):
    """Decorator to register a template builder function."""
    def decorator(fn):
        _TEMPLATES[key] = {
            "id": key,
            "title_ru": title_ru,
            "title_en": title_en,
            "description_ru": description_ru,
            "description_en": description_en,
            "tags": tags,
            "builder": fn,
        }
        return fn
    return decorator


def list_templates(*, lang: str = "ru") -> List[Dict[str, Any]]:
    """Return metadata of all available templates (without builder callable)."""
    title_key = f"title_{lang}" if f"title_{lang}" in next(iter(_TEMPLATES.values()), {}) else "title_en"
    desc_key = f"description_{lang}" if f"description_{lang}" in next(iter(_TEMPLATES.values()), {}) else "description_en"
    return [
        {
            "id": meta["id"],
            "title": meta.get(title_key, meta.get("title_en", "")),
            "description": meta.get(desc_key, meta.get("description_en", "")),
            "tags": meta["tags"],
        }
        for meta in _TEMPLATES.values()
    ]


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Return template metadata (including builder) by id."""
    return _TEMPLATES.get(template_id)


def build_protocol(
    template_id: str,
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a complete protocol from a template.

    Args:
        template_id: One of the registered template ids.
        variables: Dict mapping template placeholders to actual column names.
            Common keys: outcome, group, subject, time, covariates, etc.
        alpha: Significance level.
        options: Extra options forwarded to the builder function.

    Returns:
        Protocol dict with {name, alpha, steps: [...]}.

    Raises:
        KeyError: Unknown template id.
    """
    meta = _TEMPLATES.get(template_id)
    if meta is None:
        raise KeyError(f"Unknown template: {template_id!r}. Available: {list(_TEMPLATES)}")
    builder = meta["builder"]
    return builder(variables=variables, alpha=alpha, options=options or {})


# ---------------------------------------------------------------------------
# 1. RCT Two-Arm Comparison
# ---------------------------------------------------------------------------

@_register(
    "rct_two_arm",
    title_ru="РКИ: сравнение двух групп",
    title_en="RCT: Two-Arm Comparison",
    description_ru="Полный протокол для рандомизированного контролируемого исследования с двумя группами. "
                    "Включает Table 1, первичную и вторичную конечные точки, безопасность.",
    description_en="Complete protocol for a 2-arm RCT: Table 1, primary endpoint, "
                    "secondary endpoints, safety analysis.",
    tags=["rct", "clinical", "comparison", "two_arm"],
)
def _build_rct_two_arm(
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    outcome = variables.get("outcome", "")
    group = variables.get("group", "")
    secondary = variables.get("secondary_outcomes", [])
    safety_vars = variables.get("safety_variables", [])
    covariates = variables.get("covariates", [])

    steps: List[Dict[str, Any]] = []

    # Step 1: Table 1 — descriptive comparison
    steps.append({
        "id": "table_1",
        "type": "descriptive_compare",
        "target": outcome,
        "group": group,
        "why_selected": "Table 1: baseline demographics by treatment arm (CONSORT requirement).",
    })

    # Step 2: Primary endpoint
    steps.append({
        "id": "primary_endpoint",
        "type": "hypothesis_test",
        "target": outcome,
        "group": group,
        "auto_fallback": True,
        "why_selected": "Primary efficacy endpoint: two-group comparison with auto-selection of "
                        "parametric/non-parametric test based on normality and sample size.",
    })

    # Step 3: Secondary endpoints
    for idx, sec_var in enumerate(secondary):
        steps.append({
            "id": f"secondary_{idx + 1}",
            "type": "hypothesis_test",
            "target": sec_var,
            "group": group,
            "auto_fallback": True,
            "why_selected": f"Secondary endpoint: {sec_var}. Multiplicity correction applied at report level.",
        })

    # Step 4: Covariate-adjusted (if covariates provided)
    if covariates:
        steps.append({
            "id": "adjusted_primary",
            "type": "regression",
            "target": outcome,
            "predictors": [group] + covariates,
            "kind": "linear",
            "why_selected": "Covariate-adjusted analysis of primary endpoint to account for baseline imbalances.",
        })

    # Step 5: Safety
    for idx, saf_var in enumerate(safety_vars):
        steps.append({
            "id": f"safety_{idx + 1}",
            "type": "hypothesis_test",
            "target": saf_var,
            "group": group,
            "auto_fallback": True,
            "why_selected": f"Safety analysis: {saf_var}.",
        })

    return {
        "name": "RCT Two-Arm Protocol",
        "template_id": "rct_two_arm",
        "alpha": alpha,
        "steps": steps,
        "globals": {
            "multiplicity_correction": "fdr_bh" if len(secondary) > 1 else "none",
        },
    }


# ---------------------------------------------------------------------------
# 2. Before-After (Pre-Post) Design
# ---------------------------------------------------------------------------

@_register(
    "before_after",
    title_ru="До/После: парный дизайн",
    title_en="Before/After: Paired Design",
    description_ru="Протокол для до-после исследования: парные тесты, размер эффекта, "
                    "респондерный анализ (опционально).",
    description_en="Protocol for pre-post studies: paired tests, effect sizes, "
                    "responder analysis (optional).",
    tags=["paired", "before_after", "pre_post", "within_subject"],
)
def _build_before_after(
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    before = variables.get("before", "")
    after = variables.get("after", "")
    outcome = variables.get("outcome", before)
    group = variables.get("group")
    subject = variables.get("subject")
    threshold = variables.get("response_threshold", 0.0)

    steps: List[Dict[str, Any]] = []

    # Step 1: Paired comparison
    steps.append({
        "id": "paired_test",
        "type": "hypothesis_test",
        "target": after,
        "group": before,
        "is_paired": True,
        "auto_fallback": True,
        "why_selected": "Paired test (before/after): Wilcoxon signed-rank or paired t-test "
                        "depending on normality of differences.",
    })

    # Step 2: If group exists, compare groups on delta
    if group:
        steps.append({
            "id": "group_delta",
            "type": "hypothesis_test",
            "target": after,
            "group": group,
            "auto_fallback": True,
            "why_selected": "Between-group comparison on post-treatment values to assess differential response.",
        })

    # Step 3: Responder analysis (optional)
    if subject and group:
        steps.append({
            "id": "responder",
            "type": "responders",
            "outcome_columns": [before, after],
            "time_labels": ["Baseline", "Follow-up"],
            "group_column": group,
            "subject_column": subject,
            "threshold": threshold,
            "direction": options.get("direction", "decrease"),
            "why_selected": "Responder analysis: proportion achieving clinically meaningful "
                            f"change (threshold ≥ {threshold}).",
        })

    return {
        "name": "Before/After Protocol",
        "template_id": "before_after",
        "alpha": alpha,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# 3. Cross-Sectional (Survey / Observational)
# ---------------------------------------------------------------------------

@_register(
    "cross_sectional",
    title_ru="Поперечное исследование",
    title_en="Cross-Sectional Study",
    description_ru="Протокол для одномоментного наблюдательного исследования: "
                    "описательная статистика, корреляции, регрессия.",
    description_en="Protocol for cross-sectional studies: descriptives, correlations, regression.",
    tags=["cross_sectional", "observational", "survey", "correlation"],
)
def _build_cross_sectional(
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    outcome = variables.get("outcome", "")
    predictors = variables.get("predictors", [])
    group = variables.get("group")

    steps: List[Dict[str, Any]] = []

    # Step 1: Descriptive stats (if group)
    if group:
        steps.append({
            "id": "descriptives",
            "type": "descriptive_compare",
            "target": outcome,
            "group": group,
            "why_selected": "Table 1: sample characteristics by group.",
        })

    # Step 2: Correlations with each predictor
    for idx, pred in enumerate(predictors):
        steps.append({
            "id": f"correlation_{idx + 1}",
            "type": "correlation",
            "target": outcome,
            "group": pred,
            "auto_fallback": True,
            "why_selected": f"Bivariate association between {outcome} and {pred}. "
                            "Pearson or Spearman selected based on normality.",
        })

    # Step 3: Multiple regression
    if len(predictors) >= 2:
        steps.append({
            "id": "regression",
            "type": "regression",
            "target": outcome,
            "predictors": predictors,
            "kind": options.get("regression_kind", "linear"),
            "why_selected": "Multivariable regression to identify independent predictors of outcome.",
        })

    return {
        "name": "Cross-Sectional Protocol",
        "template_id": "cross_sectional",
        "alpha": alpha,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# 4. Longitudinal (Repeated Measures)
# ---------------------------------------------------------------------------

@_register(
    "longitudinal",
    title_ru="Продольное исследование",
    title_en="Longitudinal Study",
    description_ru="Протокол для повторных измерений: смешанные модели, "
                    "временной тренд, взаимодействие группа × время.",
    description_en="Protocol for repeated measures: mixed effects models, "
                    "time trends, group × time interaction.",
    tags=["longitudinal", "repeated_measures", "mixed_effects", "time_series"],
)
def _build_longitudinal(
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    outcome = variables.get("outcome", "")
    outcome_columns = variables.get("outcome_columns", [])
    time_col = variables.get("time")
    group = variables.get("group", "")
    subject = variables.get("subject", "")
    time_labels = variables.get("time_labels", [])
    covariates = variables.get("covariates", [])

    steps: List[Dict[str, Any]] = []

    # Step 1: Descriptive comparison at each timepoint
    if outcome_columns:
        steps.append({
            "id": "timepoint_comparison",
            "type": "batch_compare_by_factor",
            "target": outcome or outcome_columns[0],
            "group": group,
            "split_by": time_col or "Time",
            "why_selected": "Group comparison at each timepoint to identify where differences emerge.",
        })

    # Step 2: Mixed effects model
    step_config: Dict[str, Any] = {
        "id": "mixed_effects",
        "type": "mixed_effects",
        "outcome": outcome,
        "group_column": group,
        "subject_column": subject,
        "covariates": covariates,
        "random_slopes": options.get("random_slopes", False),
        "why_selected": "Linear Mixed Model to estimate group × time interaction while "
                        "accounting for repeated measurements within subjects.",
    }
    if outcome_columns:
        step_config["outcome_columns"] = outcome_columns
    if time_col:
        step_config["time_column"] = time_col
    if time_labels:
        step_config["time_labels"] = time_labels
    steps.append(step_config)

    # Step 3: Group comparison on final timepoint
    final_col = outcome_columns[-1] if outcome_columns else outcome
    steps.append({
        "id": "final_comparison",
        "type": "hypothesis_test",
        "target": final_col,
        "group": group,
        "auto_fallback": True,
        "why_selected": "Comparison at final timepoint as a supplementary sensitivity check.",
    })

    return {
        "name": "Longitudinal Protocol",
        "template_id": "longitudinal",
        "alpha": alpha,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# 5. Responder Analysis
# ---------------------------------------------------------------------------

@_register(
    "responder_analysis",
    title_ru="Анализ респондеров",
    title_en="Responder Analysis",
    description_ru="Протокол для анализа ответивших на лечение: определение порога, "
                    "доля респондеров, NNT, логистическая регрессия предикторов ответа.",
    description_en="Protocol for treatment responder enrichment: threshold, responder rates, "
                    "NNT, logistic regression for predictors of response.",
    tags=["responder", "enrichment", "nnt", "clinical"],
)
def _build_responder_analysis(
    *,
    variables: Dict[str, Any],
    alpha: float = 0.05,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    outcome_columns = variables.get("outcome_columns", [])
    group = variables.get("group", "")
    subject = variables.get("subject")
    time_labels = variables.get("time_labels", [])
    threshold = variables.get("response_threshold", 0.0)
    direction = options.get("direction", "decrease")
    predictors = variables.get("predictors", [])

    steps: List[Dict[str, Any]] = []

    # Step 1: Responder rates by group
    resp_step: Dict[str, Any] = {
        "id": "responder_rates",
        "type": "responders",
        "outcome_columns": outcome_columns,
        "group_column": group,
        "threshold": threshold,
        "direction": direction,
        "why_selected": f"Primary responder analysis: proportion achieving ≥ {threshold} "
                        f"{'decrease' if direction == 'decrease' else 'increase'} from baseline.",
    }
    if subject:
        resp_step["subject_column"] = subject
    if time_labels:
        resp_step["time_labels"] = time_labels
    steps.append(resp_step)

    # Step 2: Group comparison on final outcome
    if len(outcome_columns) >= 2:
        steps.append({
            "id": "endpoint_comparison",
            "type": "hypothesis_test",
            "target": outcome_columns[-1],
            "group": group,
            "auto_fallback": True,
            "why_selected": "Continuous endpoint comparison at final visit as sensitivity analysis.",
        })

    # Step 3: Logistic regression for predictors of response
    if predictors:
        steps.append({
            "id": "predictors_of_response",
            "type": "regression",
            "target": outcome_columns[-1] if outcome_columns else "",
            "predictors": [group] + predictors,
            "kind": "logistic",
            "why_selected": "Logistic regression to identify baseline predictors of treatment response.",
        })

    return {
        "name": "Responder Analysis Protocol",
        "template_id": "responder_analysis",
        "alpha": alpha,
        "steps": steps,
    }
