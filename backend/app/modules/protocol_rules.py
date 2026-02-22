import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

from app.modules.semantics import load_semantics
from app.modules.study_design import load_study_design, rebuild_and_save_study_design
from app.modules.ai_context import safe_plan_constraints, enforce_protocol_constraints


SUPPORTED_METHODS_V2 = {
    "descriptive_compare",
    "auto",
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "t_test_rel",
    "wilcoxon",
    "anova",
    "anova_welch",
    "kruskal",
    "chi_square",
    "pearson",
    "spearman",
    "linear_regression",
    "logistic_regression",
    "roc_analysis",
    "mixed_effects",
    "clustered_correlation",
    "bootstrap_pipeline",
    "cluster_profiles",
    "external_validation",
    "random_forest",
    "gradient_boosting",
    "knn",
    "svm",
    "anova_twoway",
    "rm_anova",
    "friedman",
    "batch_analysis",
    "timepoint_batch_analysis",
    "paired_wide",
    "delta_batch_analysis",
}


METHOD_REQUIRED_FIELDS = {
    "descriptive_compare": ["target", "group"],
    "auto": ["outcome", "group"],
    "t_test_ind": ["outcome", "group"],
    "t_test_welch": ["outcome", "group"],
    "mann_whitney": ["outcome", "group"],
    "t_test_rel": ["outcome", "group"],
    "wilcoxon": ["outcome", "group"],
    "anova": ["outcome", "group"],
    "anova_welch": ["outcome", "group"],
    "kruskal": ["outcome", "group"],
    "chi_square": ["outcome", "group"],
    "pearson": ["outcome", "group"],
    "spearman": ["outcome", "group"],
    "linear_regression": ["outcome", "predictors"],
    "logistic_regression": ["outcome", "predictors"],
    "roc_analysis": ["outcome", "group"],
    "mixed_effects": ["outcome", "time", "group", "subject"],
    "clustered_correlation": ["variables"],
    "bootstrap_pipeline": ["outcome"],
    "cluster_profiles": ["variables"],
    "external_validation": ["outcome", "predictors", "external_dataset_id"],
    "random_forest": ["outcome", "predictors"],
    "gradient_boosting": ["outcome", "predictors"],
    "knn": ["outcome", "predictors"],
    "svm": ["outcome", "predictors"],
    "anova_twoway": ["outcome", "group1", "group2"],
    "rm_anova": ["outcome_cols", "subject_col"],
    "friedman": ["outcome_cols"],
    "batch_analysis": ["group", "targets"],
    "timepoint_batch_analysis": ["split_by", "group"],
    "paired_wide": ["baseline", "follow"],
    "delta_batch_analysis": ["group", "pairs"],
}

COMORBIDITY_KEYWORDS = (
    "коморб",
    "comorb",
    "diab",
    "диаб",
    "гиперт",
    "hypert",
    "obes",
    "ожир",
    "ckd",
    "хбп",
    "cad",
    "ибс",
    "copd",
    "хобл",
    "asthma",
    "астм",
    "renal",
    "почек",
    "онко",
    "cancer",
)

TREATMENT_KEYWORDS = (
    "treat",
    "therapy",
    "tx",
    "леч",
    "терап",
    "стероид",
    "insulin",
    "инсулин",
    "metformin",
    "метформ",
    "anticoag",
    "антикоаг",
    "antiviral",
    "противовирус",
    "oxygen",
    "кислород",
    "vent",
    "ивл",
    "вакцин",
    "vaccine",
)


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


def _column_kind(meta: Dict[str, Any]) -> str:
    if not isinstance(meta, dict):
        return "text"
    kind = meta.get("type") or meta.get("kind")
    if isinstance(kind, str) and kind:
        kind_l = kind.lower()
        if "int" in kind_l or "float" in kind_l or "double" in kind_l or "number" in kind_l:
            return "numeric"
        if "date" in kind_l or "time" in kind_l:
            return "datetime"
        if "bool" in kind_l or "category" in kind_l:
            return "categorical"
        if "object" in kind_l or "string" in kind_l:
            return "categorical"
    return "text"


def _normality_ok(meta: Dict[str, Any]) -> Optional[bool]:
    norm = meta.get("normality") if isinstance(meta, dict) else None
    if isinstance(norm, dict) and "p_value" in norm:
        try:
            return float(norm.get("p_value")) >= 0.05
        except Exception:
            return None
    return None


def _unique_count(meta: Dict[str, Any]) -> Optional[int]:
    if not isinstance(meta, dict):
        return None
    val = meta.get("unique_count")
    try:
        return int(val)
    except Exception:
        return None


def _score_outcome_name(name: str) -> int:
    name_l = str(name or "").lower()
    score = 0
    strong = ["исход", "летал", "death", "mortality"]
    mid = ["осложн", "complication", "пневмон", "outcome", "status", "endpoint"]
    mild = ["длительн", "length", "дней", "severity", "тяжест", "score", "event", "survival"]
    if any(k in name_l for k in strong):
        score += 5
    if any(k in name_l for k in mid):
        score += 3
    if any(k in name_l for k in mild):
        score += 2
    if "госпитал" in name_l:
        score += 1
    negative = ["возраст", "age", "пол", "sex", "gender", "перед", "до ", "анамнез", "истор"]
    if any(k in name_l for k in negative):
        score -= 2
    return score


def _pick_primary_numeric(outcomes: List[str], columns_meta: Dict[str, Any]) -> Optional[str]:
    best = None
    best_score = -10
    for col in outcomes:
        meta = columns_meta.get(col, {})
        if _column_kind(meta) != "numeric":
            continue
        score = _score_outcome_name(col)
        if score > best_score:
            best_score = score
            best = col
    return best or (outcomes[0] if outcomes else None)


def _pick_primary_binary(categorical: List[str], columns_meta: Dict[str, Any], min_score: int = 1) -> Optional[str]:
    best = None
    best_score = -10
    for col in categorical:
        meta = columns_meta.get(col, {})
        uniq = _unique_count(meta)
        if uniq != 2:
            continue
        score = _score_outcome_name(col)
        if score > best_score:
            best_score = score
            best = col
    if best_score < min_score:
        return None
    return best


def _extract_categories(meta: Dict[str, Any]) -> List[str]:
    if not isinstance(meta, dict):
        return []
    cats: List[str] = []
    raw = meta.get("categories")
    if isinstance(raw, list):
        cats.extend([str(v) for v in raw if isinstance(v, (str, int, float))])
    raw = meta.get("top_values")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "value" in item:
                cats.append(str(item.get("value")))
    return [c for c in cats if c.strip()]


def _pick_positive_label(meta: Dict[str, Any]) -> Optional[str]:
    labels = _extract_categories(meta)
    if not labels:
        return None

    def score_label(label: str) -> int:
        l = str(label or "").strip().lower()
        score = 0
        if l in {"1", "yes", "true", "positive", "pos", "y", "да"}:
            score += 2
        if any(k in l for k in ["death", "умер", "летал", "fatal", "severe", "тяж", "critical", "icu", "intub"]):
            score += 3
        if any(k in l for k in ["worse", "bad", "fail", "nonresponder", "нет эфф", "без эфф", "no response"]):
            score += 1
        if any(k in l for k in ["alive", "surviv", "выпис", "recovered", "no", "0", "false", "negative"]):
            score -= 2
        return score

    scored = [(score_label(label), label) for label in labels]
    scored.sort(key=lambda x: (x[0], len(str(x[1]))), reverse=True)
    best_score, best_label = scored[0]
    if best_score <= 0:
        return None
    return best_label


def _pick_multiclass_outcome(
    categorical: List[str],
    columns_meta: Dict[str, Any],
    max_classes: int = 6,
    min_score: int = 2,
) -> Tuple[Optional[str], Optional[str]]:
    best = None
    best_label = None
    best_score = -10
    for col in categorical:
        meta = columns_meta.get(col, {})
        uniq = _unique_count(meta)
        if uniq is None or uniq < 3 or uniq > max_classes:
            continue
        label = _pick_positive_label(meta)
        if not label:
            continue
        score = _score_outcome_name(col)
        if score > best_score:
            best_score = score
            best = col
            best_label = label
    if best_score < min_score:
        return None, None
    return best, best_label


def _score_subgroup_name(name: str) -> int:
    name_l = str(name or "").lower()
    score = 0
    keywords = [
        "пол", "sex", "gender",
        "возраст", "age", "age_group", "возрастн",
        "стад", "stage", "severity", "тяжест",
        "коморб", "comorb", "risk", "группа риска",
        "диабет", "diabetes", "гиперт", "hypert",
        "smok", "кур", "ожир", "obesity",
    ]
    if any(k in name_l for k in keywords):
        score += 2
    if any(k in name_l for k in ["группа", "cohort", "arm", "treatment"]):
        score += 1
    return score


def _pick_subgroup_columns(
    categorical_cols: List[str],
    columns_meta: Dict[str, Any],
    exclude: List[str],
    max_groups: int = 2,
    max_unique: int = 8,
) -> List[str]:
    scored: List[Tuple[int, str]] = []
    exclude_set = {c for c in exclude if c}
    for col in categorical_cols:
        if col in exclude_set:
            continue
        meta = columns_meta.get(col, {})
        uniq = _unique_count(meta)
        if uniq is None or uniq < 2 or uniq > max_unique:
            continue
        score = _score_subgroup_name(col)
        score += 1 if uniq <= 4 else 0
        scored.append((score, col))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in scored[:max_groups]]


def _safe_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
    if isinstance(value, (str, int, float)):
        v = str(value).strip()
        return [v] if v else []
    return []


def _normalize_correction(value: Any) -> Optional[str]:
    if value is None:
        return None
    corr = str(value).strip().lower()
    if not corr:
        return None
    if corr in {"bh", "fdr_bh"}:
        return "fdr_bh"
    if corr in {"by", "fdr_by"}:
        return "fdr_by"
    if corr in {"bky", "fdr_bky", "fdr_tsbky"}:
        return "fdr_tsbky"
    if corr in {"bonferroni", "bonf"}:
        return "bonferroni"
    if corr in {"holm"}:
        return "holm"
    if corr in {"sidak"}:
        return "sidak"
    if corr in {"holm-sidak", "holmsidak", "holm_sidak"}:
        return "holm-sidak"
    if corr in {"none", "off", "no"}:
        return "none"
    return corr


def _dedupe_protocol(steps: List[Dict[str, Any]], max_steps: int) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        method = str(step.get("method") or "").strip()
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        key_parts = [method]
        for k in ("outcome", "target", "group", "group1", "group2", "time", "subject", "split_by", "baseline", "follow"):
            if k in cfg:
                key_parts.append(f"{k}:{cfg.get(k)}")
        if "targets" in cfg and isinstance(cfg.get("targets"), list):
            key_parts.append("targets:" + ",".join([str(t) for t in cfg.get("targets")[:5]]))
        if "outcome_cols" in cfg and isinstance(cfg.get("outcome_cols"), list):
            key_parts.append("outcome_cols:" + ",".join([str(t) for t in cfg.get("outcome_cols")[:5]]))
        if "variables" in cfg and isinstance(cfg.get("variables"), list):
            key_parts.append("variables:" + ",".join([str(t) for t in cfg.get("variables")[:5]]))
        if "pairs" in cfg and isinstance(cfg.get("pairs"), list):
            pair_bits = []
            for item in cfg.get("pairs")[:3]:
                if not isinstance(item, dict):
                    continue
                b = item.get("baseline")
                f = item.get("follow")
                if b and f:
                    pair_bits.append(f"{b}->{f}")
            if pair_bits:
                key_parts.append("pairs:" + ",".join(pair_bits))
        key = "|".join(key_parts)
        if key in seen:
            continue
        seen.add(key)
        out.append(step)
        if len(out) >= max_steps:
            break
    return out


def _chunk_list(values: List[str], chunk_size: int) -> List[List[str]]:
    if not values:
        return []
    size = max(1, int(chunk_size))
    return [values[i : i + size] for i in range(0, len(values), size)]


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _contains_keywords(name: str, keywords: Tuple[str, ...]) -> bool:
    name_l = str(name or "").strip().lower()
    return bool(name_l) and any(k in name_l for k in keywords)


def _pick_keyword_subgroups(
    categorical_cols: List[str],
    columns_meta: Dict[str, Any],
    *,
    exclude: List[str],
    keywords: Tuple[str, ...],
    max_groups: int = 2,
    max_unique: int = 12,
) -> List[str]:
    out: List[str] = []
    exclude_set = {c for c in exclude if c}
    for col in categorical_cols:
        if col in exclude_set:
            continue
        if not _contains_keywords(col, keywords):
            continue
        uniq = _unique_count(columns_meta.get(col, {}))
        if uniq is None or uniq < 2 or uniq > max_unique:
            continue
        out.append(col)
        if len(out) >= max_groups:
            break
    return out


def merge_protocols(
    base_steps: List[Dict[str, Any]],
    extra_steps: List[Dict[str, Any]],
    constraints: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    constraints = constraints or safe_plan_constraints({})
    max_steps = int(constraints.get("max_steps") or 20)
    merged = list(base_steps or []) + list(extra_steps or [])
    merged = _dedupe_protocol(merged, max_steps=max_steps)
    return enforce_protocol_constraints(merged, constraints)


def build_exploratory_plan(
    *,
    dataset_id: str,
    base_dir: str,
    preferences: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    scan_report: Optional[Dict[str, Any]] = None,
    semantics: Optional[Dict[str, Any]] = None,
    study_design: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dataset_id = str(dataset_id)
    base_dir = str(base_dir)
    prefs = preferences if isinstance(preferences, dict) else {}
    incoming_constraints = constraints if isinstance(constraints, dict) else None
    constraints = incoming_constraints or safe_plan_constraints(prefs)

    if scan_report is None:
        scan_report = _load_json(os.path.join(base_dir, dataset_id, "processed", "scan_report.json")) or {}

    if semantics is None:
        semantics = load_semantics(base_dir, dataset_id)

    if study_design is None:
        study_design = load_study_design(base_dir, dataset_id)
        if study_design is None:
            study_design = rebuild_and_save_study_design(
                dataset_id=dataset_id,
                base_dir=base_dir,
                scan_report=scan_report,
                semantics=semantics,
                source="auto",
            )

    columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else {}
    if not isinstance(columns_meta, dict):
        columns_meta = {}

    design = study_design.get("design") if isinstance(study_design, dict) else {}
    analysis_policy = study_design.get("analysis_policy") if isinstance(study_design, dict) else {}

    group_col = design.get("group_column")
    time_col = design.get("time_column")
    subject_col = design.get("subject_column")
    id_like_cols = _safe_list(design.get("id_like_columns")) if isinstance(design, dict) else []
    endpoint_groups = design.get("endpoint_groups") if isinstance(design, dict) else None
    endpoint_groups = endpoint_groups if isinstance(endpoint_groups, list) else []

    pref_group = prefs.get("group_column") or prefs.get("group")
    if isinstance(pref_group, str) and pref_group in columns_meta:
        group_col = pref_group

    outcomes = _safe_list(design.get("outcomes")) if isinstance(design, dict) else []
    categorical_outcomes = _safe_list(design.get("categorical_outcomes")) if isinstance(design, dict) else []
    predictors = _safe_list(design.get("predictors")) if isinstance(design, dict) else []

    numeric_cols: List[str] = []
    categorical_cols: List[str] = []
    for col, meta in columns_meta.items():
        kind = _column_kind(meta)
        if kind == "numeric":
            numeric_cols.append(str(col))
        elif kind == "categorical":
            categorical_cols.append(str(col))

    def _filter_excluded(cols: List[str]) -> List[str]:
        excluded = {group_col, time_col, subject_col, *id_like_cols}
        return [c for c in cols if c and c not in excluded]

    numeric_cols = _filter_excluded(numeric_cols)
    categorical_cols = _filter_excluded(categorical_cols)
    outcomes = [c for c in outcomes if c in numeric_cols] or list(numeric_cols)
    categorical_outcomes = [c for c in categorical_outcomes if c in categorical_cols] or list(categorical_cols)
    predictors = [c for c in predictors if c in (numeric_cols + categorical_cols)] or list(
        dict.fromkeys([*numeric_cols, *categorical_cols])
    )

    analysis_mode = str(prefs.get("analysis_mode") or prefs.get("mode") or "").strip().lower()
    is_publication = analysis_mode in {"publication", "publish", "manuscript", "article", "confirmatory"}
    is_discovery = analysis_mode in {"discovery", "hypothesis", "hypothesis_generation", "hypothesis-gen", "idea_mining"}
    is_expert = analysis_mode in {"expert_comprehensive", "expert", "expert_full", "exhaustive"}
    is_comprehensive = analysis_mode in {"comprehensive"} or is_publication or is_expert or is_discovery
    exploratory = bool(analysis_mode in {"exploratory", "maximal", "broad"} or is_discovery or prefs.get("allow_data_mining"))
    if "exploratory_mode" in analysis_policy:
        exploratory = exploratory or bool(analysis_policy.get("exploratory_mode"))
    if is_expert:
        exploratory = True

    target_outcome_total = len(list(dict.fromkeys([*outcomes, *categorical_outcomes])))
    n_columns_total = len(columns_meta)
    total_rows_meta = _safe_int((scan_report.get("missing_report") or {}).get("total_rows"), 0)

    policy_max_targets = _safe_int(analysis_policy.get("max_batch_targets"), 0)
    if policy_max_targets > 0:
        max_targets = policy_max_targets
    elif is_expert:
        max_targets = min(380, max(120, target_outcome_total + max(30, target_outcome_total // 2)))
    elif is_comprehensive:
        max_targets = min(300, max(80, target_outcome_total + max(20, target_outcome_total // 3)))
    elif exploratory:
        max_targets = min(180, max(60, target_outcome_total or 60))
    else:
        max_targets = min(90, max(40, min(60, target_outcome_total or 40)))

    policy_max_steps = _safe_int(analysis_policy.get("max_protocol_steps"), 0)
    constraints_max_steps = _safe_int(constraints.get("max_steps"), 20)
    if incoming_constraints and "max_steps" in incoming_constraints:
        max_steps = constraints_max_steps
    elif policy_max_steps > 0:
        max_steps = max(constraints_max_steps, policy_max_steps)
    elif is_expert:
        estimated_chunks = int(math.ceil(target_outcome_total / float(max(1, max_targets // 3))))
        adaptive_steps = 62 + estimated_chunks * 4 + (n_columns_total // 35)
        if total_rows_meta > 2000:
            adaptive_steps += 10
        if total_rows_meta > 10000:
            adaptive_steps += 8
        max_steps = max(constraints_max_steps, min(140, adaptive_steps))
    elif is_comprehensive:
        estimated_chunks = int(math.ceil(target_outcome_total / float(max(1, max_targets // 3))))
        adaptive_steps = 40 + estimated_chunks * 3 + (n_columns_total // 40)
        if total_rows_meta > 2000:
            adaptive_steps += 6
        max_steps = max(constraints_max_steps, min(120, adaptive_steps))
    else:
        max_steps = constraints_max_steps

    max_predictors = _safe_int(constraints.get("max_predictors"), 6)
    if is_expert:
        max_predictors = max(max_predictors, min(40, 14 + max(0, target_outcome_total // 20)))
    elif is_comprehensive:
        max_predictors = max(max_predictors, min(20, 8 + max(0, target_outcome_total // 30)))

    max_corr_vars = max(8, _safe_int(constraints.get("max_variables_per_step"), 8) * 3)
    if is_expert:
        max_corr_vars = max(max_corr_vars, min(90, 20 + max(0, target_outcome_total // 2)))
    elif is_comprehensive:
        max_corr_vars = max(max_corr_vars, min(60, 12 + max(0, target_outcome_total // 2)))
    max_corr_vars = min(90 if is_expert else (60 if is_comprehensive else 30), max_corr_vars)
    base_chunk = int(analysis_policy.get("batch_chunk_size") or 0)
    if base_chunk <= 0:
        base_chunk = max(8, min(20, _safe_int(constraints.get("max_variables_per_step"), 8) * 2))
        if is_expert:
            base_chunk = min(40, max(base_chunk, 18))
        elif is_comprehensive:
            base_chunk = min(30, max(base_chunk, 14))
    batch_chunk_size = min(max_targets, base_chunk)
    estimated_all_chunks = int(math.ceil(target_outcome_total / float(max(1, batch_chunk_size))))
    default_batch_chunks = 8 if exploratory else 4
    if is_expert:
        default_batch_chunks = min(96, max(18, estimated_all_chunks + (6 if is_publication else 4)))
    elif is_comprehensive:
        default_batch_chunks = min(64, max(12, estimated_all_chunks + (4 if is_publication else 2)))
    max_batch_chunks = _safe_int(analysis_policy.get("max_batch_chunks"), default_batch_chunks)

    multiplicity = _normalize_correction(
        prefs.get("multiplicity_correction") or analysis_policy.get("multiplicity_correction") or "fdr_bh"
    )
    post_hoc = prefs.get("post_hoc") or analysis_policy.get("post_hoc") or None
    post_hoc_correction = _normalize_correction(
        prefs.get("post_hoc_correction") or analysis_policy.get("post_hoc_correction") or None
    )
    alternative = prefs.get("alternative") or "two-sided"

    globals_out = {
        "alternative": alternative,
        "post_hoc": post_hoc,
        "post_hoc_correction": post_hoc_correction,
    }

    steps: List[Dict[str, Any]] = []
    step_idx = 1
    delta_pairs: List[Dict[str, Any]] = []
    paired_added = 0
    max_paired = 6
    if exploratory:
        max_paired = min(12, max_steps)

    def add_step(method: str, config: Dict[str, Any], name: Optional[str] = None) -> None:
        nonlocal step_idx
        steps.append(
            {
                "id": f"step_{step_idx}",
                "name": name,
                "method": method,
                "config": config,
            }
        )
        step_idx += 1

    preferred_outcome = prefs.get("primary_outcome") or prefs.get("outcome")
    preferred_positive_label = prefs.get("positive_label")

    primary_numeric = _pick_primary_numeric(outcomes, columns_meta)
    primary_binary = _pick_primary_binary(categorical_outcomes, columns_meta, min_score=(0 if exploratory else 1))
    primary_binary_label = None
    primary_binary_ovr = False
    if group_col:
        meta = columns_meta.get(group_col, {})
        group_score = _score_outcome_name(group_col)
        if _unique_count(meta) == 2 and group_score >= 2:
            primary_binary = group_col
        elif not primary_binary and _unique_count(meta) == 2 and group_score >= 1:
            primary_binary = group_col

    if isinstance(preferred_outcome, str) and preferred_outcome in columns_meta:
        meta = columns_meta.get(preferred_outcome, {})
        kind = _column_kind(meta)
        uniq = _unique_count(meta)
        if kind == "numeric":
            primary_numeric = preferred_outcome
        elif kind == "categorical":
            if uniq == 2:
                primary_binary = preferred_outcome
            elif uniq and uniq > 2:
                primary_binary = preferred_outcome
                primary_binary_ovr = True
                if preferred_positive_label:
                    primary_binary_label = str(preferred_positive_label)
                else:
                    primary_binary_label = _pick_positive_label(meta)

    if not primary_binary:
        multi_col, pos_label = _pick_multiclass_outcome(
            categorical_outcomes,
            columns_meta,
            max_classes=6,
            min_score=(1 if exploratory else 2),
        )
        if multi_col and pos_label:
            primary_binary = multi_col
            primary_binary_label = pos_label
            primary_binary_ovr = True

    if group_col and outcomes:
        max_desc = int(analysis_policy.get("max_descriptive_targets") or max_targets)
        max_desc = max(1, min(max_desc, max_targets))
        max_desc = min(max_desc, max(4, max_steps // 3))
        desc_targets: List[str] = []
        if exploratory:
            desc_targets = outcomes[:max_desc]
        else:
            desc_targets = [primary_numeric or outcomes[0]]

        # Ensure primary outcome is first in list
        if primary_numeric and primary_numeric in outcomes:
            if primary_numeric in desc_targets:
                desc_targets = [primary_numeric] + [t for t in desc_targets if t != primary_numeric]
            elif len(desc_targets) < max_desc:
                desc_targets = [primary_numeric] + desc_targets

        seen_desc = set()
        for target in desc_targets:
            if not target or target in seen_desc:
                continue
            seen_desc.add(target)
            add_step(
                "descriptive_compare",
                {"target": target, "group": group_col},
                name=f"Описательная статистика: {target}",
            )

    # Mixed effects for repeated measures (long format)
    if group_col and time_col and subject_col and outcomes:
        add_step(
            "mixed_effects",
            {
                "outcome": primary_numeric or outcomes[0],
                "time": time_col,
                "group": group_col,
                "subject": subject_col,
                "covariates": predictors[:max_predictors],
            },
            name="Смешанные эффекты (Time×Group)",
        )

    # Wide repeated measures
    for group_item in endpoint_groups:
        cols = _safe_list(group_item.get("columns"))
        if len(cols) < 2:
            continue
        ok_flags = []
        for c in cols:
            meta = columns_meta.get(c, {})
            ok = _normality_ok(meta)
            if ok is not None:
                ok_flags.append(bool(ok))
        all_normal = all(ok_flags) if ok_flags else True
        if len(cols) == 2:
            baseline, follow = cols[0], cols[1]
            paired_method = "t_test_rel" if all_normal else "wilcoxon"
            if paired_added < max_paired:
                add_step(
                    "paired_wide",
                    {
                        "baseline": baseline,
                        "follow": follow,
                        "method": paired_method,
                    },
                    name=f"Парный тест: {group_item.get('endpoint')}",
                )
                paired_added += 1
            if group_col:
                delta_pairs.append(
                    {
                        "baseline": baseline,
                        "follow": follow,
                        "label": group_item.get("endpoint") or baseline,
                    }
                )
            continue

        method_id = "rm_anova" if (all_normal and subject_col) else "friedman"
        cfg = {"outcome_cols": cols[:max_targets]}
        if method_id == "rm_anova" and subject_col:
            cfg["subject_col"] = subject_col
        if group_col:
            cfg["group_col"] = group_col
        add_step(method_id, cfg, name=f"Повторные измерения: {group_item.get('endpoint')}")

    if group_col and delta_pairs:
        add_step(
            "delta_batch_analysis",
            {
                "group": group_col,
                "pairs": delta_pairs[:max_targets],
                "method_id": "auto",
                "auto_fallback": True,
                "multiplicity_correction": multiplicity,
                "post_hoc": post_hoc,
                "post_hoc_correction": post_hoc_correction,
            },
            name="Δ сравнение групп (V1→V2)",
        )

    # Batch analysis for numeric outcomes vs group (chunked)
    if group_col and outcomes:
        group_meta = columns_meta.get(group_col, {}) if isinstance(columns_meta, dict) else {}
        unique = _unique_count(group_meta) or 2
        # Heuristic: choose param/nonparam based on normality across outcomes
        normal_flags = []
        for col in outcomes[:max_targets]:
            meta = columns_meta.get(col, {})
            ok = _normality_ok(meta)
            if ok is not None:
                normal_flags.append(bool(ok))
        normal_ratio = sum(normal_flags) / max(1, len(normal_flags)) if normal_flags else 1.0
        if unique <= 2:
            method_id = "t_test_ind" if normal_ratio >= 0.6 else "mann_whitney"
        else:
            method_id = "anova" if normal_ratio >= 0.6 else "kruskal"

        numeric_chunks = _chunk_list(outcomes, batch_chunk_size)
        if max_batch_chunks:
            numeric_chunks = numeric_chunks[:max_batch_chunks]
        total_chunks = len(numeric_chunks)
        for idx, chunk in enumerate(numeric_chunks, start=1):
            if len(steps) >= max_steps:
                break
            cfg = {
                "group": group_col,
                "targets": chunk,
                "method_id": method_id,
                "auto_fallback": True,
                "multiplicity_correction": multiplicity,
            }
            if unique > 2:
                cfg["post_hoc"] = post_hoc
                cfg["post_hoc_correction"] = post_hoc_correction
            label = "Сравнение групп (numeric)"
            if total_chunks > 1:
                label = f"{label} {idx}/{total_chunks}"
            add_step("batch_analysis", cfg, name=label)

    # Subgroup analyses (additional categorical stratifiers)
    comorbidity_groups: List[str] = []
    treatment_groups: List[str] = []
    if is_comprehensive:
        exclude_for_keywords = [group_col, time_col, subject_col, primary_binary]
        comorbidity_groups = _pick_keyword_subgroups(
            categorical_cols,
            columns_meta,
            exclude=exclude_for_keywords,
            keywords=COMORBIDITY_KEYWORDS,
            max_groups=2,
            max_unique=10,
        )
        treatment_groups = _pick_keyword_subgroups(
            categorical_cols,
            columns_meta,
            exclude=exclude_for_keywords,
            keywords=TREATMENT_KEYWORDS,
            max_groups=2,
            max_unique=12,
        )

    subgroup_cols: List[str] = []
    pref_subgroups = prefs.get("subgroup_columns")
    if isinstance(pref_subgroups, list):
        subgroup_cols = [str(v) for v in pref_subgroups if isinstance(v, (str, int, float)) and str(v).strip()]
    elif isinstance(pref_subgroups, (str, int, float)):
        subgroup_cols = [s.strip() for s in str(pref_subgroups).split(",") if s.strip()]

    if not subgroup_cols and exploratory:
        subgroup_cols = _pick_subgroup_columns(
            categorical_cols,
            columns_meta,
            exclude=[group_col, time_col, subject_col, primary_binary],
            max_groups=2,
            max_unique=8,
        )
    if comorbidity_groups or treatment_groups:
        subgroup_cols = list(dict.fromkeys([*comorbidity_groups, *treatment_groups, *subgroup_cols]))

    if subgroup_cols and outcomes:
        max_subgroup_targets = min(max_targets, 30)
        for sg in subgroup_cols:
            if sg == group_col or not sg:
                continue
            if sg not in columns_meta:
                continue
            sg_meta = columns_meta.get(sg, {})
            unique = _unique_count(sg_meta) or 2
            normal_flags = []
            for col in outcomes[:max_subgroup_targets]:
                meta = columns_meta.get(col, {})
                ok = _normality_ok(meta)
                if ok is not None:
                    normal_flags.append(bool(ok))
            normal_ratio = sum(normal_flags) / max(1, len(normal_flags)) if normal_flags else 1.0
            if unique <= 2:
                method_id = "t_test_ind" if normal_ratio >= 0.6 else "mann_whitney"
            else:
                method_id = "anova" if normal_ratio >= 0.6 else "kruskal"
            cfg = {
                "group": sg,
                "targets": outcomes[:max_subgroup_targets],
                "method_id": method_id,
                "auto_fallback": True,
                "multiplicity_correction": multiplicity,
            }
            if unique > 2:
                cfg["post_hoc"] = post_hoc
                cfg["post_hoc_correction"] = post_hoc_correction
            add_step("batch_analysis", cfg, name=f"Подгруппы: {sg}")

            if group_col and primary_numeric:
                add_step(
                    "anova_twoway",
                    {
                        "outcome": primary_numeric,
                        "group1": group_col,
                        "group2": sg,
                    },
                    name=f"Взаимодействие: {group_col} × {sg}",
                )

    # Batch analysis for categorical outcomes vs group (chunked)
    if group_col and categorical_outcomes:
        cat_chunks = _chunk_list(categorical_outcomes, batch_chunk_size)
        if max_batch_chunks:
            cat_chunks = cat_chunks[:max_batch_chunks]
        total_chunks = len(cat_chunks)
        for idx, chunk in enumerate(cat_chunks, start=1):
            if len(steps) >= max_steps:
                break
            label = "Ассоциации категориальных показателей"
            if total_chunks > 1:
                label = f"{label} {idx}/{total_chunks}"
            add_step(
                "batch_analysis",
                {
                    "group": group_col,
                    "targets": chunk,
                    "method_id": "chi_square",
                    "auto_fallback": True,
                    "multiplicity_correction": multiplicity,
                },
                name=label,
            )

    # Timepoint batch analysis (long format)
    if group_col and time_col and outcomes:
        add_step(
            "timepoint_batch_analysis",
            {
                "split_by": time_col,
                "group": group_col,
                "targets": outcomes[:max_targets],
                "method_id": "kruskal",
                "auto_fallback": True,
                "multiplicity_correction": multiplicity,
                "post_hoc": post_hoc,
                "post_hoc_correction": post_hoc_correction,
            },
            name="Сравнение по визитам (batch)",
        )

    # Correlation mining
    if len(numeric_cols) >= 3:
        add_step(
            "clustered_correlation",
            {
                "variables": numeric_cols[:max_corr_vars],
                "method": "spearman",
                "linkage_method": "ward",
                "show_p_values": True,
            },
            name="Кластерная корреляция",
        )
    elif len(numeric_cols) >= 2:
        add_step(
            "spearman",
            {"outcome": numeric_cols[0], "group": numeric_cols[1]},
            name="Корреляция",
        )

    # Regression
    if predictors and outcomes:
        target_numeric = primary_numeric or outcomes[0]
        reg_preds = [p for p in predictors if p != target_numeric]
        if reg_preds:
            add_step(
                "linear_regression",
                {
                    "outcome": target_numeric,
                    "predictors": reg_preds[:max_predictors],
                    "covariates": [],
                    "show_or": True,
                    "show_roc": False,
                },
                name="Регрессия (линейная)",
            )

    # Logistic regression / ROC for binary outcomes
    if primary_binary and predictors:
        target = primary_binary
        log_preds = [p for p in predictors if p != target]
        if log_preds:
            config = {
                "outcome": target,
                "predictors": log_preds[:max_predictors],
                "covariates": [],
                "show_or": True,
                "show_roc": True,
            }
            if primary_binary_ovr and primary_binary_label:
                config["one_vs_rest"] = True
                config["positive_label"] = primary_binary_label
            add_step(
                "logistic_regression",
                config,
                name="Регрессия (логистическая)",
            )

            if is_expert:
                ml_common = {
                    "outcome": target,
                    "predictors": log_preds[:max_predictors],
                    "task": "classification",
                    "test_size": 0.25,
                    "random_state": 42,
                }
                if primary_binary_ovr and primary_binary_label:
                    ml_common["positive_label"] = primary_binary_label
                add_step("random_forest", dict(ml_common), name="ML-бенчмарк: Random Forest (classification)")
                add_step("gradient_boosting", dict(ml_common), name="ML-бенчмарк: Gradient Boosting (classification)")
        roc_pred = None
        for col in numeric_cols:
            if col != target:
                roc_pred = col
                break
        if roc_pred and not primary_binary_ovr:
            add_step(
                "roc_analysis",
                {"outcome": roc_pred, "group": target},
                name="ROC-анализ",
            )

    if is_expert and predictors and outcomes:
        target_numeric = primary_numeric or outcomes[0]
        reg_preds = [p for p in predictors if p != target_numeric]
        if reg_preds:
            ml_common = {
                "outcome": target_numeric,
                "predictors": reg_preds[:max_predictors],
                "task": "regression",
                "test_size": 0.25,
                "random_state": 42,
            }
            add_step("random_forest", dict(ml_common), name="ML-бенчмарк: Random Forest (regression)")
            add_step("gradient_boosting", dict(ml_common), name="ML-бенчмарк: Gradient Boosting (regression)")

    # P2: bootstrap stability pipeline for primary group effect
    if is_expert and group_col and primary_numeric:
        group_meta = columns_meta.get(group_col, {}) if isinstance(columns_meta, dict) else {}
        group_unique = _unique_count(group_meta)
        if group_unique == 2:
            add_step(
                "bootstrap_pipeline",
                {
                    "outcome": primary_numeric,
                    "group": group_col,
                    "statistic": "mean_difference",
                    "n_resamples": 2000,
                    "ci_level": 0.95,
                    "random_state": 42,
                },
                name="Bootstrap-устойчивость основного эффекта",
            )

    # P2: clustering profiles (patient-level unsupervised segmentation)
    if is_expert and len(numeric_cols) >= 4:
        cluster_vars = [c for c in numeric_cols if c not in {group_col, time_col, subject_col}]
        cluster_vars = cluster_vars[: max(4, min(max_corr_vars, 18))]
        if len(cluster_vars) >= 4:
            add_step(
                "cluster_profiles",
                {
                    "variables": cluster_vars,
                    "n_clusters": None,
                    "scale": True,
                    "random_state": 42,
                },
                name="Профили кластеров пациентов",
            )

    # P2: optional external validation dataset if user provided it explicitly
    external_validation_dataset_id = str(
        prefs.get("external_validation_dataset_id")
        or prefs.get("validation_dataset_id")
        or analysis_policy.get("external_validation_dataset_id")
        or ""
    ).strip()
    if is_expert and external_validation_dataset_id and predictors:
        if primary_binary:
            ext_target = primary_binary
            ext_predictors = [p for p in predictors if p != ext_target][:max_predictors]
            if ext_predictors:
                ext_cfg = {
                    "outcome": ext_target,
                    "predictors": ext_predictors,
                    "task": "classification",
                    "model_method": "logistic_regression",
                    "external_dataset_id": external_validation_dataset_id,
                    "test_size": 0.25,
                    "random_state": 42,
                }
                if primary_binary_ovr and primary_binary_label:
                    ext_cfg["positive_label"] = primary_binary_label
                add_step(
                    "external_validation",
                    ext_cfg,
                    name="Внешняя валидация модели исхода",
                )
        elif primary_numeric:
            ext_target = primary_numeric
            ext_predictors = [p for p in predictors if p != ext_target][:max_predictors]
            if ext_predictors:
                add_step(
                    "external_validation",
                    {
                        "outcome": ext_target,
                        "predictors": ext_predictors,
                        "task": "regression",
                        "model_method": "linear_regression",
                        "external_dataset_id": external_validation_dataset_id,
                        "test_size": 0.25,
                        "random_state": 42,
                    },
                    name="Внешняя валидация регрессионной модели",
                )

    # Coverage enforcer (add missing outcomes if budget allows)
    def _collect_covered(step_list: List[Dict[str, Any]]) -> set:
        covered = set()
        for step in step_list:
            if not isinstance(step, dict):
                continue
            cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
            for key in ("outcome", "target", "group", "group1", "group2", "baseline", "follow"):
                val = cfg.get(key)
                if isinstance(val, str):
                    covered.add(val)
            for key in ("targets", "outcome_cols", "outcome_columns", "variables"):
                vals = cfg.get(key)
                if isinstance(vals, list):
                    for v in vals:
                        if isinstance(v, str):
                            covered.add(v)
        return covered

    if group_col:
        covered = _collect_covered(steps)
        missing_numeric = [c for c in outcomes if c not in covered]
        missing_categorical = [c for c in categorical_outcomes if c not in covered]

        if missing_numeric and len(steps) < max_steps:
            chunks = _chunk_list(missing_numeric, batch_chunk_size)
            if max_batch_chunks:
                chunks = chunks[:max_batch_chunks]
            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                if len(steps) >= max_steps:
                    break
                label = "Coverage: numeric outcomes"
                if total_chunks > 1:
                    label = f"{label} {idx}/{total_chunks}"
                add_step(
                    "batch_analysis",
                    {
                        "group": group_col,
                        "targets": chunk,
                        "method_id": "auto",
                        "auto_fallback": True,
                        "multiplicity_correction": multiplicity,
                    },
                    name=label,
                )

        if missing_categorical and len(steps) < max_steps:
            chunks = _chunk_list(missing_categorical, batch_chunk_size)
            if max_batch_chunks:
                chunks = chunks[:max_batch_chunks]
            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                if len(steps) >= max_steps:
                    break
                label = "Coverage: categorical outcomes"
                if total_chunks > 1:
                    label = f"{label} {idx}/{total_chunks}"
                add_step(
                    "batch_analysis",
                    {
                        "group": group_col,
                        "targets": chunk,
                        "method_id": "chi_square",
                        "auto_fallback": True,
                        "multiplicity_correction": multiplicity,
                    },
                    name=label,
                )

    constraints_local = dict(constraints or {})
    constraints_local["max_steps"] = max_steps
    steps = _dedupe_protocol(steps, max_steps=max_steps)
    steps = enforce_protocol_constraints(steps, constraints_local)

    target_outcomes = list(dict.fromkeys([*outcomes, *categorical_outcomes]))
    covered_cols = _collect_covered(steps)
    covered_outcomes = [c for c in target_outcomes if c in covered_cols]
    missing_outcomes = [c for c in target_outcomes if c not in covered_cols]
    coverage_ratio = (len(covered_outcomes) / float(max(1, len(target_outcomes)))) if target_outcomes else 1.0
    method_set = {str(step.get("method") or "").strip() for step in steps if isinstance(step, dict)}

    def _group_branch_covered(groups: List[str]) -> bool:
        if not groups:
            return True
        expected = set(groups)
        covered_groups: set = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            method_id = str(step.get("method") or "").strip()
            cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
            if method_id == "batch_analysis":
                grp = cfg.get("group")
                if isinstance(grp, str) and grp in expected:
                    covered_groups.add(grp)
            elif method_id == "anova_twoway":
                grp2 = cfg.get("group2")
                if isinstance(grp2, str) and grp2 in expected:
                    covered_groups.add(grp2)
        return len(covered_groups) >= len(expected)

    dynamics_required = bool(time_col or endpoint_groups)
    dynamics_covered = (not dynamics_required) or bool(
        method_set.intersection(
            {"mixed_effects", "timepoint_batch_analysis", "paired_wide", "delta_batch_analysis", "rm_anova", "friedman"}
        )
    )
    clinical_branches = {
        "outcomes": bool(target_outcomes),
        "dynamics": bool(dynamics_covered),
        "comorbidity": bool(_group_branch_covered(comorbidity_groups)),
        "treatment": bool(_group_branch_covered(treatment_groups)),
        "required": {
            "dynamics": bool(dynamics_required),
            "comorbidity": bool(comorbidity_groups),
            "treatment": bool(treatment_groups),
        },
    }
    branches_ok = True
    if is_comprehensive:
        branches_ok = (
            (not dynamics_required or clinical_branches["dynamics"])
            and (not comorbidity_groups or clinical_branches["comorbidity"])
            and (not treatment_groups or clinical_branches["treatment"])
        )

    coverage_report = {
        "target_total": int(len(target_outcomes)),
        "covered_total": int(len(covered_outcomes)),
        "coverage_ratio": float(round(coverage_ratio, 4)),
        "covered_outcomes": covered_outcomes[:200],
        "missing_outcomes": missing_outcomes[:200],
        "max_steps": int(max_steps),
        "steps_built": int(len(steps)),
        "clinical_branches": clinical_branches,
        "status": "ok" if coverage_ratio >= 0.95 and branches_ok else "partial",
    }
    if coverage_ratio < 0.95 and target_outcomes:
        notes_msg = (
            f"Coverage ниже целевого порога: {len(covered_outcomes)}/{len(target_outcomes)} "
            f"({coverage_ratio:.1%}). Увеличьте max_steps/max_batch_chunks или используйте discovery/comprehensive/publication/expert_comprehensive."
        )
    elif is_comprehensive and not branches_ok:
        notes_msg = (
            "Coverage outcomes достаточный, но не все обязательные clinical ветки закрыты "
            "(comorbidity/treatment/dynamics). Проверьте design и лимиты планировщика."
        )
    else:
        notes_msg = "Coverage целевых outcomes в пределах целевого порога."

    return {
        "protocol_name": "Exploratory protocol",
        "globals": globals_out,
        "protocol": steps,
        "notes": ["Сформирован rules-based протокол с расширенным анализом.", notes_msg],
        "coverage_report": coverage_report,
    }
