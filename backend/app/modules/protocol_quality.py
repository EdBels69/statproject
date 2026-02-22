from typing import Any, Dict, List, Optional, Set

from app.modules.protocol_rules import SUPPORTED_METHODS_V2, METHOD_REQUIRED_FIELDS


def _safe_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
    if isinstance(value, (str, int, float)):
        v = str(value).strip()
        return [v] if v else []
    return []


def _column_set(scan_report: Optional[Dict[str, Any]]) -> Set[str]:
    if not isinstance(scan_report, dict):
        return set()
    cols = scan_report.get("columns")
    if not isinstance(cols, dict):
        return set()
    return {str(c) for c in cols.keys()}


def _collect_outcomes(study_design: Optional[Dict[str, Any]], scan_report: Optional[Dict[str, Any]]) -> List[str]:
    if isinstance(study_design, dict):
        design = study_design.get("design") if isinstance(study_design.get("design"), dict) else {}
        outcomes = _safe_list(design.get("outcomes"))
        outcomes += _safe_list(design.get("categorical_outcomes"))
        if outcomes:
            return list(dict.fromkeys(outcomes))

    if not isinstance(scan_report, dict):
        return []
    cols = scan_report.get("columns")
    if not isinstance(cols, dict):
        return []
    out: List[str] = []
    for name, meta in cols.items():
        if not isinstance(meta, dict):
            continue
        t = str(meta.get("type") or "").lower()
        if any(k in t for k in ["int", "float", "double", "number", "category", "object", "bool"]):
            out.append(str(name))
    return list(dict.fromkeys(out))


def evaluate_protocol_quality(
    protocol: Optional[List[Dict[str, Any]]],
    study_design: Optional[Dict[str, Any]] = None,
    scan_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    steps = protocol if isinstance(protocol, list) else []
    total_steps = len(steps)
    if total_steps == 0:
        return {
            "score": 0.0,
            "valid_ratio": 0.0,
            "coverage_ratio": 0.0,
            "design_fit": 0.0,
            "redundancy_ratio": 0.0,
            "issues": ["protocol_empty"],
            "invalid_steps": [],
        }

    columns = _column_set(scan_report)
    outcomes = _collect_outcomes(study_design, scan_report)

    valid_steps = 0
    covered_outcomes: Set[str] = set()
    issues: List[str] = []
    invalid_steps: List[Dict[str, Any]] = []
    seen = set()
    dup_count = 0

    for step in steps:
        if not isinstance(step, dict):
            continue
        method = str(step.get("method") or "").strip()
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        key_base = f"{method}"
        if config.get("baseline") or config.get("follow"):
            key = f"{key_base}:{config.get('baseline')}->{config.get('follow')}"
        elif isinstance(config.get("pairs"), list) and config.get("pairs"):
            first = config.get("pairs")[0]
            if isinstance(first, dict):
                key = f"{key_base}:{first.get('baseline')}->{first.get('follow')}"
            else:
                key = f"{key_base}:pairs"
        else:
            if config.get("group1") or config.get("group2"):
                key = f"{key_base}:{config.get('outcome') or config.get('target')}:{config.get('group1')}:{config.get('group2')}"
            else:
                key = f"{key_base}:{config.get('outcome') or config.get('target') or config.get('group')}"
        if key in seen:
            dup_count += 1
        else:
            seen.add(key)

        if method not in SUPPORTED_METHODS_V2:
            invalid_steps.append({"step": step, "error": "unsupported_method"})
            continue

        missing_fields = []
        for req in METHOD_REQUIRED_FIELDS.get(method, []):
            val = config.get(req)
            if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not val):
                missing_fields.append(req)

        if missing_fields:
            invalid_steps.append({"step": step, "error": f"missing:{','.join(missing_fields)}"})
            continue

        # Column existence checks
        col_fields = ["outcome", "target", "group", "group1", "group2", "time", "subject", "split_by", "baseline", "follow"]
        list_fields = ["targets", "outcome_cols", "outcome_columns", "variables", "predictors", "covariates"]
        missing_cols = []
        for field in col_fields:
            col = config.get(field)
            if isinstance(col, str) and columns and col not in columns:
                missing_cols.append(col)
        for field in list_fields:
            vals = config.get(field)
            if isinstance(vals, list):
                for v in vals:
                    if isinstance(v, str) and columns and v not in columns:
                        missing_cols.append(v)
        pairs = config.get("pairs")
        if isinstance(pairs, list):
            for item in pairs:
                if not isinstance(item, dict):
                    continue
                for key in ("baseline", "follow"):
                    val = item.get(key)
                    if isinstance(val, str) and columns and val not in columns:
                        missing_cols.append(val)

        if missing_cols:
            invalid_steps.append({"step": step, "error": f"missing_columns:{','.join(sorted(set(missing_cols)))}"})
            continue

        valid_steps += 1

        for field in ["outcome", "target"]:
            val = config.get(field)
            if isinstance(val, str):
                covered_outcomes.add(val)
        for field in ["targets", "outcome_cols", "outcome_columns", "variables"]:
            vals = config.get(field)
            if isinstance(vals, list):
                for v in vals:
                    if isinstance(v, str):
                        covered_outcomes.add(v)

    valid_ratio = valid_steps / float(max(1, total_steps))
    coverage_ratio = len(set(outcomes) & covered_outcomes) / float(max(1, len(outcomes))) if outcomes else 0.0

    design_fit = 1.0
    if isinstance(study_design, dict):
        design = study_design.get("design") if isinstance(study_design.get("design"), dict) else {}
        repeated = bool(design.get("repeated_measures"))
        if repeated:
            has_rm = any(
                isinstance(s, dict)
                and str(s.get("method"))
                in {"mixed_effects", "rm_anova", "friedman", "timepoint_batch_analysis", "paired_wide", "delta_batch_analysis"}
                for s in steps
            )
            design_fit = 1.0 if has_rm else 0.4

    redundancy_ratio = dup_count / float(max(1, total_steps))

    score = (
        0.4 * valid_ratio
        + 0.3 * coverage_ratio
        + 0.2 * design_fit
        + 0.1 * (1.0 - redundancy_ratio)
    ) * 100.0

    if invalid_steps:
        issues.append("invalid_steps")
    if coverage_ratio < 0.4:
        issues.append("low_coverage")
    if design_fit < 0.8:
        issues.append("design_mismatch")

    return {
        "score": round(score, 2),
        "valid_ratio": round(valid_ratio, 3),
        "coverage_ratio": round(coverage_ratio, 3),
        "design_fit": round(design_fit, 3),
        "redundancy_ratio": round(redundancy_ratio, 3),
        "issues": issues,
        "invalid_steps": invalid_steps,
    }
