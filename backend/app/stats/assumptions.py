from typing import Any, Dict, List, Optional

import numpy as np
import warnings
from scipy import stats


def _clean_numeric(values: List[Any]) -> np.ndarray:
    out: List[float] = []
    for x in values:
        try:
            xf = float(x)
            if np.isfinite(xf):
                out.append(xf)
        except Exception:
            continue
    return np.array(out, dtype=float)


def _is_near_constant(values: np.ndarray, *, atol: float = 1e-12, rtol: float = 1e-9) -> bool:
    if values.size < 2:
        return True
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return True
    min_v = float(np.min(finite))
    max_v = float(np.max(finite))
    spread = abs(max_v - min_v)
    scale = max(abs(min_v), abs(max_v), 1.0)
    return bool(spread <= (atol + rtol * scale))


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
        if np.isfinite(out):
            return out
        return None
    except Exception:
        return None


def _to_list(values: Any) -> List[Any]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, np.ndarray)):
        return list(values)
    try:
        return list(values)
    except Exception:
        return []


def check_normality(
    data,
    alpha: float = 0.05,
    method: str = "shapiro",
    decision: str = "majority",
) -> Dict[str, Any]:
    clean = _clean_numeric(_to_list(data))
    n = int(clean.shape[0])
    tests: Dict[str, Dict[str, Any]] = {}
    near_constant = _is_near_constant(clean) if n >= 3 else False

    if 3 <= n <= 5000:
        if near_constant:
            tests["shapiro"] = {"stat": None, "p": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    stat, p = stats.shapiro(clean)
                stat_f = _finite_float(stat)
                p_f = _finite_float(p)
                if stat_f is None or p_f is None:
                    raise ValueError("non-finite shapiro")
                tests["shapiro"] = {"stat": stat_f, "p": p_f, "passed": bool(p_f > alpha)}
            except Exception:
                tests["shapiro"] = {"stat": None, "p": None, "passed": None}
    else:
        tests["shapiro"] = {"stat": None, "p": None, "passed": None}

    if n >= 8:
        if near_constant:
            tests["dagostino"] = {"stat": None, "p": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    stat, p = stats.normaltest(clean)
                stat_f = _finite_float(stat)
                p_f = _finite_float(p)
                if stat_f is None or p_f is None:
                    raise ValueError("non-finite normaltest")
                tests["dagostino"] = {"stat": stat_f, "p": p_f, "passed": bool(p_f > alpha)}
            except Exception:
                tests["dagostino"] = {"stat": None, "p": None, "passed": None}
    else:
        tests["dagostino"] = {"stat": None, "p": None, "passed": None}

    if n >= 8:
        if near_constant:
            tests["anderson"] = {"stat": None, "critical_5": None, "p": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ad = stats.anderson(clean, dist="norm")
                levels = [float(v) for v in list(getattr(ad, "significance_level", []))]
                crits = [float(v) for v in list(getattr(ad, "critical_values", []))]
                crit_5: Optional[float] = None
                if levels and crits and len(levels) == len(crits):
                    for lvl, crit in zip(levels, crits):
                        if abs(float(lvl) - 5.0) < 1e-9:
                            crit_5 = float(crit)
                            break
                    if crit_5 is None:
                        idx = int(np.argmin(np.abs(np.array(levels) - 5.0)))
                        crit_5 = float(crits[idx])
                stat = _finite_float(getattr(ad, "statistic", None))
                passed = bool(stat < crit_5) if (stat is not None and crit_5 is not None) else None
                tests["anderson"] = {"stat": stat, "critical_5": crit_5, "p": None, "passed": passed}
            except Exception:
                tests["anderson"] = {"stat": None, "critical_5": None, "p": None, "passed": None}
    else:
        tests["anderson"] = {"stat": None, "critical_5": None, "p": None, "passed": None}

    if n >= 20:
        if near_constant:
            tests["ks"] = {"stat": None, "p": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                sigma = float(np.std(clean, ddof=1))
                if np.isfinite(sigma) and sigma > 0:
                    z = (clean - float(np.mean(clean))) / sigma
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        stat, p = stats.kstest(z, "norm")
                    stat_f = _finite_float(stat)
                    p_f = _finite_float(p)
                    if stat_f is None or p_f is None:
                        raise ValueError("non-finite ks")
                    tests["ks"] = {"stat": stat_f, "p": p_f, "passed": bool(p_f > alpha)}
                else:
                    tests["ks"] = {"stat": None, "p": None, "passed": None}
            except Exception:
                tests["ks"] = {"stat": None, "p": None, "passed": None}
    else:
        tests["ks"] = {"stat": None, "p": None, "passed": None}

    test_mode = str(method or "shapiro").strip().lower()
    aliases = {
        "dagostino-pearson": "dagostino",
        "normaltest": "dagostino",
        "kolmogorov-smirnov": "ks",
        "kolmogorov_smirnov": "ks",
        "kstest": "ks",
        "all": "suite",
    }
    test_mode = aliases.get(test_mode, test_mode)

    if test_mode in {"suite", "multi"}:
        selected = [k for k in ("shapiro", "dagostino", "anderson", "ks") if tests.get(k, {}).get("passed") is not None]
    elif test_mode == "auto":
        selected = []
        for k in ("shapiro", "dagostino", "ks", "anderson"):
            if tests.get(k, {}).get("passed") is not None:
                selected = [k]
                break
    elif test_mode in {"shapiro", "dagostino", "anderson", "ks"}:
        selected = [test_mode]
    else:
        selected = [k for k in ("shapiro", "dagostino", "anderson", "ks") if tests.get(k, {}).get("passed") is not None]

    if not selected:
        return {
            "test": "shapiro",
            "stat": None,
            "p": None,
            "passed": None,
            "n": n,
            "selected_tests": [],
            "decision_rule": "single",
            "tests": tests,
        }

    passes = [tests[k]["passed"] for k in selected if tests.get(k, {}).get("passed") is not None]
    decision_mode = str(decision or "majority").strip().lower()
    if decision_mode == "strict":
        decision_mode = "all"
    if decision_mode == "lenient":
        decision_mode = "any"
    if len(selected) == 1:
        passed = passes[0] if passes else None
        decision_mode = "single"
    elif decision_mode == "all":
        passed = all(passes) if passes else None
    elif decision_mode == "any":
        passed = any(passes) if passes else None
    else:
        decision_mode = "majority"
        passed = bool(sum(1 for p in passes if p) >= int(np.ceil(len(passes) / 2.0))) if passes else None

    primary = selected[0]
    payload = tests.get(primary, {})
    p_val = payload.get("p")
    return {
        "test": primary,
        "stat": round(float(payload.get("stat")), 4) if isinstance(payload.get("stat"), (int, float)) else None,
        "p": round(float(p_val), 4) if isinstance(p_val, (int, float)) else None,
        "passed": bool(passed) if isinstance(passed, bool) else None,
        "n": n,
        "selected_tests": selected,
        "decision_rule": decision_mode,
        "tests": tests,
    }


def check_homogeneity(
    groups: List,
    alpha: float = 0.05,
    method: str = "levene",
    center: str = "median",
) -> Dict[str, Any]:
    clean = [_clean_numeric(_to_list(g)) for g in groups]
    if any(len(g) < 2 for g in clean):
        return {"test": "levene", "passed": None}

    method_name = str(method or "levene").strip().lower()
    if method_name in {"brown_forsythe", "brown-forsythe"}:
        method_name = "levene"

    try:
        if method_name == "bartlett":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                stat, p = stats.bartlett(*clean)
            return {"test": "bartlett", "stat": round(float(stat), 4), "p": round(float(p), 4), "passed": bool(p > alpha)}
        if method_name == "fligner":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                stat, p = stats.fligner(*clean)
            return {"test": "fligner", "stat": round(float(stat), 4), "p": round(float(p), 4), "passed": bool(p > alpha)}
        center_name = str(center or "median").strip().lower()
        if center_name not in {"mean", "median", "trimmed"}:
            center_name = "median"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            stat, p = stats.levene(*clean, center=center_name)
        return {
            "test": "levene",
            "center": center_name,
            "stat": round(float(stat), 4),
            "p": round(float(p), 4),
            "passed": bool(p > alpha),
        }
    except Exception:
        return {"test": method_name or "levene", "passed": None}


def recommend_test(n_groups: int, paired: bool, norm_ok: bool, homo_ok: bool) -> str:
    if n_groups == 2:
        if paired:
            return "wilcoxon" if not norm_ok else "t_test_rel"
        if norm_ok and homo_ok:
            return "t_test_ind"
        return "mann_whitney" if not norm_ok else "t_test_welch"
    if paired:
        return "friedman" if not norm_ok else "rm_anova"
    return "kruskal" if not norm_ok else "anova"
