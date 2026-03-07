from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import pingouin as pg
import warnings
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar
from statsmodels.stats.contingency_tables import cochrans_q as sm_cochrans_q
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller, acf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import roc_curve, auc, cohen_kappa_score
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA, FactorAnalysis
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from scipy.cluster.hierarchy import linkage as scipy_linkage, leaves_list
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from app.stats.registry import METHODS
from app.core.logging import logger

# Import new engines
from app.stats.mixed_effects import MixedEffectsEngine, RepeatedMeasuresEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine
from app.stats.assumptions import recommend_test

GROUP_TESTS = ["t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "anova", "anova_welch", "kruskal"]

def _recommend_group_test(group_count: int, is_paired: bool, normality_ok: bool, homogeneity_ok: bool) -> Optional[str]:
    if group_count < 2:
        return None

    rec = recommend_test(group_count, bool(is_paired), bool(normality_ok), bool(homogeneity_ok))
    if rec == "anova" and not homogeneity_ok:
        return "anova_welch"
    return rec

def _extract_ci_bounds(ci_value):
    if ci_value is None:
        return None, None

    if isinstance(ci_value, (list, tuple, np.ndarray)) and len(ci_value) == 2:
        try:
            return float(ci_value[0]), float(ci_value[1])
        except Exception:
            return None, None

    if isinstance(ci_value, str):
        import re

        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", ci_value)
        if len(nums) >= 2:
            try:
                return float(nums[0]), float(nums[1])
            except Exception:
                return None, None

    return None, None


def _bf10_from_p_value_bound(p_value: Any) -> Optional[float]:
    try:
        if p_value is None:
            return None
        p = float(p_value)
        if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
            return None
    except Exception:
        return None

    try:
        if p >= (1.0 / float(np.e)):
            return 1.0
        bf01_min = -float(np.e) * p * float(np.log(p))
        if not np.isfinite(bf01_min) or bf01_min <= 0.0:
            return None
        return float(1.0 / bf01_min)
    except Exception:
        return None


def _bf10_to_posterior_h1(bf10: Any) -> Optional[float]:
    try:
        bf = float(bf10)
    except Exception:
        return None
    if not np.isfinite(bf) or bf <= 0.0:
        return None
    return float(bf / (1.0 + bf))


def _bf10_evidence_label(bf10: Any) -> Dict[str, Any]:
    try:
        bf = float(bf10)
    except Exception:
        return {"label": "unknown", "label_ru": "неопределённо"}
    if not np.isfinite(bf) or bf <= 0.0:
        return {"label": "unknown", "label_ru": "неопределённо"}

    if bf >= 100:
        return {"label": "extreme_h1", "label_ru": "экстремальные в пользу H1"}
    if bf >= 30:
        return {"label": "very_strong_h1", "label_ru": "очень сильные в пользу H1"}
    if bf >= 10:
        return {"label": "strong_h1", "label_ru": "сильные в пользу H1"}
    if bf >= 3:
        return {"label": "moderate_h1", "label_ru": "умеренные в пользу H1"}
    if bf > (1.0 / 3.0):
        return {"label": "anecdotal", "label_ru": "слабые/неубедительные"}
    if bf > (1.0 / 10.0):
        return {"label": "moderate_h0", "label_ru": "умеренные в пользу H0"}
    if bf > (1.0 / 30.0):
        return {"label": "strong_h0", "label_ru": "сильные в пользу H0"}
    return {"label": "very_strong_h0", "label_ru": "очень сильные в пользу H0"}


def _augment_bayesian_payload(
    payload: Dict[str, Any],
    *,
    method_id: str,
    prior: str = "cauchy(0, 0.707)",
) -> Dict[str, Any]:
    out = dict(payload) if isinstance(payload, dict) else {}
    out["method"] = str(method_id)

    bf10 = out.get("bf10")
    try:
        bf10_val = float(bf10) if bf10 is not None else None
    except Exception:
        bf10_val = None
    if bf10_val is None or not np.isfinite(bf10_val) or bf10_val <= 0.0:
        bf10_val = _bf10_from_p_value_bound(out.get("p_value"))

    bf01_val = (1.0 / bf10_val) if isinstance(bf10_val, (int, float)) and bf10_val not in {0.0, -0.0} else None
    post_h1 = _bf10_to_posterior_h1(bf10_val)
    post_h0 = (1.0 - post_h1) if isinstance(post_h1, (int, float)) else None
    evidence = _bf10_evidence_label(bf10_val)

    out["bf10"] = float(bf10_val) if isinstance(bf10_val, (int, float)) and np.isfinite(float(bf10_val)) else None
    out["bf01"] = float(bf01_val) if isinstance(bf01_val, (int, float)) and np.isfinite(float(bf01_val)) else None
    out["posterior_prob_h1"] = float(post_h1) if isinstance(post_h1, (int, float)) and np.isfinite(float(post_h1)) else None
    out["posterior_prob_h0"] = float(post_h0) if isinstance(post_h0, (int, float)) and np.isfinite(float(post_h0)) else None
    out["bayes_evidence"] = evidence
    out["bayesian"] = {
        "prior": str(prior),
        "bf10": out.get("bf10"),
        "bf01": out.get("bf01"),
        "posterior_prob_h1": out.get("posterior_prob_h1"),
        "posterior_prob_h0": out.get("posterior_prob_h0"),
        "evidence": evidence,
    }

    if isinstance(out.get("bf10"), (int, float)):
        if out["bf10"] >= 3.0:
            out["bayes_decision"] = "supports_h1"
        elif out["bf10"] <= (1.0 / 3.0):
            out["bayes_decision"] = "supports_h0"
        else:
            out["bayes_decision"] = "inconclusive"
        out["significant"] = bool(out["bf10"] >= 3.0)
    return out


def _normalize_multiplicity_correction(correction: Any, default: str = "fdr_bh") -> str:
    corr = str(correction or "").strip().lower()
    if corr in {"", "default"}:
        corr = str(default or "fdr_bh").strip().lower() or "fdr_bh"
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


def _normalize_alternative(alternative: Any, default: str = "two-sided") -> str:
    alt = str(alternative or "").strip().lower()
    if alt in {"", "default"}:
        alt = str(default or "two-sided").strip().lower() or "two-sided"
    alt = alt.replace("_", "-")
    if alt in {"two-sided", "twosided", "two-tailed", "two tailed", "two-tail", "two tail", "two.sided", "two"}:
        return "two-sided"
    if alt in {"greater", "right", "gt", ">"}:
        return "greater"
    if alt in {"less", "left", "lt", "<"}:
        return "less"
    return "two-sided"


def _normalize_method_id(method_id: Any) -> str:
    method = str(method_id or "").strip().lower()
    if not method:
        return ""
    aliases = {
        "mixed_model": "mixed_effects",
        "fisher": "fisher_exact",
        "welch_t_test": "t_test_welch",
        "kruskal_wallis": "kruskal",
        "two_way_anova": "anova_twoway",
        "hierarchical": "hierarchical_clustering",
        "hierarchical_cluster": "hierarchical_clustering",
        "hclust": "hierarchical_clustering",
        "k_means": "kmeans",
        "factor_analysis": "efa",
        "exploratory_factor_analysis": "efa",
        "principal_component_analysis": "pca",
        "cohen_kappa": "cohens_kappa",
        "cronbach": "cronbach_alpha",
        "shapiro": "shapiro_wilk",
        "bland_altman_analysis": "bland_altman",
        "point-biserial": "point_biserial",
        "partial_corr": "partial_correlation",
        "cochranq": "cochran_q",
        "bayesian_t_test_one": "bayes_t_test_one",
        "bayesian_t_test_ind": "bayes_t_test_ind",
        "bayesian_t_test_rel": "bayes_t_test_rel",
        "bayesian_correlation": "bayes_correlation",
        "bayesian_anova": "bayes_anova",
        "bayesian_linear_regression": "bayes_linear_regression",
        "bayesian_chi_square": "bayes_chi_square",
        "bayes_regression": "bayes_linear_regression",
        "bayes_chisq": "bayes_chi_square",
        "bayes_corr": "bayes_correlation",
        "timeseries": "time_series_analysis",
        "time_series": "time_series_analysis",
    }
    return aliases.get(method, method)


def _apply_multiplicity_with_trace(
    p_values: List[Any],
    *,
    alpha: float = 0.05,
    correction: Any = "fdr_bh",
) -> Dict[str, Any]:
    method = _normalize_multiplicity_correction(correction, default="fdr_bh")
    adjusted: List[Optional[float]] = [None] * len(p_values)
    rejected: List[Optional[bool]] = [None] * len(p_values)

    valid_indices: List[int] = []
    valid_pvals: List[float] = []
    for i, p_raw in enumerate(p_values):
        try:
            p = float(p_raw)
            if not np.isfinite(p):
                continue
            valid_indices.append(i)
            valid_pvals.append(p)
        except Exception:
            continue

    if method == "none":
        for i in valid_indices:
            p = float(p_values[i])
            adjusted[i] = p
            rejected[i] = bool(p < alpha)
    elif valid_pvals:
        try:
            reject_arr, adj_arr, _, _ = multipletests(valid_pvals, alpha=alpha, method=method)
            for local_i, global_i in enumerate(valid_indices):
                adjusted[global_i] = float(adj_arr[local_i])
                rejected[global_i] = bool(reject_arr[local_i])
        except Exception:
            # Fallback to unadjusted if statsmodels rejects an unknown method.
            method = "none"
            for i in valid_indices:
                p = float(p_values[i])
                adjusted[i] = p
                rejected[i] = bool(p < alpha)

    trace = {
        "method": method,
        "alpha": float(alpha),
        "n_total": int(len(p_values)),
        "n_valid": int(len(valid_indices)),
        "valid_indices": valid_indices,
        "p_values_raw": [float(p) if i in valid_indices else None for i, p in enumerate(p_values)],
        "p_values_adj": adjusted,
        "reject": rejected,
    }
    return {"method": method, "adjusted": adjusted, "rejected": rejected, "trace": trace}


def _safe_bootstrap_samples(raw: Any, default: int = 1000) -> int:
    try:
        val = int(raw)
    except Exception:
        val = int(default)
    return max(100, min(100000, val))


def _cohen_d_from_arrays(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if x.size < 2 or y.size < 2:
        return None
    sx = float(np.std(x, ddof=1))
    sy = float(np.std(y, ddof=1))
    if not np.isfinite(sx) or not np.isfinite(sy):
        return None
    n1 = int(x.size)
    n2 = int(y.size)
    denom = float(np.sqrt((((n1 - 1) * sx * sx) + ((n2 - 1) * sy * sy)) / float(max(1, n1 + n2 - 2))))
    if not np.isfinite(denom) or denom == 0.0:
        return None
    return float((float(np.mean(x)) - float(np.mean(y))) / denom)


def _bootstrap_ci_two_sample(
    x: Any,
    y: Any,
    *,
    stat_fn,
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    x_arr = pd.to_numeric(pd.Series(x), errors="coerce").dropna().to_numpy(dtype=float)
    y_arr = pd.to_numeric(pd.Series(y), errors="coerce").dropna().to_numpy(dtype=float)
    if x_arr.size < 2 or y_arr.size < 2:
        return None

    rng = np.random.default_rng(int(random_state))
    vals: List[float] = []
    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    for _ in range(n_boot):
        idx_x = rng.integers(0, x_arr.size, size=x_arr.size)
        idx_y = rng.integers(0, y_arr.size, size=y_arr.size)
        try:
            v = stat_fn(x_arr[idx_x], y_arr[idx_y])
            if v is None:
                continue
            vf = float(v)
            if np.isfinite(vf):
                vals.append(vf)
        except Exception:
            continue

    if len(vals) < 10:
        return None

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    lo = float(np.percentile(vals, 100.0 * alpha_tail))
    hi = float(np.percentile(vals, 100.0 * (1.0 - alpha_tail)))
    return {
        "ci_level": float(ci_level),
        "samples": int(n_boot),
        "n_valid": int(len(vals)),
        "ci_lower": lo,
        "ci_upper": hi,
        "estimate": float(np.mean(vals)),
    }


def _bootstrap_ci_one_sample(
    x: Any,
    *,
    stat_fn,
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    x_arr = pd.to_numeric(pd.Series(x), errors="coerce").dropna().to_numpy(dtype=float)
    if x_arr.size < 3:
        return None

    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    rng = np.random.default_rng(int(random_state))
    vals: List[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, x_arr.size, size=x_arr.size)
        try:
            v = stat_fn(x_arr[idx])
            if v is None:
                continue
            vf = float(v)
            if np.isfinite(vf):
                vals.append(vf)
        except Exception:
            continue

    if len(vals) < 10:
        return None

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    lo = float(np.percentile(vals, 100.0 * alpha_tail))
    hi = float(np.percentile(vals, 100.0 * (1.0 - alpha_tail)))
    return {
        "ci_level": float(ci_level),
        "samples": int(n_boot),
        "n_valid": int(len(vals)),
        "ci_lower": lo,
        "ci_upper": hi,
        "estimate": float(np.mean(vals)),
    }


def _bootstrap_ci_paired(
    x: Any,
    y: Any,
    *,
    stat_fn,
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    pair = pd.DataFrame({"x": x, "y": y})
    pair["x"] = pd.to_numeric(pair["x"], errors="coerce")
    pair["y"] = pd.to_numeric(pair["y"], errors="coerce")
    pair = pair.dropna()
    if pair.shape[0] < 3:
        return None

    x_arr = pair["x"].to_numpy(dtype=float)
    y_arr = pair["y"].to_numpy(dtype=float)
    n = int(pair.shape[0])
    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    rng = np.random.default_rng(int(random_state))

    vals: List[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        try:
            v = stat_fn(x_arr[idx], y_arr[idx])
            if v is None:
                continue
            vf = float(v)
            if np.isfinite(vf):
                vals.append(vf)
        except Exception:
            continue

    if len(vals) < 10:
        return None

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    lo = float(np.percentile(vals, 100.0 * alpha_tail))
    hi = float(np.percentile(vals, 100.0 * (1.0 - alpha_tail)))
    return {
        "ci_level": float(ci_level),
        "samples": int(n_boot),
        "n_valid": int(len(vals)),
        "ci_lower": lo,
        "ci_upper": hi,
        "estimate": float(np.mean(vals)),
    }


def _bootstrap_ci_correlation(
    x: Any,
    y: Any,
    *,
    method: str = "pearson",
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    pair = pd.DataFrame({"x": x, "y": y})
    pair["x"] = pd.to_numeric(pair["x"], errors="coerce")
    pair["y"] = pd.to_numeric(pair["y"], errors="coerce")
    pair = pair.dropna()
    if pair.shape[0] < 4:
        return None

    x_arr = pair["x"].to_numpy(dtype=float)
    y_arr = pair["y"].to_numpy(dtype=float)
    n = int(x_arr.size)
    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    rng = np.random.default_rng(int(random_state))

    vals: List[float] = []
    method_norm = str(method or "pearson").strip().lower()
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        xb = x_arr[idx]
        yb = y_arr[idx]
        try:
            if method_norm == "spearman":
                v, _ = stats.spearmanr(xb, yb)
            elif method_norm == "kendall":
                v, _ = stats.kendalltau(xb, yb)
            else:
                v, _ = stats.pearsonr(xb, yb)
            vf = float(v)
            if np.isfinite(vf):
                vals.append(vf)
        except Exception:
            continue

    if len(vals) < 10:
        return None

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    lo = float(np.percentile(vals, 100.0 * alpha_tail))
    hi = float(np.percentile(vals, 100.0 * (1.0 - alpha_tail)))
    return {
        "ci_level": float(ci_level),
        "samples": int(n_boot),
        "n_valid": int(len(vals)),
        "ci_lower": lo,
        "ci_upper": hi,
        "estimate": float(np.mean(vals)),
    }


def _bootstrap_summary_from_values(
    values: Any,
    *,
    ci_level: float = 0.95,
    requested_samples: int = 1000,
) -> Optional[Dict[str, Any]]:
    if not isinstance(values, list):
        return None
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return None
    arr = arr[np.isfinite(arr)]
    if arr.size < 10:
        return None

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    lo = float(np.percentile(arr, 100.0 * alpha_tail))
    hi = float(np.percentile(arr, 100.0 * (1.0 - alpha_tail)))
    return {
        "ci_level": float(ci_level),
        "samples": int(requested_samples),
        "n_valid": int(arr.size),
        "ci_lower": lo,
        "ci_upper": hi,
        "estimate": float(np.mean(arr)),
    }


def _bootstrap_regression_payload(
    outcome: Any,
    X: pd.DataFrame,
    *,
    method_id: str,
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    if not isinstance(X, pd.DataFrame) or X.empty:
        return None

    y = pd.to_numeric(pd.Series(outcome), errors="coerce")
    if y.shape[0] != X.shape[0]:
        return None

    local = X.copy()
    local = local.replace([np.inf, -np.inf], np.nan)
    local.insert(0, "__y__", y.to_numpy())
    local = local.dropna()
    if local.shape[0] < max(10, int(X.shape[1]) + 3):
        return None

    y_arr = local["__y__"].to_numpy(dtype=float)
    X_df = local.drop(columns=["__y__"]).astype(float)
    if X_df.empty:
        return None

    n = int(local.shape[0])
    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    rng = np.random.default_rng(int(random_state))
    method = str(method_id or "").strip().lower()

    coef_samples: Dict[str, List[float]] = {str(col): [] for col in X_df.columns}
    r2_vals: List[float] = []
    valid_models = 0

    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yb = y_arr[idx]
        Xb = X_df.iloc[idx, :]

        try:
            if method == "logistic_regression":
                uniq = np.unique(yb[np.isfinite(yb)])
                if uniq.size != 2:
                    continue
                class_counts = pd.Series(yb).value_counts(dropna=True)
                if class_counts.empty or class_counts.min() < 2:
                    continue
                model_b = sm.Logit(yb, Xb).fit(disp=0)
                if hasattr(model_b, "prsquared"):
                    prs = float(model_b.prsquared)
                    if np.isfinite(prs):
                        r2_vals.append(prs)
            else:
                model_b = sm.OLS(yb, Xb).fit()
                if hasattr(model_b, "rsquared"):
                    rs = float(model_b.rsquared)
                    if np.isfinite(rs):
                        r2_vals.append(rs)

            params = model_b.params
            for name in coef_samples.keys():
                if name not in params.index:
                    continue
                val = float(params[name])
                if np.isfinite(val):
                    coef_samples[name].append(val)
            valid_models += 1
        except Exception:
            continue

    if valid_models < 10:
        return None

    coef_rows: List[Dict[str, Any]] = []
    for name, vals in coef_samples.items():
        summary = _bootstrap_summary_from_values(vals, ci_level=ci_level, requested_samples=n_boot)
        if not isinstance(summary, dict):
            continue
        row: Dict[str, Any] = {"variable": str(name), **summary}
        if method == "logistic_regression":
            try:
                row["or_estimate"] = float(np.exp(summary["estimate"]))
                row["or_ci_lower"] = float(np.exp(summary["ci_lower"]))
                row["or_ci_upper"] = float(np.exp(summary["ci_upper"]))
            except Exception:
                row["or_estimate"] = None
                row["or_ci_lower"] = None
                row["or_ci_upper"] = None
        coef_rows.append(row)

    metrics: Dict[str, Any] = {}
    if coef_rows:
        metrics["coefficients"] = coef_rows

    r2_summary = _bootstrap_summary_from_values(r2_vals, ci_level=ci_level, requested_samples=n_boot)
    if isinstance(r2_summary, dict):
        metrics["pseudo_r2" if method == "logistic_regression" else "r_squared"] = r2_summary

    return {
        "enabled": True,
        "samples": int(n_boot),
        "ci_level": float(ci_level),
        "method": "bootstrap_percentile",
        "n_valid_models": int(valid_models),
        "metrics": metrics,
    }


def _bootstrap_ancova_payload(
    local: pd.DataFrame,
    *,
    outcome: str,
    group: str,
    covars: List[str],
    n_boot: int = 1000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Optional[Dict[str, Any]]:
    if not isinstance(local, pd.DataFrame) or local.empty:
        return None
    if local.shape[0] < 10:
        return None

    n = int(local.shape[0])
    n_boot = _safe_bootstrap_samples(n_boot, default=1000)
    rng = np.random.default_rng(int(random_state))

    f_vals: List[float] = []
    p_vals: List[float] = []
    np2_vals: List[float] = []
    valid_models = 0

    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = local.iloc[idx, :].copy()
        try:
            anc = pg.ancova(data=sample, dv=outcome, between=group, covar=covars)
            row_group = anc[anc["Source"] == group]
            if row_group.empty:
                continue
            r = row_group.iloc[0]
            f_raw = r.get("F")
            p_raw = r.get("p-unc")
            np2_raw = r.get("np2")
            if f_raw is not None:
                f_val = float(f_raw)
                if np.isfinite(f_val):
                    f_vals.append(f_val)
            if p_raw is not None:
                p_val = float(p_raw)
                if np.isfinite(p_val):
                    p_vals.append(p_val)
            if np2_raw is not None:
                np2_val = float(np2_raw)
                if np.isfinite(np2_val):
                    np2_vals.append(np2_val)
            valid_models += 1
        except Exception:
            continue

    if valid_models < 10:
        return None

    metrics: Dict[str, Any] = {}
    f_summary = _bootstrap_summary_from_values(f_vals, ci_level=ci_level, requested_samples=n_boot)
    if isinstance(f_summary, dict):
        metrics["F"] = f_summary
    p_summary = _bootstrap_summary_from_values(p_vals, ci_level=ci_level, requested_samples=n_boot)
    if isinstance(p_summary, dict):
        metrics["p_value"] = p_summary
    np2_summary = _bootstrap_summary_from_values(np2_vals, ci_level=ci_level, requested_samples=n_boot)
    if isinstance(np2_summary, dict):
        metrics["effect_size"] = {**np2_summary, "name": "np2"}

    return {
        "enabled": True,
        "samples": int(n_boot),
        "ci_level": float(ci_level),
        "method": "bootstrap_percentile",
        "n_valid_models": int(valid_models),
        "metrics": metrics,
    }


def _varimax(loadings: np.ndarray, gamma: float = 1.0, q: int = 30, tol: float = 1e-6) -> np.ndarray:
    if not isinstance(loadings, np.ndarray) or loadings.ndim != 2:
        return loadings
    p, k = loadings.shape
    r = np.eye(k)
    d_old = 0.0
    for _ in range(int(q)):
        lam = np.dot(loadings, r)
        u, s, vh = np.linalg.svd(
            np.dot(
                loadings.T,
                np.power(lam, 3) - (gamma / float(max(1, p))) * np.dot(lam, np.diag(np.diag(np.dot(lam.T, lam)))),
            )
        )
        r = np.dot(u, vh)
        d = float(np.sum(s))
        if d_old != 0 and (d - d_old) < tol:
            break
        d_old = d
    return np.dot(loadings, r)


def interpret_effect_size(effect_size: float, effect_size_name: str) -> dict:
    """
    Interpret effect size with Cohen's thresholds.
    Returns dict with interpretation label and description.
    
    Thresholds based on Cohen (1988) and common conventions:
    - Cohen's d: 0.2 (small), 0.5 (medium), 0.8 (large)
    - Eta-squared/Partial η²: 0.01 (small), 0.06 (medium), 0.14 (large)
    - r/RBC: 0.1 (small), 0.3 (medium), 0.5 (large)
    - Cramér's V (df=1): 0.1 (small), 0.3 (medium), 0.5 (large)
    - Epsilon-squared: uses eta-squared thresholds
    """
    if effect_size is None or effect_size_name is None:
        return None
    
    abs_es = abs(effect_size)
    name_lower = effect_size_name.lower().replace("-", "_").replace(" ", "_")
    
    # Cohen's d and related (Hedges' g, Glass' delta)
    if name_lower in ["cohen_d", "cohens_d", "cohen", "hedges_g", "hedges", "glass_delta", "glass", "d"]:
        if abs_es < 0.2:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.5:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.8:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        es_label = "Cohen's d"
        if "hedges" in name_lower:
            es_label = "Hedges' g"
        elif "glass" in name_lower:
            es_label = "Glass's Δ"

        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.2, "medium": 0.5, "large": 0.8},
            "description": f"{es_label} = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"{es_label} = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Eta-squared, Partial eta-squared, Epsilon-squared
    elif name_lower in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2", "partial_eta_squared", "eps_sq", "epsilon_squared", "omega_squared", "omega2"]:
        if abs_es < 0.01:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.06:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.14:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        metric_name = "η²" if "eta" in name_lower else "ε²"
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.01, "medium": 0.06, "large": 0.14},
            "description": f"{metric_name} = {effect_size:.3f} indicates a {label} effect",
            "description_ru": f"{metric_name} = {effect_size:.3f} указывает на {label_ru} эффект"
        }
    
    # Correlation coefficient (r), Rank-biserial (RBC), Point-biserial
    elif name_lower in ["r", "rbc", "rank_biserial", "point_biserial", "phi", "spearman", "pearson", "kendall"]:
        if abs_es < 0.1:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.3:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.5:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.1, "medium": 0.3, "large": 0.5},
            "description": f"r = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"r = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Cramér's V
    elif name_lower in ["cramers_v", "cramer_v", "v"]:
        if abs_es < 0.1:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.3:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.5:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.1, "medium": 0.3, "large": 0.5},
            "description": f"Cramér's V = {effect_size:.2f} indicates a {label} association",
            "description_ru": f"Cramér's V = {effect_size:.2f} указывает на {label_ru} связь"
        }
    
    # Odds ratio (log scale interpretation)
    elif name_lower in ["odds_ratio", "or"]:
        # Odds ratio: 1.5 small, 2.5 medium, 4.3 large (Chen et al., 2010)
        if abs_es < 1.5:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 2.5:
            label = "small"
            label_ru = "малый"
        elif abs_es < 4.3:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 1.5, "medium": 2.5, "large": 4.3},
            "description": f"OR = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"OR = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Unknown effect size type - provide generic interpretation
    else:
        return {
            "label": "unknown",
            "label_ru": "неизвестный",
            "thresholds": None,
            "description": f"{effect_size_name} = {effect_size:.3f}",
            "description_ru": f"{effect_size_name} = {effect_size:.3f}"
        }



def compute_post_hoc_power(
    n1: int,
    n2: Optional[int] = None,
    effect_size: Optional[float] = None,
    alpha: float = 0.05,
    test_type: str = "two_sample",
) -> Optional[float]:
    """
    Compute observed (post-hoc) statistical power.

    Uses statsmodels power functions.
    Returns power (0-1) or None on failure.
    """
    try:
        if effect_size is None or n1 < 2:
            return None
        es = abs(float(effect_size))
        if es < 1e-10:
            return None

        if test_type in ("paired", "one_sample"):
            from statsmodels.stats.power import TTestPower

            power = TTestPower().power(
                effect_size=es,
                nobs=n1,
                alpha=alpha,
                alternative="two-sided",
            )
        elif test_type == "chi2":
            from statsmodels.stats.power import GofChisquarePower

            power = GofChisquarePower().power(
                effect_size=es,
                nobs=n1,
                alpha=alpha,
            )
        else:
            from statsmodels.stats.power import TTestIndPower

            n_eff = n2 if n2 and n2 > 1 else n1
            ratio = float(n_eff) / float(n1)
            power = TTestIndPower().power(
                effect_size=es,
                nobs1=n1,
                ratio=ratio,
                alpha=alpha,
                alternative="two-sided",
            )

        if power is not None:
            power = max(0.0, min(1.0, float(power)))
        return power
    except Exception:
        return None


def _format_posthoc_results(posthoc_df: pd.DataFrame, alpha: float) -> Optional[List[Dict[str, Any]]]:
    if posthoc_df is None or getattr(posthoc_df, "empty", True):
        return None

    out: List[Dict[str, Any]] = []
    for _, row in posthoc_df.iterrows():
        group1 = row.get("A", None)
        group2 = row.get("B", None)

        p_value = (
            row.get("p-tukey", None)
            if "p-tukey" in row
            else row.get("pval", None)
            if "pval" in row
            else row.get("p-unc", None)
            if "p-unc" in row
            else row.get("p-corr", None)
        )

        ci_lower, ci_upper = _extract_ci_bounds(row.get("CI95%", None))

        diff = row.get("diff", None)
        if diff is None and ("mean(A)" in row and "mean(B)" in row):
            try:
                diff = float(row["mean(A)"]) - float(row["mean(B)"])
            except Exception:
                diff = None

        try:
            p_value_f = float(p_value) if p_value is not None else None
        except Exception:
            p_value_f = None

        out.append(
            {
                "group1": str(group1) if group1 is not None else None,
                "group2": str(group2) if group2 is not None else None,
                "diff": float(diff) if diff is not None else None,
                "p_value": p_value_f,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "significant": (p_value_f < alpha) if p_value_f is not None else None,
            }
        )

    return out


def _apply_posthoc_correction(post_hoc: Optional[List[Dict[str, Any]]], alpha: float, correction: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(post_hoc, list) or not post_hoc:
        return post_hoc
    corr = _normalize_multiplicity_correction(correction, default="none")
    if corr == "none":
        return post_hoc

    pvals: List[Any] = []
    idxs: List[int] = []
    for i, r in enumerate(post_hoc):
        try:
            pvals.append(r.get("p_value"))
            idxs.append(i)
        except Exception:
            continue

    if not pvals:
        return post_hoc

    corr_res = _apply_multiplicity_with_trace(pvals, alpha=alpha, correction=corr)
    pvals_corrected = corr_res.get("adjusted") if isinstance(corr_res, dict) else None
    reject = corr_res.get("rejected") if isinstance(corr_res, dict) else None
    method = corr_res.get("method") if isinstance(corr_res, dict) else corr
    out = [dict(r) for r in post_hoc]
    for j, i in enumerate(idxs):
        adj = pvals_corrected[j] if isinstance(pvals_corrected, list) and j < len(pvals_corrected) else None
        sig = reject[j] if isinstance(reject, list) and j < len(reject) else None
        out[i]["p_value_adj"] = float(adj) if isinstance(adj, (int, float)) else None
        out[i]["significant_adj"] = bool(sig) if isinstance(sig, (bool, np.bool_)) else None
        out[i]["correction"] = method
    return out


def _run_dunn_posthoc(data_groups: List[pd.Series], groups: List[Any], alpha: float = 0.05) -> Optional[List[Dict[str, Any]]]:
    cleaned = []
    cleaned_groups = []
    for i, g in enumerate(groups):
        s = data_groups[i]
        if s is None:
            continue
        vals = pd.Series(s).dropna().to_numpy()
        if vals.size == 0:
            continue
        cleaned.append(vals)
        cleaned_groups.append(g)

    if len(cleaned) < 2:
        return None

    all_vals = np.concatenate(cleaned)
    labels = []
    for i, g in enumerate(cleaned_groups):
        labels.extend([g] * cleaned[i].size)
    labels = np.array(labels, dtype=object)

    n_total = int(all_vals.size)
    if n_total < 3:
        return None

    ranks = stats.rankdata(all_vals, method='average')

    _, counts = np.unique(all_vals, return_counts=True)
    tie_counts = counts[counts > 1]
    if tie_counts.size > 0:
        tie_sum = float(np.sum(np.power(tie_counts, 3) - tie_counts))
        denom = float(n_total ** 3 - n_total)
        tie_c = 1.0 - (tie_sum / denom if denom != 0 else 0.0)
    else:
        tie_c = 1.0

    base = (n_total * (n_total + 1) / 12.0) * tie_c
    if base <= 0:
        return None

    mean_ranks = {}
    ns = {}
    for g in cleaned_groups:
        mask = labels == g
        rg = ranks[mask]
        if rg.size == 0:
            continue
        mean_ranks[g] = float(np.mean(rg))
        ns[g] = int(rg.size)

    out: List[Dict[str, Any]] = []
    for i in range(len(cleaned_groups)):
        for j in range(i + 1, len(cleaned_groups)):
            a = cleaned_groups[i]
            b = cleaned_groups[j]
            na = ns.get(a, 0)
            nb = ns.get(b, 0)
            if na <= 0 or nb <= 0:
                continue
            se = np.sqrt(base * (1.0 / na + 1.0 / nb))
            if not np.isfinite(se) or se <= 0:
                continue
            z = (mean_ranks[a] - mean_ranks[b]) / se
            p = float(2.0 * stats.norm.sf(abs(float(z))))
            out.append(
                {
                    'group1': str(a),
                    'group2': str(b),
                    'diff': float(mean_ranks[a] - mean_ranks[b]),
                    'p_value': p,
                    'ci_lower': None,
                    'ci_upper': None,
                    'significant': bool(p < alpha),
                }
            )
    return out if out else None

def _clean_numeric_series(data: pd.Series) -> pd.Series:
    series = pd.to_numeric(data, errors="coerce")
    return series.replace([np.inf, -np.inf], np.nan).dropna()


def _finite_float_or_none(value: Any) -> Optional[float]:
    try:
        out = float(value)
        if np.isfinite(out):
            return out
        return None
    except Exception:
        return None


def _is_near_constant_array(values: np.ndarray, *, atol: float = 1e-12, rtol: float = 1e-9) -> bool:
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


def _call_pg_ttest(*args: Any, **kwargs: Any):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return pg.ttest(*args, **kwargs)


def _call_pg_wilcoxon(*args: Any, **kwargs: Any):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return pg.wilcoxon(*args, **kwargs)


def _call_pg_compute_effsize(*args: Any, **kwargs: Any) -> Optional[float]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return _finite_float_or_none(pg.compute_effsize(*args, **kwargs))


def check_normality_with_policy(
    data: pd.Series,
    *,
    normality_test: Optional[str] = "shapiro",
    alpha: float = 0.05,
    decision_rule: Optional[str] = "majority",
) -> Dict[str, Any]:
    clean_data = _clean_numeric_series(data)
    n = int(len(clean_data))
    out: Dict[str, Any] = {
        "n": n,
        "selected_tests": [],
        "decision_rule": None,
        "tests": {},
        "test": None,
        "stat": None,
        "p_value": None,
        "passed": None,
    }
    if n < 3:
        return out

    vals = clean_data.to_numpy(dtype=float)
    near_constant = _is_near_constant_array(vals)
    tests: Dict[str, Dict[str, Any]] = {}

    # Shapiro-Wilk: recommended for small/medium n (SciPy upper reliability note at n>5000).
    if 3 <= n <= 5000:
        if near_constant:
            tests["shapiro"] = {"stat": None, "p_value": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    stat, p_value = stats.shapiro(vals)
                stat_f = _finite_float_or_none(stat)
                p_f = _finite_float_or_none(p_value)
                if stat_f is None or p_f is None:
                    raise ValueError("non-finite shapiro output")
                tests["shapiro"] = {
                    "stat": stat_f,
                    "p_value": p_f,
                    "passed": bool(p_f > alpha),
                }
            except Exception:
                tests["shapiro"] = {"stat": None, "p_value": None, "passed": None}
    else:
        tests["shapiro"] = {"stat": None, "p_value": None, "passed": None}

    # D'Agostino-Pearson normaltest: n >= 8.
    if n >= 8:
        if near_constant:
            tests["dagostino"] = {"stat": None, "p_value": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    stat, p_value = stats.normaltest(vals)
                stat_f = _finite_float_or_none(stat)
                p_f = _finite_float_or_none(p_value)
                if stat_f is None or p_f is None:
                    raise ValueError("non-finite normaltest output")
                tests["dagostino"] = {
                    "stat": stat_f,
                    "p_value": p_f,
                    "passed": bool(p_f > alpha),
                }
            except Exception:
                tests["dagostino"] = {"stat": None, "p_value": None, "passed": None}
    else:
        tests["dagostino"] = {"stat": None, "p_value": None, "passed": None}

    # Anderson-Darling for normality (critical value at 5% level).
    if n >= 8:
        if near_constant:
            tests["anderson"] = {"stat": None, "critical_5": None, "p_value": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ad = stats.anderson(vals, dist="norm")
                levels = [float(v) for v in list(getattr(ad, "significance_level", []))]
                crits = [float(v) for v in list(getattr(ad, "critical_values", []))]
                crit_5 = None
                if levels and crits and len(levels) == len(crits):
                    for lvl, crit in zip(levels, crits):
                        if abs(float(lvl) - 5.0) < 1e-9:
                            crit_5 = float(crit)
                            break
                    if crit_5 is None:
                        idx = int(np.argmin(np.abs(np.array(levels) - 5.0)))
                        crit_5 = float(crits[idx])
                stat = _finite_float_or_none(getattr(ad, "statistic", None))
                if stat is None:
                    raise ValueError("non-finite anderson output")
                passed = bool(stat < crit_5) if crit_5 is not None else None
                tests["anderson"] = {
                    "stat": stat,
                    "critical_5": crit_5,
                    "p_value": None,
                    "passed": passed,
                }
            except Exception:
                tests["anderson"] = {"stat": None, "critical_5": None, "p_value": None, "passed": None}
    else:
        tests["anderson"] = {"stat": None, "critical_5": None, "p_value": None, "passed": None}

    # KS against fitted normal (Lilliefors-like practical check; conservative interpretation).
    if n >= 20:
        if near_constant:
            tests["ks"] = {"stat": None, "p_value": None, "passed": False, "reason": "near_constant_data"}
        else:
            try:
                mu = float(np.mean(vals))
                sigma = float(np.std(vals, ddof=1))
                if np.isfinite(sigma) and sigma > 0:
                    z = (vals - mu) / sigma
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        stat, p_value = stats.kstest(z, "norm")
                    stat_f = _finite_float_or_none(stat)
                    p_f = _finite_float_or_none(p_value)
                    if stat_f is None or p_f is None:
                        raise ValueError("non-finite ks output")
                    tests["ks"] = {
                        "stat": stat_f,
                        "p_value": p_f,
                        "passed": bool(p_f > alpha),
                    }
                else:
                    tests["ks"] = {"stat": None, "p_value": None, "passed": None}
            except Exception:
                tests["ks"] = {"stat": None, "p_value": None, "passed": None}
    else:
        tests["ks"] = {"stat": None, "p_value": None, "passed": None}

    test_mode = str(normality_test or "shapiro").strip().lower()
    if test_mode in {"", "default"}:
        test_mode = "shapiro"
    if test_mode in {"normaltest", "dagostino_pearson", "dagostino-pearson"}:
        test_mode = "dagostino"
    if test_mode in {"kstest", "kolmogorov-smirnov", "kolmogorov_smirnov"}:
        test_mode = "ks"
    if test_mode in {"suite", "all", "multi"}:
        selected = [name for name in ("shapiro", "dagostino", "anderson", "ks") if tests.get(name, {}).get("passed") is not None]
    elif test_mode == "auto":
        # Conservative fallback order: Shapiro -> D'Agostino -> KS -> Anderson.
        selected = []
        for name in ("shapiro", "dagostino", "ks", "anderson"):
            if tests.get(name, {}).get("passed") is not None:
                selected = [name]
                break
    elif test_mode in {"shapiro", "dagostino", "anderson", "ks"}:
        selected = [test_mode]
    else:
        selected = [name for name in ("shapiro", "dagostino", "anderson", "ks") if tests.get(name, {}).get("passed") is not None]
    if not selected:
        selected = [name for name in ("shapiro", "dagostino", "anderson", "ks") if tests.get(name, {}).get("passed") is not None]

    decision = str(decision_rule or "majority").strip().lower()
    if decision in {"", "default"}:
        decision = "majority"
    if decision in {"strict"}:
        decision = "all"
    if decision in {"lenient"}:
        decision = "any"

    passes = [tests[name]["passed"] for name in selected if tests.get(name, {}).get("passed") is not None]
    passed: Optional[bool]
    if not passes:
        passed = None
    elif len(selected) == 1:
        passed = bool(passes[0])
    elif decision == "all":
        passed = bool(all(passes))
    elif decision == "any":
        passed = bool(any(passes))
    else:
        passed = bool(sum(1 for p in passes if p) >= int(np.ceil(len(passes) / 2.0)))
        decision = "majority"

    primary = selected[0] if selected else None
    primary_payload = tests.get(primary or "", {})
    out.update(
        {
            "selected_tests": selected,
            "decision_rule": decision if len(selected) > 1 else "single",
            "tests": tests,
            "test": primary,
            "stat": primary_payload.get("stat"),
            "p_value": primary_payload.get("p_value"),
            "passed": passed,
        }
    )
    return out


def check_homogeneity_with_policy(
    groups_data: List[pd.Series],
    *,
    method: Optional[str] = "levene",
    alpha: float = 0.05,
    center: Optional[str] = "median",
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"test": None, "stat": None, "p_value": None, "passed": None}
    if len(groups_data) < 2:
        return out

    cleaned_groups: List[np.ndarray] = []
    for g in groups_data:
        clean = _clean_numeric_series(g)
        if len(clean) < 2:
            return out
        cleaned_groups.append(clean.to_numpy(dtype=float))

    method_name = str(method or "levene").strip().lower()
    if method_name in {"", "default"}:
        method_name = "levene"
    if method_name in {"brown-forsythe", "brown_forsythe"}:
        method_name = "levene"

    try:
        if method_name == "bartlett":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                stat, p_value = stats.bartlett(*cleaned_groups)
            out.update({"test": "bartlett", "stat": float(stat), "p_value": float(p_value), "passed": bool(float(p_value) > alpha)})
            return out
        if method_name == "fligner":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                stat, p_value = stats.fligner(*cleaned_groups)
            out.update({"test": "fligner", "stat": float(stat), "p_value": float(p_value), "passed": bool(float(p_value) > alpha)})
            return out

        center_name = str(center or "median").strip().lower()
        if center_name not in {"mean", "median", "trimmed"}:
            center_name = "median"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            stat, p_value = stats.levene(*cleaned_groups, center=center_name)
        out.update(
            {
                "test": "levene",
                "center": center_name,
                "stat": float(stat),
                "p_value": float(p_value),
                "passed": bool(float(p_value) > alpha),
            }
        )
        return out
    except Exception:
        return out


def check_normality(data: pd.Series) -> tuple[Optional[bool], Optional[float], Optional[float]]:
    """
    Backward-compatible normality check (Shapiro-only legacy output).
    Returns (is_normal, p_value, statistic).
    """
    result = check_normality_with_policy(
        data,
        normality_test="shapiro",
        alpha=0.05,
        decision_rule="single",
    )
    stat = result.get("stat")
    p_value = result.get("p_value")
    passed = result.get("passed")
    return (
        bool(passed) if isinstance(passed, bool) else None,
        float(p_value) if isinstance(p_value, (int, float)) else None,
        float(stat) if isinstance(stat, (int, float)) else None,
    )


def check_homogeneity(groups_data: List[pd.Series]) -> tuple[Optional[bool], Optional[float], Optional[float]]:
    """
    Backward-compatible homogeneity check (Levene-only legacy output).
    Returns (equal_var, p_value, statistic).
    """
    result = check_homogeneity_with_policy(
        groups_data,
        method="levene",
        alpha=0.05,
        center="median",
    )
    stat = result.get("stat")
    p_value = result.get("p_value")
    passed = result.get("passed")
    return (
        bool(passed) if isinstance(passed, bool) else None,
        float(p_value) if isinstance(p_value, (int, float)) else None,
        float(stat) if isinstance(stat, (int, float)) else None,
    )

def select_test(
    df: pd.DataFrame, 
    col_a: str, 
    col_b: str, 
    types: Dict[str, str],
    is_paired: bool = False
) -> str:
    """
    Auto-detects the best statistical test based on data properties.
    """
    type_a = types.get(col_a)
    type_b = types.get(col_b)
    
    # 1. Numeric vs Numeric -> Correlation
    if type_a == "numeric" and type_b == "numeric":
        is_norm_a, _, _ = check_normality(df[col_a])
        is_norm_b, _, _ = check_normality(df[col_b])
        return "pearson" if (is_norm_a is True and is_norm_b is True) else "spearman"

    # 2. Categorical vs Categorical -> Chi-Square
    if type_a == "categorical" and type_b == "categorical":
        return "chi_square"

    # 3. Numeric vs Categorical -> Group Comparison
    num_col = col_a if type_a == "numeric" else col_b
    cat_col = col_b if type_a == "numeric" else col_a
    
    groups = df[cat_col].dropna().unique()
    if len(groups) < 2:
        return None
        
    all_normal = True
    groups_data = []
    
    for g in groups:
        subset = df[df[cat_col] == g][num_col].dropna()
        is_normal, _, _ = check_normality(subset)
        if is_normal is False:
            all_normal = False
        groups_data.append(subset)
            
    if len(groups) == 2:
        if is_paired:
            return "t_test_rel" if all_normal else "wilcoxon"
        
        # Check Homogeneity for Independent
        equal_var, _, _ = check_homogeneity(groups_data)
        if equal_var is None:
            equal_var = True
        
        if not all_normal:
            return "mann_whitney"
        elif not equal_var:
            return "t_test_welch"
        else:
            return "t_test_ind"
    else:
        # 3+ groups
        return "anova" if all_normal else "kruskal"

def _run_analysis_python(
    df: pd.DataFrame, 
    method_id: str, 
    col_a: str, 
    col_b: str,
    is_paired: bool = False,
    alpha: float = 0.05,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes a specific statistical test.
    alpha: significance level threshold (default 0.05)
    """
    kwargs["alpha"] = alpha
    method_id = _normalize_method_id(method_id)
    # Robust numeric/categorical identification
    # Identify involved columns for cleaning
    input_cols = [col_a]
    if col_b: input_cols.append(col_b)
    if kwargs.get("group_col"): input_cols.append(kwargs.get("group_col"))
    if kwargs.get("predictors"): input_cols.extend(kwargs.get("predictors"))
    
    # Uniqify and Filter non-existent columns
    input_cols = list(set([c for c in input_cols if c and c in df.columns]))
    clean_df = df[input_cols].dropna()
    if clean_df.empty:
        raise ValueError("Недостаточно данных после очистки (все строки содержат пропуски).")
    
    # Handle 'auto' method selection
    if method_id == "auto":
        types = {}
        for col in [col_a, col_b]:
            if col and col in df.columns:
                s = df[col]
                name_l = str(col).strip().lower()
                if pd.api.types.is_numeric_dtype(s):
                    try:
                        non_na = s.dropna()
                        n = int(len(non_na))
                        unique = int(non_na.nunique(dropna=True)) if n else 0
                    except Exception:
                        n = int(len(s))
                        try:
                            unique = int(s.nunique(dropna=True))
                        except Exception:
                            unique = 0

                    ratio = float(unique) / float(max(1, n))
                    looks_like_group = any(
                        k in name_l
                        for k in [
                            "группа",
                            "group",
                            "treatment",
                            "arm",
                            "cohort",
                            "класс",
                            "категор",
                            "category",
                            "групп",
                            "рандом",
                        ]
                    )
                    if (unique and unique <= 12 and ratio <= 0.2) or (looks_like_group and unique and unique <= 50):
                        types[col] = "categorical"
                    else:
                        types[col] = "numeric"
                else:
                    types[col] = "categorical"
        
        # Auto-select the best test
        method_id = select_test(df, col_a, col_b, types, is_paired)
        if method_id is None:
            raise ValueError("Could not auto-detect appropriate statistical test. Please select manually.")

    requested_method_id = method_id

    if method_id in GROUP_TESTS:
        if col_a not in clean_df.columns or col_b not in clean_df.columns:
            raise ValueError("Не найдены колонки для группового сравнения.")
        if clean_df.shape[0] < 2:
            raise ValueError("Недостаточно наблюдений для группового сравнения.")
        auto_fallback = bool(kwargs.get("auto_fallback", True))

        groups = sorted(clean_df[col_b].unique()) if col_b in clean_df.columns else []
        data_groups = [clean_df[clean_df[col_b] == g][col_a] for g in groups] if groups else []
        assumptions = (
            _check_assumptions(
                groups,
                data_groups,
                alpha=alpha,
                normality_test=kwargs.get("normality_test"),
                normality_decision=kwargs.get("normality_decision"),
                homogeneity_test=kwargs.get("homogeneity_test"),
                homogeneity_center=kwargs.get("homogeneity_center"),
            )
            if groups
            else {}
        )
        warnings = _generate_warnings(str(requested_method_id).strip(), path_type="group", assumptions=assumptions)

        norm_res = assumptions.get("normality") if isinstance(assumptions, dict) else None
        normality_state: str = "unknown"
        if isinstance(norm_res, dict) and norm_res:
            passed_vals = [v.get("passed") for v in norm_res.values() if isinstance(v, dict)]
            if any(v is False for v in passed_vals):
                normality_state = "failed"
            elif any(v is None for v in passed_vals):
                normality_state = "unknown"
            else:
                normality_state = "passed"

        homo_res = assumptions.get("homogeneity") if isinstance(assumptions, dict) else None
        homogeneity_state: str = "unknown"
        if isinstance(homo_res, dict) and ("passed" in homo_res):
            if homo_res.get("passed") is False:
                homogeneity_state = "failed"
            elif homo_res.get("passed") is True:
                homogeneity_state = "passed"
            else:
                homogeneity_state = "unknown"

        recommended: Optional[str] = None
        if normality_state != "unknown" and homogeneity_state != "unknown":
            recommended = _recommend_group_test(
                len(groups),
                bool(is_paired),
                normality_state == "passed",
                homogeneity_state == "passed",
            )

        method_used = recommended if (auto_fallback and recommended and recommended != requested_method_id) else requested_method_id

        if method_used != requested_method_id:
            warnings.append(f"Auto-fallback used: {requested_method_id} → {method_used}.")

        out = _handle_group_comparison(clean_df, method_used, col_a, col_b, kwargs)
        out["method_requested"] = requested_method_id
        out["method_used"] = method_used
        out["recommended_method"] = recommended
        out["assumptions"] = assumptions
        out["assumption_checks"] = assumptions
        out["warnings"] = warnings
        out["assumption_warning"] = " ".join([str(w) for w in warnings]) if warnings else None
        return out
    
    # Dispatcher
    if method_id == "t_test_one":
        return _handle_one_sample(clean_df, method_id, col_a, kwargs)

    elif method_id == "bayes_t_test_one":
        return _handle_bayes_t_test_one(clean_df, col_a, kwargs)

    elif method_id in ["pearson", "spearman", "kendall"]:
        return _handle_correlation(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "bayes_correlation":
        return _handle_bayes_correlation(clean_df, col_a, col_b, kwargs)

    elif method_id == "bayes_anova":
        return _handle_bayes_anova(clean_df, col_a, col_b, kwargs)

    elif method_id == "bayes_chi_square":
        return _handle_bayes_chi_square(clean_df, col_a, col_b, kwargs)

    elif method_id == "chi_square":
        return _handle_chi_square(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["fisher", "fisher_exact"]:
        return _handle_fisher_exact(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "survival_km":
        return _handle_survival(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "bayes_linear_regression":
        return _handle_bayes_linear_regression(clean_df, col_a, col_b, kwargs)

    elif method_id in ["linear_regression", "logistic_regression"]:
        return _handle_regression(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "roc_analysis":
        return _handle_roc_analysis(clean_df, method_id, col_a, col_b)

    elif method_id in ["random_forest", "gradient_boosting", "knn", "svm"]:
        return _handle_ml(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["mixed_model", "mixed_effects"]:
        return _handle_mixed_effects(df, col_a, col_b, kwargs)

    elif method_id == "rm_anova":
        return _handle_rm_anova(df, col_a, kwargs)

    elif method_id == "friedman":
        return _handle_friedman(df, col_a, kwargs)

    elif method_id == "anova_twoway":
        return _handle_anova_twoway(df, col_a, kwargs)

    elif method_id == "clustered_correlation":
        return _handle_clustered_correlation(df, kwargs)

    elif method_id == "shapiro_wilk":
        return _handle_shapiro_wilk(df, col_a, kwargs)

    elif method_id == "bland_altman":
        return _handle_bland_altman(df, col_a, col_b, kwargs)

    elif method_id == "time_series_analysis":
        return _handle_time_series_analysis(df, col_a, kwargs)

    elif method_id == "icc":
        return _handle_icc(df, col_a, col_b, kwargs)

    elif method_id == "cohens_kappa":
        return _handle_cohens_kappa(df, col_a, col_b, kwargs)

    elif method_id == "mcnemar":
        return _handle_mcnemar(df, col_a, col_b, kwargs)

    elif method_id == "cochran_q":
        return _handle_cochran_q(df, kwargs)

    elif method_id == "bayes_t_test_ind":
        return _handle_bayes_t_test_ind(clean_df, col_a, col_b, kwargs)

    elif method_id == "bayes_t_test_rel":
        return _handle_bayes_t_test_rel(clean_df, col_a, col_b, kwargs)

    elif method_id == "point_biserial":
        return _handle_point_biserial(df, col_a, col_b, kwargs)

    elif method_id == "partial_correlation":
        return _handle_partial_correlation(df, col_a, col_b, kwargs)

    elif method_id == "cronbach_alpha":
        return _handle_cronbach_alpha(df, col_a, col_b, kwargs)

    elif method_id == "ancova":
        return _handle_ancova(df, col_a, col_b, kwargs)

    elif method_id == "pca":
        return _handle_pca(df, col_a, col_b, kwargs)

    elif method_id == "efa":
        return _handle_efa(df, col_a, col_b, kwargs)

    elif method_id == "kmeans":
        return _handle_kmeans(df, col_a, col_b, kwargs)

    elif method_id == "hierarchical_clustering":
        return _handle_hierarchical_clustering(df, col_a, col_b, kwargs)

    raise ValueError(f"Method {method_id} not implemented")


def _roc_payload(y_true_bin: np.ndarray, y_score: np.ndarray) -> Dict[str, Any]:
    fpr, tpr, thresholds = roc_curve(y_true_bin, y_score)
    roc_auc = auc(fpr, tpr)

    roc_data = []
    step = max(1, len(fpr) // 500)
    for i in range(0, len(fpr), step):
        roc_data.append({
            "x": float(fpr[i]),
            "y": float(tpr[i]),
            "threshold": float(thresholds[i]),
        })
    if roc_data and roc_data[-1]["x"] != float(fpr[-1]):
        roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})

    return {
        "auc": float(roc_auc),
        "plot_data": roc_data,
        "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"},
    }


def _handle_ml(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        r2_score,
        mean_absolute_error,
        mean_squared_error,
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.ensemble import (
        RandomForestRegressor,
        RandomForestClassifier,
        GradientBoostingRegressor,
        GradientBoostingClassifier,
    )
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    predictors = kwargs.get("predictors")
    if predictors is None:
        predictors = [col_b] if col_b else []
    if not isinstance(predictors, list):
        predictors = [col_b] if col_b else []
    predictors = [p for p in predictors if p]

    task = str(kwargs.get("task") or "regression").strip().lower()
    random_state = kwargs.get("random_state")
    test_size = float(kwargs.get("test_size") or 0.25)
    if not (0.05 <= test_size <= 0.8):
        test_size = 0.25

    cols = [c for c in [col_a, *predictors] if c and c in df.columns]
    clean_df = df[cols].dropna()

    if col_a not in clean_df.columns:
        raise ValueError(f"Target column '{col_a}' not found")
    if not predictors:
        raise ValueError("predictors is required for ML methods")

    y_raw = clean_df[col_a]
    X_raw = clean_df[predictors]
    X = pd.get_dummies(X_raw, drop_first=True)

    if task == "classification":
        y_non_na = y_raw.dropna()
        uniq = list(pd.unique(y_non_na))
        if len(uniq) != 2:
            raise ValueError(f"Classification requires a binary target. Found {len(uniq)} unique values.")

        if pd.api.types.is_numeric_dtype(y_non_na):
            y_as_float = y_raw.astype(float)
            uniq_num = sorted(set(float(v) for v in pd.unique(y_as_float.dropna())))
            if set(uniq_num) == {0.0, 1.0}:
                y_bin = y_as_float.to_numpy()
                neg_label = "0"
                pos_label = "1"
            else:
                mapping = {uniq_num[0]: 0.0, uniq_num[1]: 1.0}
                y_bin = y_as_float.map(mapping).to_numpy()
                neg_label = str(uniq_num[0])
                pos_label = str(uniq_num[1])
        else:
            uniq_str = sorted(str(v) for v in uniq)
            neg_label = uniq_str[0]
            pos_label = uniq_str[1]
            y_bin = y_raw.astype(str).map(lambda v: 1.0 if v == pos_label else 0.0).to_numpy()

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y_bin,
            test_size=test_size,
            random_state=random_state,
            stratify=y_bin if len(np.unique(y_bin)) == 2 else None,
        )

        if method_id == "random_forest":
            model = RandomForestClassifier(n_estimators=200, random_state=random_state)
        elif method_id == "gradient_boosting":
            model = GradientBoostingClassifier(random_state=random_state)
        elif method_id == "knn":
            model = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=int(kwargs.get("n_neighbors") or 5)))
        else:
            model = make_pipeline(
                StandardScaler(),
                SVC(
                    C=float(kwargs.get("C") or 1.0),
                    kernel=str(kwargs.get("kernel") or "rbf"),
                    probability=True,
                    random_state=random_state,
                ),
            )

        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))

        y_score = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test)
            if isinstance(proba, np.ndarray) and proba.ndim == 2 and proba.shape[1] >= 2:
                y_score = proba[:, 1]
        if y_score is None and hasattr(model, "decision_function"):
            y_score = model.decision_function(X_test)
        if y_score is None:
            y_score = y_pred

        roc_out = _roc_payload(np.asarray(y_test).astype(int), np.asarray(y_score, dtype=float))
        roc_out["pos_label"] = pos_label
        roc_out["neg_label"] = neg_label

        return {
            "method": method_id,
            "task": "classification",
            "accuracy": acc,
            "f1": f1,
            "precision": precision,
            "recall": recall,
            "roc": roc_out,
        }

    y = pd.to_numeric(y_raw, errors="coerce")
    if y.isna().any():
        raise ValueError("Regression requires a numeric target")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y.to_numpy(dtype=float),
        test_size=test_size,
        random_state=random_state,
    )

    if method_id == "random_forest":
        model = RandomForestRegressor(n_estimators=300, random_state=random_state)
    elif method_id == "gradient_boosting":
        model = GradientBoostingRegressor(random_state=random_state)
    elif method_id == "knn":
        model = make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=int(kwargs.get("n_neighbors") or 5)))
    else:
        model = make_pipeline(
            StandardScaler(),
            SVR(C=float(kwargs.get("C") or 1.0), kernel=str(kwargs.get("kernel") or "rbf")),
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    r2 = float(r2_score(y_test, y_pred))
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    return {
        "method": method_id,
        "task": "regression",
        "r_squared": r2,
        "mae": mae,
        "rmse": rmse,
    }


def _handle_group_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    local = df[[col_a, col_b]].dropna()
    if local.empty:
        raise ValueError("Недостаточно данных для группового сравнения.")
    groups = sorted(local[col_b].unique())
    data_groups = [local[local[col_b] == g][col_a] for g in groups]
    group_counts = [int(g.dropna().shape[0]) for g in data_groups]
    nonempty_groups = sum(1 for c in group_counts if c > 0)
    if nonempty_groups < 2:
        raise ValueError("Недостаточно групп для сравнения.")
    if any(c < 2 for c in group_counts):
        raise ValueError("Недостаточно наблюдений в одной из групп.")
    
    stat_val, p_val = 0.0, 1.0
    alt = _normalize_alternative(kwargs.get("alternative"), default="two-sided")
    eff_size = None
    eff_size_name = None
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    observed_power = None
    bf10 = None
    post_hoc_results = None
    anova_table = None
    method_str = str(method_id).strip()
    bootstrap_enabled = bool(kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(kwargs.get("bootstrap_samples"), default=1000)
    bootstrap_payload: Optional[Dict[str, Any]] = None

    if method_str == "t_test_ind" and len(groups) == 2:
        res = _call_pg_ttest(data_groups[0], data_groups[1], paired=False, alternative=alt, correction=False)
        stat_val = float(res["T"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        
        requested_es = kwargs.get("effect_size", "cohen")
        eff_size = None
        eff_size_name = requested_es
        
        if requested_es == "cohen":
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
        elif requested_es == "hedges":
             try:
                 eff_size = _call_pg_compute_effsize(data_groups[0], data_groups[1], eftype='hedges')
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        elif requested_es == "glass":
             try:
                 # Glass's delta: diff / sd of control group (assume group 2 is control)
                 # data_groups[1] is the second group
                 m1 = np.mean(data_groups[0])
                 m2 = np.mean(data_groups[1])
                 sd2 = np.std(data_groups[1], ddof=1)
                 eff_size = (m1 - m2) / sd2
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        else:
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
             eff_size_name = "cohen-d"

        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
        
    elif method_str == "t_test_welch" and len(groups) == 2:
        res = _call_pg_ttest(data_groups[0], data_groups[1], paired=False, alternative=alt, correction=True)
        stat_val = float(res["T"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        
        requested_es = kwargs.get("effect_size", "cohen")
        eff_size = None
        eff_size_name = requested_es
        
        if requested_es == "cohen":
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
        elif requested_es == "hedges":
             try:
                 eff_size = _call_pg_compute_effsize(data_groups[0], data_groups[1], eftype='hedges')
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        elif requested_es == "glass":
             try:
                 m1 = np.mean(data_groups[0])
                 m2 = np.mean(data_groups[1])
                 sd2 = np.std(data_groups[1], ddof=1)
                 eff_size = (m1 - m2) / sd2
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        else:
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
             eff_size_name = "cohen-d"

        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
        
    elif method_id == "mann_whitney" and len(groups) == 2:
        res = pg.mwu(data_groups[0], data_groups[1], alternative=alt)
        stat_val = float(res["U-val"].iloc[0]) if "U-val" in res.columns else float(res["U"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        eff_size = float(res["RBC"].iloc[0]) if "RBC" in res.columns else eff_size
        eff_size_name = "rbc" if eff_size is not None else None
        
    elif method_id == "anova":
        aov = pg.anova(data=df, dv=col_a, between=col_b, detailed=True)
        row = aov[aov["Source"] == col_b].iloc[0] if "Source" in aov.columns and (aov["Source"] == col_b).any() else aov.iloc[0]
        stat_val = float(row.get("F"))
        p_val = float(row.get("p-unc"))
        
        # Calculate requested effect size
        requested_es = kwargs.get("effect_size", "eta_squared")
        eff_size = None
        eff_size_name = requested_es

        ss_between = float(row['SS'])
        ss_total = float(aov['SS'].sum()) if 'SS' in aov.columns else 0.0
        df_between = float(row['DF'])
        df_within = float(aov[aov["Source"] == "Within"]['DF'].iloc[0]) if "Within" in aov["Source"].values else float(aov['DF'].sum()) - df_between
        ms_within = float(aov[aov["Source"] == "Within"]['MS'].iloc[0]) if "Within" in aov["Source"].values else 1.0

        anova_table = aov.to_dict('records') # Added line
        
        if requested_es == "eta_squared":
             if ss_total > 0:
                 eff_size = ss_between / ss_total
        elif requested_es == "partial_eta_squared":
            # For one-way ANOVA, partial eta squared = eta squared
             if ss_total > 0:
                 eff_size = ss_between / ss_total
        elif requested_es == "omega_squared":
             if (ss_total + ms_within) > 0:
                 eff_size = (ss_between - (df_between * ms_within)) / (ss_total + ms_within)

        # Fallback if calculation failed or not requested type found in common logic
        if eff_size is None:
             if "np2" in row:
                 eff_size = float(row.get("np2"))
                 eff_size_name = "np2"
             elif "eta2" in row:
                 eff_size = float(row.get("eta2"))
                 eff_size_name = "eta2"

        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'tukey') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None

                if post_hoc_results is None:
                    post_hoc_results = _run_tukey_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'games_howell':
                try:
                    post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'bonferroni':
                 # Manual pairwise t-tests with Bonferroni
                 try:
                     post = pg.pairwise_tests(data=df, dv=col_a, between=col_b, padjust='bonf')
                     post_hoc_results = _format_posthoc_results(post, alpha)
                 except Exception:
                     post_hoc_results = None
            elif post_hoc == 'holm':
                 try:
                     post = pg.pairwise_tests(data=df, dv=col_a, between=col_b, padjust='holm')
                     post_hoc_results = _format_posthoc_results(post, alpha)
                 except Exception:
                     post_hoc_results = None
            elif post_hoc == 'scheffe':
                 # Scheffe is not directly in pg.pairwise_tests, simplify to none or generic
                 # Pingouin doesn't have built-in Scheffe. 
                 # We will skip or fallback to Tukey? 
                 # Let's fallback to uncorrected pairwise for now or just skip.
                 post_hoc_results = None

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "anova_welch":
        welch = pg.welch_anova(data=df, dv=col_a, between=col_b)
        anova_table = welch.to_dict('records')
        row = welch.iloc[0]
        stat_val = float(row.get("F"))
        p_val = float(row.get("p-unc"))
        
        # Welch ANOVA effect size is typically eta-squared or omega-squared estimated
        # Pingouin returns np2 sometimes?
        requested_es = kwargs.get("effect_size", "eta_squared")
        eff_size = None
        eff_size_name = requested_es
        
        if "np2" in row:
             eff_size = float(row.get("np2"))
             # Override name if user asked for specific one that matches
             if requested_es in ["eta_squared", "partial_eta_squared"]:
                 eff_size_name = requested_es # In one-way they are same
        
        # If strict calculation needed for Omega-squared in Welch, it's complex. 
        # For now rely on what we have + fallback.
        if eff_size is None and "eta2" in row:
            eff_size = float(row.get("eta2"))

        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'games_howell') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'games_howell':
                post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                post_hoc_results = _format_posthoc_results(post, alpha)
            elif post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "kruskal":
        kr = pg.kruskal(data=df, dv=col_a, between=col_b)
        anova_table = kr.to_dict('records')
        row = kr.iloc[0]
        stat_val = float(row.get("H"))
        p_val = float(row.get("p-unc"))
        if "eps-sq" in row:
            eff_size = float(row.get("eps-sq"))
            eff_size_name = "eps-sq"
        elif "eta2" in row:
            eff_size = float(row.get("eta2"))
            eff_size_name = "eta2"
        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'none') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'games_howell':
                try:
                    post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "t_test_rel" and len(groups) == 2:
         res = _call_pg_ttest(data_groups[0], data_groups[1], paired=True, alternative=alt)
         stat_val = float(res["T"].iloc[0])
         p_val = float(res["p-val"].iloc[0])
         
         requested_es = kwargs.get("effect_size", "cohen")
         eff_size = None
         eff_size_name = requested_es
         
         if requested_es == "cohen":
              eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
         elif requested_es == "hedges":
              try:
                  eff_size = _call_pg_compute_effsize(data_groups[0], data_groups[1], paired=True, eftype='hedges')
              except Exception:
                  eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                  eff_size_name = "cohen-d" # Fallback
         else:
              eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
              eff_size_name = "cohen-d"

         eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
         power = float(res["power"].iloc[0]) if "power" in res.columns else None
         try:
             bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
         except Exception:
             bf10 = None

    elif method_id == "wilcoxon" and len(groups) == 2:
         res = _call_pg_wilcoxon(data_groups[0], data_groups[1], alternative=alt)
         stat_val = float(res["W-val"].iloc[0]) if "W-val" in res.columns else float(res["W"].iloc[0])
         p_val = float(res["p-val"].iloc[0])
         eff_size = float(res["RBC"].iloc[0]) if "RBC" in res.columns else eff_size
         eff_size_name = "rbc" if eff_size is not None else None
         
    if bf10 is None:
        bf10 = _bf10_from_p_value_bound(p_val)

    # Prepare Plot Data & Descriptives
    plot_data, plot_stats = _prepare_group_plot_data(groups, data_groups)
    
    # If descriptives not requested, clear the stats table data
    if not kwargs.get("descriptives", True):
        plot_stats = None

    alpha = kwargs.get("alpha", 0.05)

    if method_str in {"t_test_ind", "t_test_welch"} and len(data_groups) >= 2:
        observed_power = compute_post_hoc_power(
            n1=len(pd.Series(data_groups[0]).dropna()),
            n2=len(pd.Series(data_groups[1]).dropna()) if len(data_groups) > 1 else None,
            effect_size=eff_size,
            alpha=alpha,
            test_type="two_sample",
        )
    elif method_str == "t_test_rel" and len(data_groups) >= 2:
        observed_power = compute_post_hoc_power(
            n1=len(pd.Series(data_groups[0]).dropna()),
            effect_size=eff_size,
            alpha=alpha,
            test_type="paired",
        )

    # Calculate Assumptions
    assumptions = _check_assumptions(
        groups,
        data_groups,
        alpha=alpha,
        normality_test=kwargs.get("normality_test"),
        normality_decision=kwargs.get("normality_decision"),
        homogeneity_test=kwargs.get("homogeneity_test"),
        homogeneity_center=kwargs.get("homogeneity_center"),
    )
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_str, path_type="group", assumptions=assumptions)

    # Interpret effect size for user
    effect_interpretation = interpret_effect_size(eff_size, eff_size_name) if eff_size is not None else None

    # Handle CI visibility
    if not kwargs.get("ci", True):
        eff_ci_lower = None
        eff_ci_upper = None

    comparisons: Optional[List[Dict[str, Any]]] = None
    try:
        comparisons = []
        if isinstance(post_hoc_results, list) and post_hoc_results:
            for r in post_hoc_results:
                a = r.get("group1")
                b = r.get("group2")
                raw_p = r.get("p_value")
                adj_p = r.get("p_value_adj")
                p = adj_p if isinstance(adj_p, (int, float)) else raw_p
                if a is None or b is None or p is None:
                    continue
                comparisons.append({"a": str(a), "b": str(b), "p_value": float(p), "p_value_raw": float(raw_p) if raw_p is not None else None, "p_value_adj": float(adj_p) if adj_p is not None else None})
        elif len(groups) == 2 and isinstance(p_val, (int, float)):
            comparisons.append({"a": str(groups[0]), "b": str(groups[1]), "p_value": float(p_val)})
    except Exception:
        comparisons = None

    if bootstrap_enabled:
        bootstrap_payload = {
            "enabled": True,
            "samples": int(bootstrap_samples),
            "ci_level": 0.95,
            "metrics": {},
        }
        try:
            if len(groups) == 2:
                x_arr = pd.to_numeric(pd.Series(data_groups[0]), errors="coerce").dropna().to_numpy(dtype=float)
                y_arr = pd.to_numeric(pd.Series(data_groups[1]), errors="coerce").dropna().to_numpy(dtype=float)

                ci_mean_diff = _bootstrap_ci_two_sample(
                    x_arr,
                    y_arr,
                    stat_fn=lambda a, b: float(np.mean(a) - np.mean(b)),
                    n_boot=bootstrap_samples,
                )
                if ci_mean_diff is not None:
                    bootstrap_payload["metrics"]["mean_diff"] = ci_mean_diff

                if method_str in {"t_test_ind", "t_test_welch", "t_test_rel"} or (
                    isinstance(eff_size_name, str) and "cohen" in eff_size_name.lower()
                ):
                    ci_cohen = _bootstrap_ci_two_sample(
                        x_arr,
                        y_arr,
                        stat_fn=_cohen_d_from_arrays,
                        n_boot=bootstrap_samples,
                    )
                    if ci_cohen is not None:
                        bootstrap_payload["metrics"]["effect_size"] = {**ci_cohen, "name": "cohen_d"}
                        if kwargs.get("ci", True):
                            eff_ci_lower = float(ci_cohen["ci_lower"])
                            eff_ci_upper = float(ci_cohen["ci_upper"])
        except Exception as e:
            logger.warning(f"bootstrap_ci failed for group comparison ({method_str}): {e}")

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "effect_size_name": eff_size_name,
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "observed_power": observed_power,
        "bf10": bf10,
        "significant": p_val < alpha,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "post_hoc": post_hoc_results,
        "comparisons": comparisons,
        "anova_table": anova_table,
        "bootstrap": bootstrap_payload,
    }

def _run_tukey_posthoc(data_groups, groups, alpha=0.05):
    try:
        all_vals = []
        all_groups = []
        for i, g in enumerate(groups):
            vals = data_groups[i]
            all_vals.extend(vals)
            all_groups.extend([g]*len(vals))
        
        tukey = pairwise_tukeyhsd(endog=all_vals, groups=all_groups, alpha=alpha)
        summary_data = tukey.summary().data[1:]
        post_hoc = []
        for row in summary_data:
            post_hoc.append({
                "group1": str(row[0]),
                "group2": str(row[1]),
                "diff": float(row[2]),
                "p_value": float(row[3]),
                "ci_lower": float(row[4]),
                "ci_upper": float(row[5]),
                "significant": bool(row[6])
            })
        return post_hoc
    except Exception as e:
        logger.error(f"Post-hoc failed: {e}", exc_info=True)
        return None

def _handle_one_sample(df, method_id, col_a, kwargs):
    data = df[col_a]
    test_val = float(kwargs.get("test_value", 0))
    alt = _normalize_alternative(kwargs.get("alternative"), default="two-sided")
    alpha = kwargs.get("alpha", 0.05)
    bootstrap_enabled = bool(kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(kwargs.get("bootstrap_samples"), default=1000)

    res = _call_pg_ttest(data, test_val, paired=False, alternative=alt)
    stat_val = float(res["T"].iloc[0])
    p_val = float(res["p-val"].iloc[0])
    eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
    eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
    power = float(res["power"].iloc[0]) if "power" in res.columns else None
    try:
        bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
    except Exception:
        bf10 = None
    
    plot_data = [{"value": float(v)} for v in data]
    mean = float(data.mean())
    std = float(data.std())
    
    plot_stats = {
        "group": {
            "mean": mean,
            "sd": std,
            "count": len(data),
            "sem": std/np.sqrt(len(data))
        }
    }
    
    if not kwargs.get("descriptives", True):
        plot_stats = None

    effect_interpretation = interpret_effect_size(eff_size, "cohen-d") if eff_size is not None else None
    observed_power = compute_post_hoc_power(
        n1=len(pd.Series(data).dropna()),
        effect_size=eff_size,
        alpha=alpha,
        test_type="one_sample",
    )
    
    if not kwargs.get("ci", True):
         eff_ci_lower = None
         eff_ci_upper = None
         effect_size_ci_lower = None # 1-sample eff size CI not usually returned by pg.ttest
         effect_size_ci_upper = None
    else:
         effect_size_ci_lower = None
         effect_size_ci_upper = None

    bootstrap_payload: Optional[Dict[str, Any]] = None
    if bootstrap_enabled:
        bootstrap_payload = {
            "enabled": True,
            "samples": int(bootstrap_samples),
            "ci_level": 0.95,
            "metrics": {},
        }
        try:
            ci_mean_diff = _bootstrap_ci_one_sample(
                data,
                stat_fn=lambda a: float(np.mean(a) - test_val),
                n_boot=bootstrap_samples,
            )
            if ci_mean_diff is not None:
                bootstrap_payload["metrics"]["mean_diff"] = ci_mean_diff

            ci_cohen = _bootstrap_ci_one_sample(
                data,
                stat_fn=lambda a: (
                    float((np.mean(a) - test_val) / np.std(a, ddof=1))
                    if np.std(a, ddof=1) not in {0.0, -0.0}
                    else None
                ),
                n_boot=bootstrap_samples,
            )
            if ci_cohen is not None:
                bootstrap_payload["metrics"]["effect_size"] = {**ci_cohen, "name": "cohen_d"}
        except Exception as e:
            logger.warning(f"bootstrap_ci failed for one-sample ({method_id}): {e}")

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "effect_size_name": "cohen-d" if eff_size is not None else None,
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower, # CI for mean diff
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "observed_power": observed_power,
        "bf10": bf10,
        "significant": p_val < alpha,
        "groups": ["Sample"],
        "plot_data": plot_data,
        "plot_stats": plot_stats,
        "extra": {"test_value": test_val},
        "bootstrap": bootstrap_payload,
    }

def _handle_correlation(df, method_id, col_a, col_b, kwargs):
    x, y = df[col_a], df[col_b]
    alpha = kwargs.get("alpha", 0.05)
    alt = _normalize_alternative(kwargs.get("alternative"), default="two-sided")
    bootstrap_enabled = bool(kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(kwargs.get("bootstrap_samples"), default=1000)
    corr_pref = str(kwargs.get("correlation_method") or "").strip().lower()
    if corr_pref in {"pearson", "spearman", "kendall"}:
        method_used = corr_pref
    else:
        method_used = str(method_id).strip().lower()
        if method_used not in {"pearson", "spearman", "kendall"}:
            method_used = "spearman"

    stat_val = 0.0
    p_val = 1.0
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    bf10 = None

    try:
        res = pg.corr(x=x, y=y, method=method_used, alternative=alt)
        stat_val = float(res["r"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
    except Exception:
        if method_used == "pearson":
            stat_val, p_val = stats.pearsonr(x, y)
        elif method_used == "kendall":
            stat_val, p_val = stats.kendalltau(x, y)
        else:
            stat_val, p_val = stats.spearmanr(x, y)
        
    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    
    # Interpret correlation as effect size
    effect_interpretation = interpret_effect_size(stat_val, method_used)
    
    if not kwargs.get("ci", True):
        eff_ci_lower = None
        eff_ci_upper = None

    bootstrap_payload: Optional[Dict[str, Any]] = None
    if bootstrap_enabled:
        try:
            ci_corr = _bootstrap_ci_correlation(
                x,
                y,
                method=method_used,
                n_boot=bootstrap_samples,
            )
            if ci_corr is not None:
                bootstrap_payload = {
                    "enabled": True,
                    "samples": int(bootstrap_samples),
                    "ci_level": 0.95,
                    "metrics": {
                        "correlation": {**ci_corr, "name": method_used},
                    },
                }
                if kwargs.get("ci", True):
                    eff_ci_lower = float(ci_corr["ci_lower"])
                    eff_ci_upper = float(ci_corr["ci_upper"])
            else:
                bootstrap_payload = {
                    "enabled": True,
                    "samples": int(bootstrap_samples),
                    "ci_level": 0.95,
                    "metrics": {},
                }
        except Exception as e:
            logger.warning(f"bootstrap_ci failed for correlation ({method_used}): {e}")

    # Plot Data (Sampled)
    plot_data = []
    sample_indices = np.random.choice(df.index, min(len(df), 1000), replace=False)
    for idx in sample_indices:
        plot_data.append({"x": float(df.loc[idx, col_a]), "y": float(df.loc[idx, col_b])})
        
    return {
        "method": method_used,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(stat_val),  # r is the effect size
        "effect_size_name": "tau" if method_used == "kendall" else "r",
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10 if bf10 is not None else _bf10_from_p_value_bound(p_val),
        "significant": p_val < alpha,
        "regression": {"slope": float(slope), "intercept": float(intercept), "r_squared": float(r_value**2)},
        "plot_data": plot_data,
        "bootstrap": bootstrap_payload,
    }


def _handle_bayes_t_test_one(df: pd.DataFrame, col_a: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_one_sample(df, "bayes_t_test_one", col_a, kwargs)
    base["frequentist_method"] = "t_test_one"
    return _augment_bayesian_payload(base, method_id="bayes_t_test_one")


def _handle_bayes_t_test_ind(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_group_comparison(df, "t_test_ind", col_a, col_b, kwargs)
    base["frequentist_method"] = "t_test_ind"
    return _augment_bayesian_payload(base, method_id="bayes_t_test_ind")


def _handle_bayes_t_test_rel(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_group_comparison(df, "t_test_rel", col_a, col_b, kwargs)
    base["frequentist_method"] = "t_test_rel"
    return _augment_bayesian_payload(base, method_id="bayes_t_test_rel")


def _handle_bayes_correlation(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    corr_method = str(kwargs.get("correlation_method") or kwargs.get("method") or "pearson").strip().lower()
    if corr_method not in {"pearson", "spearman", "kendall"}:
        corr_method = "pearson"
    next_kwargs = dict(kwargs)
    next_kwargs["correlation_method"] = corr_method
    base = _handle_correlation(df, corr_method, col_a, col_b, next_kwargs)
    base["frequentist_method"] = corr_method
    return _augment_bayesian_payload(base, method_id="bayes_correlation")


def _handle_bayes_anova(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_group_comparison(df, "anova", col_a, col_b, kwargs)
    base["frequentist_method"] = "anova"
    return _augment_bayesian_payload(base, method_id="bayes_anova")


def _handle_bayes_chi_square(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_chi_square(df, "chi_square", col_a, col_b, kwargs)
    base["frequentist_method"] = str(base.get("method") or "chi_square")
    return _augment_bayesian_payload(base, method_id="bayes_chi_square")


def _handle_bayes_linear_regression(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    base = _handle_regression(df, "linear_regression", col_a, col_b, kwargs)
    base["frequentist_method"] = "linear_regression"
    return _augment_bayesian_payload(base, method_id="bayes_linear_regression")


def _handle_time_series_analysis(df: pd.DataFrame, col_a: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    value_col = str(kwargs.get("outcome") or kwargs.get("target") or kwargs.get("value_col") or col_a).strip()
    time_col = str(kwargs.get("time") or kwargs.get("time_col") or "").strip()
    forecast_horizon_raw = kwargs.get("forecast_horizon", kwargs.get("horizon", 0))
    try:
        forecast_horizon = int(forecast_horizon_raw)
    except Exception:
        forecast_horizon = 0
    forecast_horizon = max(0, min(365, forecast_horizon))
    if not value_col or value_col not in df.columns:
        return {"error": "value column not found"}

    cols = [value_col] + ([time_col] if time_col and time_col in df.columns else [])
    local = df[cols].copy()
    local[value_col] = pd.to_numeric(local[value_col], errors="coerce")
    local = local.dropna(subset=[value_col])
    if local.shape[0] < 8:
        return {"error": "Недостаточно данных для анализа временного ряда (n < 8)"}

    x_values: List[Any]
    time_index: Optional[pd.DatetimeIndex] = None
    numeric_time_values: Optional[np.ndarray] = None
    numeric_ratio: Optional[float] = None
    time_axis_kind = "index"
    parse_datetime_attempted = False
    parse_datetime_succeeded = False
    datetime_parse_ratio: Optional[float] = None
    time_min_year: Optional[int] = None
    time_max_year: Optional[int] = None
    n_unique_time = 0
    if time_col and time_col in local.columns:
        raw_time = local[time_col]
        n_unique_time = int(raw_time.nunique(dropna=True)) if len(raw_time) else 0
        raw_time_num = pd.to_numeric(raw_time, errors="coerce")
        numeric_ratio = float(raw_time_num.notna().mean()) if len(raw_time_num) else 0.0
        is_datetime_dtype = bool(pd.api.types.is_datetime64_any_dtype(raw_time))
        numeric_like = (numeric_ratio >= 0.95) and (not is_datetime_dtype)

        if not numeric_like:
            parse_datetime_attempted = True
            parsed_dt = pd.to_datetime(raw_time, errors="coerce")
            valid_dt = parsed_dt.notna()
            valid_dt_count = int(valid_dt.sum())
            datetime_parse_ratio = float(valid_dt.mean()) if len(parsed_dt) else 0.0
            enough_dt = valid_dt_count >= max(3, int(local.shape[0] * 0.6))
            if enough_dt:
                dt_values = parsed_dt[valid_dt]
                min_year = int(dt_values.dt.year.min()) if len(dt_values) else 0
                max_year = int(dt_values.dt.year.max()) if len(dt_values) else 0
                time_min_year = int(min_year) if len(dt_values) else None
                time_max_year = int(max_year) if len(dt_values) else None
                plausible_years = (1900 <= min_year <= 2200) and (1900 <= max_year <= 2200)
                unique_days = int(dt_values.dt.floor("D").nunique()) if len(dt_values) else 0
                try:
                    span_seconds = float((dt_values.max() - dt_values.min()).total_seconds()) if len(dt_values) else 0.0
                except Exception:
                    span_seconds = 0.0
                has_variation = (unique_days >= 2) and (span_seconds > 0.0)
                if plausible_years and has_variation:
                    parse_datetime_succeeded = True
                    local["__time__"] = parsed_dt
                    local = local.dropna(subset=["__time__"]).sort_values("__time__")
                    time_index = pd.DatetimeIndex(local["__time__"])
                    x_values = [
                        str(v).replace(" 00:00:00", "")
                        for v in local["__time__"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
                    ]
                    time_axis_kind = "datetime"

        if not parse_datetime_succeeded:
            if numeric_ratio >= 0.6:
                local["__time_num__"] = raw_time_num
                local = local.dropna(subset=["__time_num__"]).sort_values("__time_num__")
                numeric_time_values = local["__time_num__"].to_numpy(dtype=float)
                x_values = []
                for v in numeric_time_values.tolist():
                    if np.isfinite(v) and abs(v - round(v)) < 1e-9:
                        x_values.append(int(round(v)))
                    else:
                        x_values.append(float(v))
                time_axis_kind = "numeric"
            else:
                local["__time__"] = raw_time.astype(str)
                local = local.sort_values("__time__")
                x_values = local["__time__"].astype(str).tolist()
                time_axis_kind = "categorical"
    else:
        local["__time__"] = np.arange(local.shape[0], dtype=int)
        x_values = [int(v) for v in local["__time__"].tolist()]
        time_axis_kind = "index"

    if local.shape[0] < 8:
        return {"error": "Недостаточно данных для анализа временного ряда (n < 8)"}

    y = local[value_col].to_numpy(dtype=float)
    n_obs = int(y.shape[0])
    idx = np.arange(n_obs, dtype=float)
    warnings: List[str] = []

    time_quality_flags: List[str] = []
    if time_col and time_col in df.columns:
        if n_unique_time < 3:
            time_quality_flags.append("insufficient_unique_time_points")
            warnings.append(
                f"Time column '{time_col}' contains only {n_unique_time} unique values; chronology may be unstable."
            )

        if time_axis_kind != "datetime":
            time_quality_flags.append("non_calendar_time_axis")
            if time_axis_kind == "numeric":
                warnings.append(
                    "Time axis is numeric; chronology is treated as an ordered sequence, not as calendar dates."
                )
            elif time_axis_kind == "categorical":
                warnings.append(
                    "Time axis is categorical text; chronology is sorted lexicographically. Use explicit calendar dates."
                )

        if (
            isinstance(datetime_parse_ratio, (int, float))
            and np.isfinite(float(datetime_parse_ratio))
            and float(datetime_parse_ratio) < 0.8
            and time_axis_kind != "datetime"
        ):
            time_quality_flags.append("low_datetime_parse_ratio")
            warnings.append(
                f"Only {float(datetime_parse_ratio) * 100.0:.1f}% of time values could be parsed as datetime."
            )

        if isinstance(time_min_year, int) and isinstance(time_max_year, int):
            current_year = int(pd.Timestamp.utcnow().year)
            if time_min_year <= 1971 and time_max_year <= 1985:
                time_quality_flags.append("epoch_artifact_risk")
                warnings.append(
                    "Calendar years are concentrated in 1970-1985; verify date parsing to avoid Unix-epoch artifacts."
                )
            elif time_min_year < 1990 or time_max_year > (current_year + 5):
                time_quality_flags.append("unusual_year_range")
                warnings.append(
                    f"Calendar year range looks unusual ({time_min_year}-{time_max_year}); verify chronology and source dates."
                )

    inferred_frequency: Optional[str] = None
    if time_index is not None and len(time_index) >= 3:
        try:
            inferred_frequency = pd.infer_freq(time_index)
        except Exception:
            inferred_frequency = None

    if "epoch_artifact_risk" in time_quality_flags or "unusual_year_range" in time_quality_flags:
        time_quality_level = "warning"
    elif time_quality_flags:
        time_quality_level = "caution"
    else:
        time_quality_level = "ok"

    time_quality: Dict[str, Any] = {
        "time_col_provided": bool(time_col and time_col in df.columns),
        "time_axis_kind": time_axis_kind,
        "n_unique_time": int(n_unique_time if (time_col and time_col in df.columns) else n_obs),
        "datetime_parse_attempted": bool(parse_datetime_attempted),
        "datetime_parse_succeeded": bool(parse_datetime_succeeded),
        "datetime_parse_ratio": (
            float(datetime_parse_ratio)
            if isinstance(datetime_parse_ratio, (int, float)) and np.isfinite(float(datetime_parse_ratio))
            else None
        ),
        "min_year": int(time_min_year) if isinstance(time_min_year, int) else None,
        "max_year": int(time_max_year) if isinstance(time_max_year, int) else None,
        "inferred_frequency": str(inferred_frequency) if isinstance(inferred_frequency, str) and inferred_frequency else None,
        "quality": time_quality_level,
        "flags": time_quality_flags or None,
    }

    slope, intercept, r_val, p_trend, _ = stats.linregress(idx, y)
    adf_stat = None
    adf_p = None
    adf_used_lag = None
    adf_crit = None
    try:
        adf_out = adfuller(y, autolag="AIC")
        adf_stat = float(adf_out[0])
        adf_p = float(adf_out[1])
        adf_used_lag = int(adf_out[2])
        adf_crit = {str(k): float(v) for k, v in (adf_out[4] or {}).items()}
    except Exception:
        adf_stat = None
        adf_p = None

    max_lags = kwargs.get("acf_lags")
    try:
        max_lags_i = int(max_lags)
    except Exception:
        max_lags_i = max(1, min(40, n_obs // 4))
    max_lags_i = max(1, min(max_lags_i, n_obs - 1))
    acf_rows: List[Dict[str, Any]] = []
    try:
        acf_vals = acf(y, nlags=max_lags_i, fft=True)
        acf_rows = [{"lag": int(i), "acf": float(acf_vals[i])} for i in range(len(acf_vals))]
    except Exception:
        acf_rows = []

    lag1 = None
    if len(acf_rows) > 1 and isinstance(acf_rows[1].get("acf"), (int, float)):
        lag1 = float(acf_rows[1]["acf"])

    lb_lag_raw = kwargs.get("ljung_lags")
    try:
        lb_lag = int(lb_lag_raw) if lb_lag_raw is not None else max(1, min(20, n_obs // 5))
    except Exception:
        lb_lag = max(1, min(20, n_obs // 5))
    lb_lag = max(1, min(lb_lag, n_obs - 1))
    lb_stat = None
    lb_p = None
    lb_white_noise = None
    try:
        lb_df = acorr_ljungbox(y, lags=[lb_lag], return_df=True)
        lb_stat = float(lb_df["lb_stat"].iloc[0])
        lb_p = float(lb_df["lb_pvalue"].iloc[0])
        lb_white_noise = bool(lb_p > alpha)
    except Exception:
        lb_stat = None
        lb_p = None
        lb_white_noise = None

    seasonal_period = kwargs.get("seasonal_period")
    try:
        period = int(seasonal_period) if seasonal_period is not None else None
    except Exception:
        period = None

    decomposition = None
    if isinstance(period, int) and period >= 2:
        if n_obs >= (2 * period):
            try:
                model_kind = str(kwargs.get("decompose_model") or "additive").strip().lower()
                if model_kind not in {"additive", "multiplicative"}:
                    model_kind = "additive"
                dec = seasonal_decompose(
                    pd.Series(y),
                    model=model_kind,
                    period=period,
                    extrapolate_trend="freq",
                )
                trend_vals = dec.trend.to_numpy(dtype=float)
                seasonal_vals = dec.seasonal.to_numpy(dtype=float)
                resid_vals = dec.resid.to_numpy(dtype=float)
                decomposition = {
                    "period": int(period),
                    "model": model_kind,
                    "trend": [float(v) if np.isfinite(v) else None for v in trend_vals.tolist()],
                    "seasonal": [float(v) if np.isfinite(v) else None for v in seasonal_vals.tolist()],
                    "resid": [float(v) if np.isfinite(v) else None for v in resid_vals.tolist()],
                }
            except Exception as e:
                warnings.append(
                    f"Seasonal decomposition failed and was skipped ({type(e).__name__})."
                )
        else:
            warnings.append(
                f"Seasonal decomposition skipped: need at least {2 * int(period)} observations for period={int(period)}."
            )

    forecast = None
    if forecast_horizon > 0:
        forecast_method = "holt_winters"
        try:
            seasonal_mode = "add" if isinstance(period, int) and period >= 2 and n_obs >= (2 * period) else None
            seasonal_periods = int(period) if seasonal_mode else None
            model = ExponentialSmoothing(
                y,
                trend="add",
                seasonal=seasonal_mode,
                seasonal_periods=seasonal_periods,
                initialization_method="estimated",
            )
            fit = model.fit(optimized=True, use_brute=False)
            y_forecast = np.asarray(fit.forecast(forecast_horizon), dtype=float)
        except Exception as e:
            forecast_method = "trend_extrapolation"
            warnings.append(
                f"Holt-Winters forecast failed; linear trend extrapolation was used ({type(e).__name__})."
            )
            y_forecast = np.asarray(
                [float(intercept + slope * (n_obs + i)) for i in range(forecast_horizon)],
                dtype=float,
            )

        future_x: List[Any] = []
        if time_index is not None and len(time_index) > 0:
            freq = None
            try:
                freq = pd.infer_freq(time_index)
            except Exception:
                freq = None
            future_idx = None
            if freq:
                try:
                    future_idx = pd.date_range(start=time_index[-1], periods=forecast_horizon + 1, freq=freq)[1:]
                except Exception:
                    future_idx = None
            if future_idx is None:
                try:
                    median_delta = time_index.to_series().diff().dropna().median()
                    if pd.isna(median_delta):
                        median_delta = pd.Timedelta(days=1)
                except Exception:
                    median_delta = pd.Timedelta(days=1)
                current = time_index[-1]
                future_idx = []
                for _ in range(forecast_horizon):
                    current = current + median_delta
                    future_idx.append(current)
            future_x = [str(v).replace(" 00:00:00", "") for v in list(future_idx)]
        elif numeric_time_values is not None and len(numeric_time_values) > 0:
            step = 1.0
            if len(numeric_time_values) > 1:
                try:
                    diffs = np.diff(numeric_time_values)
                    diffs = diffs[np.isfinite(diffs)]
                    if len(diffs):
                        med = float(np.median(diffs))
                        if np.isfinite(med) and abs(med) > 0:
                            step = med
                except Exception:
                    step = 1.0
            cur = float(numeric_time_values[-1])
            future_raw = [float(cur + step * (i + 1)) for i in range(forecast_horizon)]
            future_x = []
            for v in future_raw:
                if np.isfinite(v) and abs(v - round(v)) < 1e-9:
                    future_x.append(int(round(v)))
                else:
                    future_x.append(float(v))
        else:
            future_x = [int(n_obs + i) for i in range(forecast_horizon)]

        forecast = {
            "horizon": int(forecast_horizon),
            "method": forecast_method,
            "points": [
                {"x": future_x[i], "y": float(y_forecast[i])}
                for i in range(min(forecast_horizon, int(len(y_forecast))))
            ],
        }

    trend_sign = "upward" if slope > 0 else ("downward" if slope < 0 else "flat")
    trend_sign_ru = "восходящий" if slope > 0 else ("нисходящий" if slope < 0 else "плоский")
    stationary = bool(adf_p < alpha) if isinstance(adf_p, (int, float)) else None
    seasonality_note = "Seasonal pattern extracted." if isinstance(decomposition, dict) else "Seasonality not confirmed."
    seasonality_note_ru = "Сезонная компонента извлечена." if isinstance(decomposition, dict) else "Сезонность не подтверждена."
    lb_note = (
        f"Ljung-Box(p={float(lb_p):.4f}) -> {'white-noise-like' if lb_white_noise else 'autocorrelated'}."
        if isinstance(lb_p, (int, float))
        else "Ljung-Box not available."
    )
    lb_note_ru = (
        f"Ljung-Box(p={float(lb_p):.4f}) -> {'ряд ближе к белому шуму' if lb_white_noise else 'есть автокорреляция'}."
        if isinstance(lb_p, (int, float))
        else "Ljung-Box недоступен."
    )
    forecast_note = (
        f" Forecast generated for {forecast_horizon} step(s)."
        if isinstance(forecast, dict) and isinstance(forecast.get("points"), list) and forecast.get("points")
        else ""
    )
    forecast_note_ru = (
        f" Построен прогноз на {forecast_horizon} шаг(ов)."
        if isinstance(forecast, dict) and isinstance(forecast.get("points"), list) and forecast.get("points")
        else ""
    )
    time_quality_note = (
        " Time axis quality requires caution; verify chronology before interpreting trend and forecast."
        if time_quality_level in {"caution", "warning"}
        else ""
    )
    time_quality_note_ru = (
        " Качество временной оси требует осторожной интерпретации; проверьте хронологию перед выводами по тренду и прогнозу."
        if time_quality_level in {"caution", "warning"}
        else ""
    )

    interpretation = (
        f"Trend is {trend_sign} (slope={slope:.4f}, p={float(p_trend):.4f}). "
        + (
            f"ADF p={float(adf_p):.4f} -> {'stationary' if stationary else 'non-stationary'}."
            if isinstance(adf_p, (int, float))
            else "ADF not available."
        )
        + f" {seasonality_note} {lb_note}{forecast_note}{time_quality_note}"
    )
    interpretation_ru = (
        f"Тренд {trend_sign_ru} (наклон={slope:.4f}, p={float(p_trend):.4f}). "
        + (
            f"ADF p={float(adf_p):.4f} -> {'ряд стационарен' if stationary else 'ряд нестационарен'}."
            if isinstance(adf_p, (int, float))
            else "ADF недоступен."
        )
        + f" {seasonality_note_ru} {lb_note_ru}{forecast_note_ru}{time_quality_note_ru}"
    )

    plot_data = [
        {"x": x_values[i], "y": float(y[i]), "trend": float(intercept + slope * i)}
        for i in range(n_obs)
    ]
    if parse_datetime_attempted and not parse_datetime_succeeded:
        warnings.append(
            "Time column could not be reliably interpreted as calendar datetime; chronology interpretation may be unreliable."
        )

    if warnings:
        warnings_seen: set = set()
        warnings_clean: List[str] = []
        for raw in warnings:
            msg = str(raw).strip()
            if not msg or msg in warnings_seen:
                continue
            warnings_seen.add(msg)
            warnings_clean.append(msg)
        warnings = warnings_clean

    return {
        "method": "time_series_analysis",
        "value_col": value_col,
        "time_col": time_col or None,
        "time_axis_kind": time_axis_kind,
        "time_quality": time_quality,
        "n_observations": n_obs,
        "stat_value": float(adf_stat) if isinstance(adf_stat, (int, float)) else None,
        "p_value": float(adf_p) if isinstance(adf_p, (int, float)) else None,
        "significant": bool(stationary) if stationary is not None else None,
        "effect_size": float(slope),
        "effect_size_name": "trend_slope",
        "effect_size_interpretation": interpret_effect_size(float(lag1), "r") if isinstance(lag1, (int, float)) else None,
        "stationary": stationary,
        "trend": {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_val ** 2),
            "p_value": float(p_trend),
            "direction": trend_sign,
        },
        "autocorrelation": {
            "lag1": float(lag1) if isinstance(lag1, (int, float)) else None,
            "acf": acf_rows,
        },
        "diagnostics": {
            "ljung_box": {
                "lag": int(lb_lag),
                "statistic": float(lb_stat) if isinstance(lb_stat, (int, float)) else None,
                "p_value": float(lb_p) if isinstance(lb_p, (int, float)) else None,
                "white_noise_like": lb_white_noise,
            },
            "time_quality": time_quality,
        },
        "adf": {
            "statistic": float(adf_stat) if isinstance(adf_stat, (int, float)) else None,
            "p_value": float(adf_p) if isinstance(adf_p, (int, float)) else None,
            "used_lag": adf_used_lag,
            "critical_values": adf_crit,
        },
        "decomposition": decomposition,
        "forecast": forecast,
        "plot_data": plot_data,
        "plot_config": {"type": "line", "x_label": time_col or "index", "y_label": value_col},
        "warnings": warnings or None,
        "conclusion": interpretation_ru,
        "interpretation_en": interpretation,
    }

def _handle_chi_square(df, method_id, col_a, col_b, kwargs):
    ct = pd.crosstab(df[col_a], df[col_b])
    alpha = kwargs.get("alpha", 0.05)
    
    # Check expected frequencies for Fisher's Rule (if < 5 in >20% of cells, or any < 1, usually)
    # Simple rule: if any expected cell < 5 and table is 2x2 -> Fisher
    stat_val, p_val, dof, expected = stats.chi2_contingency(ct)
    
    warning = None
    min_expected = np.min(expected)
    
    switched_to_fisher = False
    if ct.shape == (2, 2) and min_expected < 5:
        # Switch to Fisher's Exact Test
        odds_ratio, p_val_fisher = stats.fisher_exact(ct)
        p_val = p_val_fisher
        warning = f"Low expected count ({min_expected:.2f} < 5). Auto-switched to Fisher's Exact Test."
        method_id = "fisher_exact"
        switched_to_fisher = True

    n_total = int(ct.to_numpy().sum()) if hasattr(ct, "to_numpy") else None
    cramers_v = None
    try:
        if n_total and n_total > 0:
            r, c = ct.shape
            denom = min(r - 1, c - 1)
            if denom > 0:
                phi2 = float(stat_val) / float(n_total)
                cramers_v = float(np.sqrt(phi2 / float(denom))) if phi2 >= 0 else None
    except Exception:
        cramers_v = None

    effect_value = None
    effect_name = None
    effect_interpretation = None
    if switched_to_fisher:
        try:
            effect_value = float(odds_ratio) if "odds_ratio" in locals() and odds_ratio is not None else None
        except Exception:
            effect_value = None
        effect_name = "odds_ratio" if effect_value is not None else None
        try:
            if effect_value is not None:
                effect_interpretation = interpret_effect_size(effect_value, "odds_ratio")
        except Exception:
            effect_interpretation = None
    else:
        try:
            effect_value = float(cramers_v) if cramers_v is not None else None
        except Exception:
            effect_value = None
        effect_name = "cramers_v" if effect_value is not None else None
        try:
            if effect_value is not None:
                effect_interpretation = interpret_effect_size(effect_value, "cramers_v")
        except Exception:
            effect_interpretation = None

    contingency = {
        "rows": [str(x) for x in ct.index.tolist()],
        "cols": [str(x) for x in ct.columns.tolist()],
        "counts": ct.values.tolist(),
        "n": n_total,
    }

    try:
        groups = [str(x) for x in ct.columns.tolist()]
    except Exception:
        groups = None

    plot_stats = None
    try:
        row_sums = ct.sum(axis=1)
        col_sums = ct.sum(axis=0)
        total = float(n_total or 0)
        if total > 0:
            row_pct = (row_sums / total * 100.0).round(2).to_dict()
            col_pct = (col_sums / total * 100.0).round(2).to_dict()
        else:
            row_pct, col_pct = {}, {}

        plot_stats = {
            "row_totals": {str(k): int(v) for k, v in row_sums.to_dict().items()},
            "col_totals": {str(k): int(v) for k, v in col_sums.to_dict().items()},
            "row_pct_total": {str(k): float(v) for k, v in row_pct.items()},
            "col_pct_total": {str(k): float(v) for k, v in col_pct.items()},
        }
    except Exception:
        plot_stats = None

    out = {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < alpha,
        "warning": warning,
        "contingency": contingency,
        "expected_min": float(min_expected) if min_expected is not None else None,
        "odds_ratio": float(odds_ratio) if "odds_ratio" in locals() and odds_ratio is not None else None,
        "effect_size": effect_value,
        "effect_size_name": effect_name,
        "effect_size_interpretation": effect_interpretation,
        "groups": groups,
        "plot_stats": plot_stats,
    }

    return out

def _handle_fisher_exact(df, method_id, col_a, col_b, kwargs):
    ct = pd.crosstab(df[col_a], df[col_b])
    alpha = kwargs.get("alpha", 0.05)

    if ct.shape != (2, 2):
        raise ValueError("Fisher's Exact Test requires a 2×2 contingency table")

    odds_ratio, p_val = stats.fisher_exact(ct)

    expected_min = None
    try:
        _, _, _, expected = stats.chi2_contingency(ct)
        expected_min = float(np.min(expected))
    except Exception:
        expected_min = None

    n_total = int(ct.to_numpy().sum()) if hasattr(ct, "to_numpy") else None
    contingency = {
        "rows": [str(x) for x in ct.index.tolist()],
        "cols": [str(x) for x in ct.columns.tolist()],
        "counts": ct.values.tolist(),
        "n": n_total,
    }

    try:
        groups = [str(x) for x in ct.columns.tolist()]
    except Exception:
        groups = None

    plot_stats = None
    try:
        row_sums = ct.sum(axis=1)
        col_sums = ct.sum(axis=0)
        total = float(n_total or 0)
        if total > 0:
            row_pct = (row_sums / total * 100.0).round(2).to_dict()
            col_pct = (col_sums / total * 100.0).round(2).to_dict()
        else:
            row_pct, col_pct = {}, {}

        plot_stats = {
            "row_totals": {str(k): int(v) for k, v in row_sums.to_dict().items()},
            "col_totals": {str(k): int(v) for k, v in col_sums.to_dict().items()},
            "row_pct_total": {str(k): float(v) for k, v in row_pct.items()},
            "col_pct_total": {str(k): float(v) for k, v in col_pct.items()},
        }
    except Exception:
        plot_stats = None

    effect_value = None
    effect_interpretation = None
    try:
        effect_value = float(odds_ratio) if odds_ratio is not None else None
    except Exception:
        effect_value = None
    try:
        if effect_value is not None:
            effect_interpretation = interpret_effect_size(effect_value, "odds_ratio")
    except Exception:
        effect_interpretation = None

    return {
        "method": method_id,
        "stat_value": float(odds_ratio) if odds_ratio is not None else 0.0,
        "p_value": float(p_val),
        "significant": float(p_val) < float(alpha),
        "warning": None,
        "contingency": contingency,
        "expected_min": expected_min,
        "odds_ratio": float(odds_ratio) if odds_ratio is not None else None,
        "effect_size": effect_value,
        "effect_size_name": "odds_ratio" if effect_value is not None else None,
        "effect_size_interpretation": effect_interpretation,
        "groups": groups,
        "plot_stats": plot_stats,
    }

def _handle_survival(df, method_id, col_a, col_b, kwargs):
    duration = df[col_a]
    event = df[col_b]
    alpha = kwargs.get("alpha", 0.05)
    group_col = kwargs.get("group_col")
    
    plot_data = []
    groups = ["Overall"]
    p_val = 1.0
    
    if group_col and group_col in df.columns:
        groups = sorted(df[group_col].dropna().unique())
        for g in groups:
            subset = df[df[group_col] == g]
            kmf = KaplanMeierFitter()
            kmf.fit(subset[col_a], event_observed=subset[col_b], label=str(g))
            for time, prob in zip(kmf.survival_function_.index, kmf.survival_function_.values.flatten()):
                 plot_data.append({"time": float(time), "probability": float(prob), "group": str(g)})
        
        if len(groups) == 2:
            g1 = df[df[group_col] == groups[0]]
            g2 = df[df[group_col] == groups[1]]
            results = logrank_test(g1[col_a], g2[col_a], event_observed_A=g1[col_b], event_observed_B=g2[col_b])
            p_val = results.p_value
    else:
        kmf = KaplanMeierFitter()
        kmf.fit(duration, event_observed=event)
        for time, prob in zip(kmf.survival_function_.index, kmf.survival_function_.values.flatten()):
             plot_data.append({"time": float(time), "probability": float(prob), "group": "Overall"})

    return {
        "method": method_id,
        "stat_value": 0.0,
        "p_value": float(p_val),
        "significant": p_val < alpha,
        "groups": groups,
        "plot_data": plot_data
    }

def _handle_regression(df, method_id, col_a, col_b, kwargs):
    predictors = kwargs.get("predictors", [col_b])
    covariates = kwargs.get("covariates", [])
    alpha = kwargs.get("alpha", 0.05)
    if not isinstance(predictors, list):
        predictors = [col_b]
    if not isinstance(covariates, list):
        covariates = []
    model_terms = [c for c in [*predictors, *covariates] if c]
    cols_to_clean = [col_a] + model_terms
    clean_df = df[cols_to_clean].dropna() # Re-clean locally for predictors
    if clean_df.empty:
        raise ValueError("Недостаточно данных для регрессии после очистки.")
    if col_a not in clean_df.columns:
        raise ValueError("Outcome колонка не найдена.")

    outcome = clean_df[col_a]
    X = pd.get_dummies(clean_df[model_terms], drop_first=True).astype(float)
    X = sm.add_constant(X)
    if X.shape[0] < 3:
        raise ValueError("Слишком мало наблюдений для регрессии.")
    if X.shape[1] == 0:
        raise ValueError("Нет предикторов после кодирования.")
    
    if method_id == "linear_regression":
        model = sm.OLS(outcome, X).fit()
        r_squared = model.rsquared
    else:
        # Logistic
        one_vs_rest = bool(kwargs.get("one_vs_rest", False))
        positive_label = kwargs.get("positive_label")
        outcome_non_na = outcome.dropna()
        if outcome_non_na.empty:
            raise ValueError("Логистическая регрессия требует непустой исход.")
        unique_vals = list(pd.unique(outcome_non_na))
        if len(unique_vals) != 2:
            if not one_vs_rest:
                raise ValueError(f"Logistic regression requires a binary outcome. Found {len(unique_vals)} unique values.")
            if positive_label is None:
                raise ValueError("one_vs_rest требует positive_label для бинаризации")
            if isinstance(positive_label, (int, float)):
                pos_val = float(positive_label)
                outcome = pd.to_numeric(outcome, errors="coerce").map(lambda v: 1.0 if v == pos_val else 0.0)
            else:
                positive_label = str(positive_label)
                outcome = outcome.astype(str).map(lambda v: 1.0 if str(v) == positive_label else 0.0)
            outcome_non_na = outcome.dropna()
            unique_vals = list(pd.unique(outcome_non_na))
            if len(unique_vals) != 2:
                raise ValueError("one_vs_rest: после бинаризации не найдено двух классов")

        if pd.api.types.is_numeric_dtype(outcome_non_na):
            as_float = outcome_non_na.astype(float)
            unique_num = sorted(set(float(v) for v in pd.unique(as_float)))
            if set(unique_num) == {0.0, 1.0}:
                outcome = outcome.astype(float)
            else:
                mapping = {unique_num[0]: 0.0, unique_num[1]: 1.0}
                outcome = outcome.astype(float).map(mapping)
        else:
            unique_str = sorted(str(v) for v in unique_vals)
            positive = unique_str[-1]
            outcome = outcome.astype(str).map(lambda v: 1.0 if v == positive else 0.0)
        class_counts = outcome.value_counts(dropna=True)
        if class_counts.min() < 2:
            raise ValueError("Логистическая регрессия требует минимум 2 наблюдения в каждом классе.")
        model = sm.Logit(outcome, X).fit(disp=0)
        r_squared = model.prsquared
        
    # Calculate VIF if requested (Linear Regression only usually, but can be done for X matrix)
    vif_data = {}
    if kwargs.get("vif", True) and len(model_terms) > 1:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        try:
            for i in range(X.shape[1]):
                col_name = X.columns[i]
                if col_name == 'const': continue
                v = variance_inflation_factor(X.values, i)
                vif_data[col_name] = v
        except Exception:
            pass

    show_ci = kwargs.get("ci", True)
    coef_data = []
    for name in model.params.index:
        entry = {
            "variable": name,
            "coefficient": float(model.params[name]),
            "p_value": float(model.pvalues[name]),
            "std_err": float(model.bse[name]),
            "ci_lower": float(model.conf_int().loc[name][0]) if show_ci else None,
            "ci_upper": float(model.conf_int().loc[name][1]) if show_ci else None,
            "vif": float(vif_data[name]) if name in vif_data else None
        }
        if method_id == "logistic_regression":
             entry["odds_ratio"] = float(np.exp(model.params[name]))
             # OR CI also respects show_ci? Yes usually.
             entry["or_ci_lower"] = float(np.exp(model.conf_int().loc[name][0])) if show_ci else None
             entry["or_ci_upper"] = float(np.exp(model.conf_int().loc[name][1])) if show_ci else None
        coef_data.append(entry)

    plot_data = []
    plot_config = None
    if len(model_terms) == 1 and model_terms[0] in clean_df.columns:
        predictor = model_terms[0]
        x_vals = pd.to_numeric(clean_df[predictor], errors="coerce")
        if method_id == "linear_regression":
            y_vals = pd.to_numeric(clean_df[col_a], errors="coerce")
        else:
            y_vals = pd.to_numeric(outcome, errors="coerce")
        mask = np.isfinite(x_vals) & np.isfinite(y_vals)
        idx = clean_df.index[mask]
        if len(idx) > 0:
            sample_idx = idx
            if len(sample_idx) > 1000:
                sample_idx = np.random.choice(sample_idx, 1000, replace=False)
            for i in sample_idx:
                plot_data.append({"x": float(x_vals.loc[i]), "y": float(y_vals.loc[i])})
            if plot_data:
                plot_config = {"x_label": predictor, "y_label": col_a}

    roc_out = None
    if method_id == "logistic_regression" and bool(kwargs.get("show_roc", True)):
        try:
            probs = model.predict(X)
            fpr, tpr, thresholds = roc_curve(outcome, probs)
            roc_auc = auc(fpr, tpr)
            roc_data = []
            step = max(1, len(fpr) // 500)
            for i in range(0, len(fpr), step):
                roc_data.append({
                    "x": float(fpr[i]),
                    "y": float(tpr[i]),
                    "threshold": float(thresholds[i])
                })
            if roc_data and roc_data[-1]["x"] != float(fpr[-1]):
                roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})
            roc_out = {
                "auc": float(roc_auc),
                "plot_data": roc_data,
                "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"},
            }
        except Exception:
            roc_out = None

    bootstrap_payload: Optional[Dict[str, Any]] = None
    bootstrap_enabled = bool(kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(kwargs.get("bootstrap_samples"), default=1000)
    if bootstrap_enabled:
        try:
            bootstrap_payload = _bootstrap_regression_payload(
                outcome,
                X,
                method_id=method_id,
                n_boot=bootstrap_samples,
            )
            if isinstance(bootstrap_payload, dict):
                metrics = bootstrap_payload.get("metrics") if isinstance(bootstrap_payload.get("metrics"), dict) else {}
                coef_rows = metrics.get("coefficients") if isinstance(metrics.get("coefficients"), list) else []
                coef_map = {
                    str(row.get("variable")): row
                    for row in coef_rows
                    if isinstance(row, dict) and str(row.get("variable") or "").strip()
                }
                for entry in coef_data:
                    if not isinstance(entry, dict):
                        continue
                    row = coef_map.get(str(entry.get("variable") or ""))
                    if not isinstance(row, dict):
                        continue
                    ci_l = row.get("ci_lower")
                    ci_u = row.get("ci_upper")
                    entry["bootstrap_ci_lower"] = ci_l
                    entry["bootstrap_ci_upper"] = ci_u
                    entry["bootstrap_n_valid"] = row.get("n_valid")
                    if show_ci and ci_l is not None and ci_u is not None:
                        entry["ci_lower"] = ci_l
                        entry["ci_upper"] = ci_u
                    if method_id == "logistic_regression":
                        or_l = row.get("or_ci_lower")
                        or_u = row.get("or_ci_upper")
                        entry["bootstrap_or_ci_lower"] = or_l
                        entry["bootstrap_or_ci_upper"] = or_u
                        if show_ci and or_l is not None and or_u is not None:
                            entry["or_ci_lower"] = or_l
                            entry["or_ci_upper"] = or_u
        except Exception as e:
            logger.warning(f"bootstrap_ci failed for regression ({method_id}): {e}")
            bootstrap_payload = {
                "enabled": True,
                "samples": int(bootstrap_samples),
                "ci_level": 0.95,
                "metrics": {},
                "error": str(e),
            }

    return {
        "method": method_id,
        "stat_value": float(model.fvalue) if hasattr(model, 'fvalue') else 0.0,
        "p_value": float(model.f_pvalue) if hasattr(model, 'f_pvalue') else float(model.pvalues.min()),
        "significant": any(model.pvalues < alpha),
        "r_squared": float(r_squared),
        "coefficients": coef_data,
        "aic": float(model.aic) if hasattr(model, 'aic') else None,
        "pseudo_r2": float(model.prsquared) if hasattr(model, 'prsquared') else None,
        "n_obs": int(model.nobs) if hasattr(model, 'nobs') else None,
        "roc": roc_out,
        "plot_data": plot_data,
        "plot_config": plot_config,
        "bootstrap": bootstrap_payload,
    }

def _handle_roc_analysis(df, method_id, col_a, col_b):
    y_true = df[col_b]
    y_score = df[col_a]
    classes = sorted(y_true.unique())
    
    if len(classes) != 2:
        raise ValueError(f"ROC Analysis requires exactly 2 classes. Found {len(classes)}.")
        
    pos_label = classes[1]
    neg_label = classes[0]
    y_true_bin = (y_true == pos_label).astype(int)
    
    fpr, tpr, thresholds = roc_curve(y_true_bin, y_score)
    roc_auc = auc(fpr, tpr)
    
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    
    roc_data = []
    step = max(1, len(fpr) // 500)
    for i in range(0, len(fpr), step):
        roc_data.append({
            "x": float(fpr[i]),
            "y": float(tpr[i]),
            "threshold": float(thresholds[i])
        })
    if roc_data[-1]["x"] != float(fpr[-1]):
         roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})
        
    return {
        "method": method_id,
        "auc": float(roc_auc),
        "best_threshold": float(thresholds[best_idx]),
        "youden_index": float(j_scores[best_idx]),
        "sensitivity": float(tpr[best_idx]),
        "specificity": float(1 - fpr[best_idx]),
        "pos_label": str(pos_label),
        "neg_label": str(neg_label),
        "significant": float(roc_auc) > 0.5,
        "plot_data": roc_data,
        "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"}
    }

def _prepare_group_plot_data(groups, data_groups):
    plot_data = []
    plot_stats = {}
    for i, g in enumerate(groups):
        vals = data_groups[i]
        mean = float(vals.mean())
        std = float(vals.std()) if len(vals) > 1 else 0
        n = len(vals)
        sem = std / np.sqrt(n) if n > 0 else 0
        ci_val = 1.96 * sem 
        
        plot_stats[str(g)] = {
            "mean": mean,
            "sd": std,
            "sem": sem,
            "ci_lower": mean - ci_val,
            "ci_upper": mean + ci_val,
            "median": float(vals.median()),
            "q1": float(vals.quantile(0.25)),
            "q3": float(vals.quantile(0.75)),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "count": int(n)
        }
        sample_vals = vals.sample(min(len(vals), 500)) if len(vals) > 500 else vals
        for v in sample_vals:
            plot_data.append({"group": str(g), "value": float(v)})
    return plot_data, plot_stats

def _check_assumptions(
    groups,
    data_groups,
    *,
    alpha: float = 0.05,
    normality_test: Optional[str] = None,
    normality_decision: Optional[str] = None,
    homogeneity_test: Optional[str] = None,
    homogeneity_center: Optional[str] = None,
):
    assumptions = {}
    if len(groups) >= 2:
         norm_results = {}
         for i, g in enumerate(groups):
             norm_diag = check_normality_with_policy(
                 data_groups[i],
                 normality_test=normality_test or "shapiro",
                 alpha=alpha,
                 decision_rule=normality_decision or "majority",
             )
             norm_results[str(g)] = {
                 "test": norm_diag.get("test"),
                 "p_value": norm_diag.get("p_value"),
                 "stat": norm_diag.get("stat"),
                 "passed": norm_diag.get("passed"),
                 "selected_tests": norm_diag.get("selected_tests"),
                 "decision_rule": norm_diag.get("decision_rule"),
                 "tests": norm_diag.get("tests"),
             }
         assumptions["normality"] = norm_results

         homo_diag = check_homogeneity_with_policy(
             data_groups,
             method=homogeneity_test or "levene",
             alpha=alpha,
             center=homogeneity_center or "median",
         )
         assumptions["homogeneity"] = {
             "test": homo_diag.get("test"),
             "center": homo_diag.get("center"),
             "p_value": homo_diag.get("p_value"),
             "stat": homo_diag.get("stat"),
             "passed": homo_diag.get("passed"),
         }
    return assumptions

def _generate_warnings(method_str, path_type="group", assumptions=None):
    warnings = []
    if path_type == "group":
        parametric_methods = ["t_test_ind", "t_test_welch", "t_test_rel", "anova", "rm_anova"]
        if method_str in parametric_methods:
            norm_res = assumptions.get("normality", {})
            failed_groups = [g for g, res in norm_res.items() if isinstance(res, dict) and res.get("passed") is False]
            if failed_groups:
                warnings.append(f"Normality assumption failed for groups: {', '.join(failed_groups)}. Consider using a non-parametric test.")
        
        strict_homogeneity = ["t_test_ind", "anova"]
        if method_str in strict_homogeneity:
            homo_res = assumptions.get("homogeneity")
            if isinstance(homo_res, dict) and homo_res.get("passed") is False:
                warnings.append("Homogeneity of variances assumption failed. Consider using Welch's T-test or Welch's ANOVA.")
    return warnings

def compute_descriptive_compare(df: pd.DataFrame, target: str, group: str) -> Dict[str, Any]:
    """
    Detailed descriptive statistics for Study Design / Table 1.
    Includes: Count, Mean, Median, SD, SE, IQR, Shapiro-Wilk (Normality).
    """
    import numpy as np
    from scipy import stats
    
    if group not in df.columns or target not in df.columns:
        return {}
        
    groups = df[group].dropna().unique()
    results: Dict[str, Any] = {}

    def _safe_float(v):
        try:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                return None
            return float(v)
        except Exception:
            return None

    def _safe_float3(v):
        out = _safe_float(v)
        if out is None:
            return None
        try:
            return float(round(out, 3))
        except Exception:
            return out

    def _compute(series_raw: pd.Series) -> Dict[str, Any]:
        series_num = pd.to_numeric(series_raw, errors="coerce")
        missing = int(series_num.isna().sum())
        valid = series_num.dropna()
        n = int(len(valid))

        if n == 0:
            return {
                "count": 0,
                "missing": missing,
                "mean": None,
                "median": None,
                "mode": None,
                "std": None,
                "se": None,
                "variance": None,
                "cv": None,
                "geometric_mean": None,
                "min": None,
                "max": None,
                "range": None,
                "q1": None,
                "q3": None,
                "iqr": None,
                "skewness": None,
                "kurtosis": None,
                "shapiro_w": None,
                "shapiro_p": None,
                "ci_95_low": None,
                "ci_95_high": None
            }

        mode_series = valid.mode(dropna=True)
        mode_val = mode_series.iloc[0] if not mode_series.empty else None

        mean = valid.mean()
        std = valid.std(ddof=1) if n > 1 else 0.0
        se = (std / np.sqrt(n)) if n > 1 else None

        cv = None
        try:
            mean_f = _safe_float(mean)
            std_f = _safe_float(std)
            if mean_f is not None and std_f is not None and mean_f != 0:
                cv = (std_f / mean_f) * 100
        except Exception:
            cv = None

        geometric_mean = None
        try:
            positives = valid[valid > 0]
            if int(len(positives)) > 0:
                geometric_mean = stats.gmean(positives.to_numpy(dtype=float))
        except Exception:
            geometric_mean = None

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)
        iqr = q3 - q1

        shapiro_w = None
        shapiro_p = None
        if n >= 3:
            shapiro_sample = valid
            if n > 5000:
                shapiro_sample = valid.sample(5000, random_state=0)
            sample_arr = shapiro_sample.to_numpy(dtype=float)
            if not _is_near_constant_array(sample_arr):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        w, p = stats.shapiro(sample_arr)
                    shapiro_w = _safe_float3(w)
                    shapiro_p = _safe_float3(p)
                except Exception:
                    shapiro_w = None
                    shapiro_p = None

        ci_95_low = None
        ci_95_high = None
        if se is not None:
            ci_95_low = _safe_float3(mean - 1.96 * se)
            ci_95_high = _safe_float3(mean + 1.96 * se)

        return {
            "count": n,
            "missing": missing,
            "mean": _safe_float3(mean),
            "median": _safe_float3(valid.median()),
            "mode": _safe_float3(mode_val),
            "std": _safe_float3(std),
            "se": _safe_float3(se),
            "variance": _safe_float3(valid.var(ddof=1) if n > 1 else 0.0),
            "cv": _safe_float3(cv),
            "geometric_mean": _safe_float3(geometric_mean),
            "min": _safe_float3(valid.min()),
            "max": _safe_float3(valid.max()),
            "range": _safe_float3(valid.max() - valid.min()),
            "q1": _safe_float3(q1),
            "q3": _safe_float3(q3),
            "iqr": _safe_float3(iqr),
            "skewness": _safe_float3(valid.skew()),
            "kurtosis": _safe_float3(valid.kurt()),
            "shapiro_w": shapiro_w,
            "shapiro_p": shapiro_p,
            "ci_95_low": ci_95_low,
            "ci_95_high": ci_95_high
        }

    for g in groups:
        group_mask = df[group] == g
        series_raw = df.loc[group_mask, target]
        results[str(g)] = _compute(series_raw)

    results["overall"] = _compute(df[target])
    
    return results

def run_batch_analysis(
    df: pd.DataFrame,
    targets: List[str],
    group_col: str,
    method_id: str = "t_test_ind",
    alpha: float = 0.05,
    auto_fallback: bool = True,
    multiplicity_correction: str = "fdr_bh",
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Runs analysis for multiple targets against a group column.
    Applies Benjamini-Hochberg (FDR) correction to p-values.
    """
    results = []
    p_values: List[Any] = []
    corr = _normalize_multiplicity_correction(multiplicity_correction, default="fdr_bh")
    
    # 1. Run Analysis for each target
    for target in targets:
        try:
            # Auto-detect method if needed, but usually batch implies same method
            # For MVP assume same method or auto-detect based on target type?
            # Let's enforce method_id for consistency in batch
            
            # Skip if target not in df
            if target not in df.columns:
                continue
                
            res = run_analysis(
                df,
                method_id,
                target,
                group_col,
                alpha=alpha,
                auto_fallback=auto_fallback,
                **kwargs,
            )
            
            # Store raw result
            res["target"] = target
            results.append(res)
            p_values.append(res.get("p_value"))
            
        except Exception as e:
            logger.error(f"Batch Error for {target}: {e}", exc_info=True)
            results.append({"target": target, "error": str(e), "p_value": None})
            p_values.append(None)
            
    # 2. Multiple testing correction + trace
    if results:
        corr_res = _apply_multiplicity_with_trace(p_values, alpha=alpha, correction=corr)
        pvals_corrected = corr_res.get("adjusted") if isinstance(corr_res, dict) else []
        reject = corr_res.get("rejected") if isinstance(corr_res, dict) else []
        method = corr_res.get("method") if isinstance(corr_res, dict) else corr
        trace = corr_res.get("trace") if isinstance(corr_res, dict) else None
        for i, res in enumerate(results):
            raw_p = p_values[i] if i < len(p_values) else None
            adj = pvals_corrected[i] if isinstance(pvals_corrected, list) and i < len(pvals_corrected) else None
            rej = reject[i] if isinstance(reject, list) and i < len(reject) else None
            res["p_value_raw"] = float(raw_p) if isinstance(raw_p, (int, float)) and np.isfinite(float(raw_p)) else None
            res["p_value_adj"] = float(adj) if isinstance(adj, (int, float)) and np.isfinite(float(adj)) else None
            res["significant_adj"] = bool(rej) if isinstance(rej, (bool, np.bool_)) else None
            res["multiplicity_correction"] = method
            if isinstance(trace, dict):
                # Compact per-item trace keeps auditability without changing outer API shape.
                res["multiplicity_trace"] = {
                    "method": trace.get("method"),
                    "alpha": trace.get("alpha"),
                    "n_total": trace.get("n_total"),
                    "n_valid": trace.get("n_valid"),
                    "index": i,
                }
            
    return results


def _compute_wide_delta(
    df: pd.DataFrame,
    baseline_col: str,
    follow_col: str,
    group_col: Optional[str] = None,
    subject_col: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    cols = [baseline_col, follow_col]
    if subject_col:
        cols.append(subject_col)
    if group_col:
        cols.append(group_col)
    local = df[[c for c in cols if c in df.columns]].copy()
    if baseline_col not in local.columns or follow_col not in local.columns:
        return None
    local[baseline_col] = pd.to_numeric(local[baseline_col], errors='coerce')
    local[follow_col] = pd.to_numeric(local[follow_col], errors='coerce')
    local = local.dropna(subset=[baseline_col, follow_col])
    if local.empty:
        return None

    if subject_col and subject_col in local.columns:
        by_cols = [subject_col]
        if group_col and group_col in local.columns:
            by_cols.append(group_col)
        local = local.groupby(by_cols, dropna=True, observed=False)[[baseline_col, follow_col]].mean().reset_index()
        local = local.dropna(subset=[baseline_col, follow_col])
        if local.empty:
            return None

    def summarize(block: pd.DataFrame) -> Dict[str, Any]:
        base = block[baseline_col]
        fol = block[follow_col]
        d = fol - base
        dp = None
        try:
            denom = base.replace(0, np.nan)
            dp = (d / denom) * 100
        except Exception:
            dp = None

        n = int(d.shape[0])
        mean_d = float(d.mean()) if n else None
        sd_d = float(d.std(ddof=1)) if n > 1 else None
        med_d = float(d.median()) if n else None

        mean_dp = float(dp.mean()) if (isinstance(dp, pd.Series) and dp.shape[0] > 0) else None
        med_dp = float(dp.median()) if (isinstance(dp, pd.Series) and dp.shape[0] > 0) else None

        es = None
        if sd_d is not None and sd_d != 0 and mean_d is not None:
            es = float(mean_d / sd_d)
        es_name = 'cohen_d' if es is not None else None
        es_interp = interpret_effect_size(es, es_name) if es is not None else None

        return {
            'n': n,
            'baseline_mean': float(base.mean()) if n else None,
            'follow_mean': float(fol.mean()) if n else None,
            'delta_abs_mean': mean_d,
            'delta_abs_sd': sd_d,
            'delta_abs_median': med_d,
            'delta_pct_mean': mean_dp,
            'delta_pct_median': med_dp,
            'effect_size': es,
            'effect_size_name': es_name,
            'effect_size_interpretation': es_interp,
        }

    out: Dict[str, Any] = {
        'baseline_col': str(baseline_col),
        'follow_col': str(follow_col),
        'overall': summarize(local),
    }

    if group_col and group_col in local.columns:
        by_group: Dict[str, Any] = {}
        for g, block in local.groupby(group_col, dropna=True, observed=False):
            by_group[str(g)] = summarize(block)
        out['by_group'] = by_group

    return out


# ============================================================
# NEW HANDLERS: Mixed Effects, RM-ANOVA, Friedman, Clustered Correlation
# ============================================================

def _handle_mixed_effects(df: pd.DataFrame, outcome: str, group_col: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Linear Mixed Model (Time × Group interaction).
    """
    time_col = kwargs.get("time_col")
    subject_col = kwargs.get("subject_col")
    covariates = kwargs.get("covariates", [])
    random_slope = kwargs.get("random_slope", False)
    alpha = kwargs.get("alpha", 0.05)
    
    if not time_col:
        return {"error": "time_col is required for mixed_effects"}
    if not subject_col:
        return {"error": "subject_col is required for mixed_effects"}
    
    engine = MixedEffectsEngine()
    result = engine.fit(
        df=df,
        outcome=outcome,
        time_col=time_col,
        group_col=group_col,
        subject_col=subject_col,
        covariates=covariates if covariates else None,
        random_slope=random_slope,
        alpha=alpha
    )
    
    if "error" not in result:
        result["method"] = "mixed_effects"
        result["significant"] = result.get("interaction", {}).get("significant", False)
        result["p_value"] = result.get("interaction", {}).get("min_p_value", 1.0)
    
    return result


def _handle_rm_anova(df: pd.DataFrame, outcome_prefix: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Repeated Measures ANOVA.
    """
    outcome_cols = kwargs.get("outcome_cols", [])
    subject_col = kwargs.get("subject_col")
    group_col = kwargs.get("group_col")
    alpha = kwargs.get("alpha", 0.05)
    
    if not outcome_cols:
        return {"error": "outcome_cols is required for rm_anova"}
    if not subject_col:
        return {"error": "subject_col is required for rm_anova"}
    
    engine = RepeatedMeasuresEngine()
    result = engine.fit(
        df=df,
        outcome_cols=outcome_cols,
        subject_col=subject_col,
        group_col=group_col,
        alpha=alpha
    )

    try:
        if isinstance(outcome_cols, list) and len(outcome_cols) >= 2:
            baseline_col = outcome_cols[0]
            follow_col = outcome_cols[-1]
            delta = _compute_wide_delta(
                df,
                baseline_col=baseline_col,
                follow_col=follow_col,
                group_col=group_col,
                subject_col=subject_col,
            )
            if delta is not None:
                result['delta'] = delta
    except Exception:
        pass
    
    if "error" not in result:
        result["method"] = "rm_anova"
        if result.get("interaction") and result["interaction"].get("p_value"):
            result["p_value"] = result["interaction"]["p_value"]
            result["significant"] = result["interaction"]["significant"]
        elif result.get("time_effect"):
            result["p_value"] = result["time_effect"]["p_value"]
            result["significant"] = result["time_effect"]["significant"]
        else:
            result["p_value"] = 1.0
            result["significant"] = False
    
    return result


def _handle_anova_twoway(df: pd.DataFrame, outcome: str, kwargs: Dict) -> Dict[str, Any]:
    group1 = str(kwargs.get("group1") or kwargs.get("factor_a") or "").strip()
    group2 = str(kwargs.get("group2") or kwargs.get("factor_b") or "").strip()
    alpha = kwargs.get("alpha", 0.05)

    if not outcome or outcome not in df.columns:
        return {"error": "outcome column not found"}
    if not group1 or group1 not in df.columns:
        return {"error": "group1 column not found"}
    if not group2 or group2 not in df.columns:
        return {"error": "group2 column not found"}

    local = df[[outcome, group1, group2]].copy().dropna()
    if local.empty:
        return {"error": "No data after filtering missing values"}

    try:
        aov = pg.anova(data=local, dv=outcome, between=[group1, group2], detailed=True)
    except Exception as e:
        return {"error": str(e)}

    # Add anova_table to result
    anova_table = aov.to_dict('records')

    def row_for(source: str):
        if not isinstance(aov, pd.DataFrame) or aov.empty:
            return None
        if "Source" not in aov.columns:
            return None
        hit = aov[aov["Source"] == source]
        if hit.empty:
            return None
        return hit.iloc[0]

    def to_effect(row: Optional[pd.Series]) -> Dict[str, Any]:
        if row is None:
            return {"stat_value": None, "p_value": None, "significant": False, "effect_size": None, "effect_size_name": None}
        f = row.get("F")
        p = row.get("p-unc")
        np2 = row.get("np2") if "np2" in row else None
        eta2 = row.get("eta2") if "eta2" in row else None
        es = np2 if np2 is not None else eta2
        es_name = "np2" if np2 is not None else ("eta2" if eta2 is not None else None)
        p_num = float(p) if isinstance(p, (int, float, np.floating)) else None
        sig = bool(p_num is not None and p_num < alpha)
        es_interp = interpret_effect_size(es, es_name) if es is not None else None
        return {
            "stat_value": float(f) if isinstance(f, (int, float, np.floating)) else None,
            "p_value": p_num,
            "significant": sig,
            "effect_size": float(es) if isinstance(es, (int, float, np.floating)) else None,
            "effect_size_name": es_name,
            "effect_size_interpretation": es_interp,
        }

    eff_a = to_effect(row_for(group1))
    eff_b = to_effect(row_for(group2))
    row_ab = row_for(f"{group1} * {group2}")
    if row_ab is None:
        row_ab = row_for(f"{group1}*{group2}")
    eff_ab = to_effect(row_ab)

    p_vals = [p for p in [eff_a.get("p_value"), eff_b.get("p_value"), eff_ab.get("p_value")] if isinstance(p, (int, float))]
    primary_p = min(p_vals) if p_vals else 1.0

    return {
        "method": "anova_twoway",
        "stat_value": eff_ab.get("stat_value") if eff_ab.get("stat_value") is not None else (eff_a.get("stat_value") or 0.0),
        "p_value": float(primary_p),
        "significant": bool(primary_p < alpha),
        "effects": {
            "factor_a": eff_a,
            "factor_b": eff_b,
            "interaction": eff_ab,
        },
    }


def _handle_friedman(df: pd.DataFrame, dummy: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Friedman test (non-parametric RM-ANOVA alternative).
    """
    outcome_cols = kwargs.get("outcome_cols", [])
    alpha = kwargs.get("alpha", 0.05)
    
    if not outcome_cols or len(outcome_cols) < 3:
        return {"error": "outcome_cols requires at least 3 columns for Friedman test"}
    
    data = df[outcome_cols].dropna()
    
    if len(data) < 3:
        return {"error": "Insufficient data for Friedman test"}
    
    try:
        stat_val, p_val = stats.friedmanchisquare(*[data[col] for col in outcome_cols])

        out: Dict[str, Any] = {
            "method": "friedman",
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < alpha,
            "n_subjects": len(data),
            "n_timepoints": len(outcome_cols)

        }

        try:
            baseline_col = outcome_cols[0]
            follow_col = outcome_cols[-1]
            delta = _compute_wide_delta(df, baseline_col=baseline_col, follow_col=follow_col, group_col=None)
            if delta is not None:
                out['delta'] = delta
        except Exception:
            pass

        return out
    except Exception as e:
        return {"error": str(e)}


def _handle_clustered_correlation(df: pd.DataFrame, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for clustered correlation analysis (jYS-style).
    """
    variables = kwargs.get("variables", [])
    method = kwargs.get("method", "pearson")
    linkage_method = kwargs.get("linkage_method", "ward")
    n_clusters = kwargs.get("n_clusters")
    alpha = kwargs.get("alpha", 0.05)
    
    if not variables or len(variables) < 2:
        return {"error": "Нужно выбрать минимум 2 переменные"}
    
    available_vars = [v for v in variables if v in df.columns]
    if len(available_vars) < 2:
        return {"error": f"В файле данных найдено только {len(available_vars)} переменных"}
    
    engine = ClusteredCorrelationEngine()
    result = engine.analyze(
        df=df,
        variables=available_vars,
        method=method,
        linkage_method=linkage_method,
        n_clusters=n_clusters,
        alpha=alpha
    )
    
    if "error" not in result:
        result["method"] = "clustered_correlation"
        p_values: List[float] = []
        heat = result.get("heatmap_data")
        if isinstance(heat, list):
            for cell in heat:
                if not isinstance(cell, dict):
                    continue
                if str(cell.get("row_var")) == str(cell.get("col_var")):
                    continue
                p_raw = cell.get("p")
                try:
                    p = float(p_raw)
                    if np.isfinite(p):
                        p_values.append(p)
                except Exception:
                    continue

        if p_values:
            min_p = float(min(p_values))
            result["p_value"] = min_p
            result["significant"] = bool(min_p < alpha)
        else:
            result["p_value"] = None
            result["significant"] = False

        corr_vals = []
        corr_m = result.get("correlation_matrix")
        if isinstance(corr_m, dict) and isinstance(corr_m.get("values"), list):
            values = corr_m.get("values")
            for i, row in enumerate(values):
                if not isinstance(row, list):
                    continue
                for j, item in enumerate(row):
                    if j <= i:
                        continue
                    try:
                        v = float(item)
                        if np.isfinite(v):
                            corr_vals.append(abs(v))
                    except Exception:
                        continue
        result["stat_value"] = float(max(corr_vals)) if corr_vals else None
    
    return result


def _resolve_numeric_variables(
    df: pd.DataFrame,
    kwargs: Dict[str, Any],
    *,
    fallback_cols: Optional[List[str]] = None,
    min_vars: int = 2,
) -> List[str]:
    candidate: List[str] = []
    raw_vars = kwargs.get("variables")
    if isinstance(raw_vars, list):
        candidate.extend([str(v) for v in raw_vars if isinstance(v, str) and v in df.columns])
    raw_targets = kwargs.get("targets")
    if isinstance(raw_targets, list):
        candidate.extend([str(v) for v in raw_targets if isinstance(v, str) and v in df.columns])
    raw_predictors = kwargs.get("predictors")
    if isinstance(raw_predictors, list):
        candidate.extend([str(v) for v in raw_predictors if isinstance(v, str) and v in df.columns])
    if isinstance(fallback_cols, list):
        candidate.extend([str(v) for v in fallback_cols if isinstance(v, str) and v in df.columns])

    seen: set = set()
    deduped: List[str] = []
    for col in candidate:
        if col in seen:
            continue
        seen.add(col)
        deduped.append(col)

    numeric = [c for c in deduped if pd.api.types.is_numeric_dtype(df[c])]
    if len(numeric) < int(min_vars):
        raise ValueError(f"Требуется минимум {int(min_vars)} числовых переменных")
    return numeric


def _to_binary_codes(series: pd.Series) -> tuple[pd.Series, List[str]]:
    s = series.copy()
    levels = sorted([str(v) for v in s.dropna().unique()], key=lambda x: x)
    if len(levels) != 2:
        raise ValueError("Переменная должна быть бинарной (ровно 2 уровня)")
    mapping = {levels[0]: 0, levels[1]: 1}
    coded = s.map(lambda v: mapping.get(str(v), np.nan))
    return coded, levels


def _handle_shapiro_wilk(df: pd.DataFrame, col_a: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    outcome = str(kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    if not outcome or outcome not in df.columns:
        return {"error": "outcome column not found"}

    s = pd.to_numeric(df[outcome], errors="coerce").dropna()
    if s.shape[0] < 3:
        return {"error": "Недостаточно данных для Shapiro-Wilk (n < 3)"}

    sample = s if s.shape[0] <= 5000 else s.sample(5000, random_state=42)
    sample_arr = sample.to_numpy(dtype=float)
    if _is_near_constant_array(sample_arr):
        return {
            "method": "shapiro_wilk",
            "stat_value": None,
            "p_value": None,
            "significant": None,
            "passed": False,
            "n_observations": int(s.shape[0]),
            "note": "near_constant_data",
        }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        stat_val, p_val = stats.shapiro(sample_arr)
    return {
        "method": "shapiro_wilk",
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": bool(float(p_val) < alpha),
        "passed": bool(float(p_val) > alpha),
        "n_observations": int(s.shape[0]),
    }


def _handle_bland_altman(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    m1 = str(kwargs.get("method_1") or kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    m2 = str(kwargs.get("method_2") or kwargs.get("group") or col_b).strip()
    if not m1 or m1 not in df.columns or not m2 or m2 not in df.columns:
        return {"error": "Для Bland-Altman нужны две числовые колонки"}

    local = df[[m1, m2]].copy()
    local[m1] = pd.to_numeric(local[m1], errors="coerce")
    local[m2] = pd.to_numeric(local[m2], errors="coerce")
    local = local.dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для Bland-Altman"}

    diff = local[m1] - local[m2]
    mean_pair = (local[m1] + local[m2]) / 2.0
    md = float(diff.mean())
    sd = float(diff.std(ddof=1))
    loa_low = float(md - 1.96 * sd)
    loa_high = float(md + 1.96 * sd)
    n_obs = int(local.shape[0])

    t_stat, p_val = stats.ttest_1samp(diff, popmean=0.0)
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=max(1, n_obs - 1)))
    se_md = float(sd / np.sqrt(max(1, n_obs)))
    md_ci_low = float(md - t_crit * se_md)
    md_ci_high = float(md + t_crit * se_md)

    # Approximate CI for limits of agreement (Bland & Altman, large-sample approximation).
    se_loa = float(sd * np.sqrt((1.0 / max(1, n_obs)) + ((1.96 ** 2) / (2.0 * max(1, n_obs - 1)))))
    loa_low_ci = [float(loa_low - t_crit * se_loa), float(loa_low + t_crit * se_loa)]
    loa_high_ci = [float(loa_high - t_crit * se_loa), float(loa_high + t_crit * se_loa)]

    out_mask = (diff < loa_low) | (diff > loa_high)
    n_out = int(out_mask.sum())
    frac_out = float(n_out / max(1, n_obs))

    pb_slope = None
    pb_intercept = None
    pb_p = None
    pb_r2 = None
    try:
        pb_slope, pb_intercept, pb_r, pb_p, _ = stats.linregress(mean_pair, diff)
        pb_slope = float(pb_slope)
        pb_intercept = float(pb_intercept)
        pb_p = float(pb_p)
        pb_r2 = float(pb_r ** 2)
    except Exception:
        pb_slope = None
        pb_intercept = None
        pb_p = None
        pb_r2 = None

    agreement = "good"
    agreement_ru = "хорошее"
    if frac_out > 0.1 or (isinstance(pb_p, (int, float)) and pb_p < alpha):
        agreement = "poor"
        agreement_ru = "низкое"
    elif frac_out > 0.05:
        agreement = "moderate"
        agreement_ru = "умеренное"

    interpretation_ru = (
        f"Смещение между методами: {md:.3f} "
        f"(95% ДИ [{md_ci_low:.3f}; {md_ci_high:.3f}]). "
        f"Границы согласия: [{loa_low:.3f}; {loa_high:.3f}], "
        f"вне границ {n_out}/{n_obs} ({frac_out*100:.1f}%). "
        + (
            f"Есть пропорциональное смещение (p={pb_p:.4f}). "
            if isinstance(pb_p, (int, float)) and pb_p < alpha
            else "Пропорциональное смещение не выявлено. "
        )
        + f"Итоговая оценка согласия: {agreement_ru}."
    )

    plot_rows = [
        {"x": float(mean_pair.iloc[i]), "y": float(diff.iloc[i])}
        for i in range(min(n_obs, 5000))
    ]
    x_min = float(mean_pair.min())
    x_max = float(mean_pair.max())
    return {
        "method": "bland_altman",
        "stat_value": float(t_stat) if np.isfinite(t_stat) else None,
        "p_value": float(p_val) if np.isfinite(p_val) else None,
        "significant": bool(float(p_val) < alpha) if np.isfinite(p_val) else None,
        "mean_difference": md,
        "mean_difference_ci_lower": md_ci_low,
        "mean_difference_ci_upper": md_ci_high,
        "sd_difference": sd,
        "loa_lower": loa_low,
        "loa_upper": loa_high,
        "loa_lower_ci": loa_low_ci,
        "loa_upper_ci": loa_high_ci,
        "n_observations": n_obs,
        "outside_loa_count": n_out,
        "outside_loa_fraction": frac_out,
        "proportional_bias": {
            "slope": pb_slope,
            "intercept": pb_intercept,
            "p_value": pb_p,
            "r_squared": pb_r2,
            "significant": bool(pb_p < alpha) if isinstance(pb_p, (int, float)) else None,
        },
        "agreement_rating": agreement,
        "agreement_interpretation": {
            "label": agreement,
            "label_ru": agreement_ru,
            "text_ru": interpretation_ru,
        },
        "conclusion": interpretation_ru,
        "plot_data": plot_rows,
        "plot_reference_lines": {
            "mean_difference": {"x1": x_min, "x2": x_max, "y": md},
            "loa_lower": {"x1": x_min, "x2": x_max, "y": loa_low},
            "loa_upper": {"x1": x_min, "x2": x_max, "y": loa_high},
            "zero": {"x1": x_min, "x2": x_max, "y": 0.0},
        },
        "plot_config": {
            "type": "bland_altman",
            "x_label": "Mean of two methods",
            "y_label": "Difference (method_1 - method_2)",
        },
    }


def _handle_icc(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    rating_col = str(kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    subject_col = str(kwargs.get("subject_col") or kwargs.get("subject") or "").strip()
    rater_col = str(kwargs.get("rater_col") or kwargs.get("rater") or col_b).strip()
    icc_type = str(kwargs.get("icc_type") or "ICC2").strip().upper()
    if not rating_col or rating_col not in df.columns:
        return {"error": "rating column not found"}
    if not subject_col or subject_col not in df.columns:
        return {"error": "subject_col is required for ICC"}
    if not rater_col or rater_col not in df.columns:
        return {"error": "rater_col is required for ICC"}

    local = df[[subject_col, rater_col, rating_col]].copy().dropna()
    local[rating_col] = pd.to_numeric(local[rating_col], errors="coerce")
    local = local.dropna(subset=[rating_col])
    if local.shape[0] < 4:
        return {"error": "Недостаточно данных для ICC"}

    tbl = pg.intraclass_corr(data=local, targets=subject_col, raters=rater_col, ratings=rating_col)
    row = tbl[tbl["Type"].astype(str).str.upper() == icc_type]
    if row.empty:
        row = tbl.iloc[[0]]
    r = row.iloc[0]
    p_val = float(r.get("pval")) if r.get("pval") is not None else None
    icc = float(r.get("ICC")) if r.get("ICC") is not None else None
    return {
        "method": "icc",
        "stat_value": float(r.get("F")) if r.get("F") is not None else None,
        "p_value": p_val,
        "significant": bool(p_val < alpha) if isinstance(p_val, (int, float)) else None,
        "effect_size": icc,
        "effect_size_name": "icc",
        "icc_type": str(r.get("Type")) if r.get("Type") is not None else icc_type,
        "ci95": [float(r.get("CI95%")[0]), float(r.get("CI95%")[1])] if isinstance(r.get("CI95%"), (list, tuple)) and len(r.get("CI95%")) == 2 else None,
        "n_observations": int(local.shape[0]),
    }


def _handle_cohens_kappa(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    a = str(kwargs.get("rater_a") or kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    b = str(kwargs.get("rater_b") or kwargs.get("group") or col_b).strip()
    if not a or a not in df.columns or not b or b not in df.columns:
        return {"error": "Для Cohen's kappa нужны две категориальные колонки"}

    local = df[[a, b]].copy().dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для Cohen's kappa"}
    kappa = float(cohen_kappa_score(local[a].astype(str), local[b].astype(str)))
    z = float(kappa) / float(np.sqrt((1.0 - kappa * kappa) / max(1, local.shape[0])))
    p_val = float(2.0 * stats.norm.sf(abs(z))) if np.isfinite(z) else None
    return {
        "method": "cohens_kappa",
        "stat_value": kappa,
        "p_value": p_val,
        "significant": bool(p_val < alpha) if isinstance(p_val, (int, float)) else None,
        "effect_size": kappa,
        "effect_size_name": "kappa",
        "n_observations": int(local.shape[0]),
    }


def _handle_mcnemar(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    before_col = str(kwargs.get("before") or kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    after_col = str(kwargs.get("after") or kwargs.get("group") or col_b).strip()
    if not before_col or before_col not in df.columns or not after_col or after_col not in df.columns:
        return {"error": "Для McNemar нужны две бинарные колонки"}

    local = df[[before_col, after_col]].copy().dropna()
    if local.shape[0] < 4:
        return {"error": "Недостаточно данных для McNemar"}
    b_codes, levels_b = _to_binary_codes(local[before_col].astype(str))
    a_codes, levels_a = _to_binary_codes(local[after_col].astype(str))
    coded = pd.DataFrame({"b": b_codes, "a": a_codes}).dropna()
    table = pd.crosstab(coded["b"], coded["a"]).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    exact = bool(kwargs.get("exact", True))
    res = sm_mcnemar(table, exact=exact, correction=not exact)
    p_val = float(res.pvalue) if res.pvalue is not None else None
    stat_val = float(res.statistic) if res.statistic is not None else None
    return {
        "method": "mcnemar",
        "stat_value": stat_val,
        "p_value": p_val,
        "significant": bool(p_val < alpha) if isinstance(p_val, (int, float)) else None,
        "n_observations": int(coded.shape[0]),
        "table": {
            "levels_before": levels_b,
            "levels_after": levels_a,
            "counts": table.values.tolist(),
        },
    }


def _handle_cochran_q(df: pd.DataFrame, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    outcome_cols = kwargs.get("outcome_cols") or kwargs.get("variables") or kwargs.get("targets")
    if not isinstance(outcome_cols, list) or len(outcome_cols) < 3:
        return {"error": "outcome_cols requires at least 3 binary columns for Cochran's Q"}
    cols = [str(c) for c in outcome_cols if isinstance(c, str) and c in df.columns]
    if len(cols) < 3:
        return {"error": "Недостаточно валидных колонок для Cochran's Q"}

    local = df[cols].copy().dropna()
    if local.shape[0] < 4:
        return {"error": "Недостаточно данных для Cochran's Q"}

    coded = local.copy()
    for c in cols:
        codes, _ = _to_binary_codes(coded[c].astype(str))
        coded[c] = codes
    coded = coded.dropna()
    if coded.shape[0] < 4:
        return {"error": "Недостаточно данных после бинарного кодирования"}

    res = sm_cochrans_q(coded.to_numpy(dtype=float))
    p_val = float(res.pvalue) if res.pvalue is not None else None
    stat_val = float(res.statistic) if res.statistic is not None else None
    return {
        "method": "cochran_q",
        "stat_value": stat_val,
        "p_value": p_val,
        "significant": bool(p_val < alpha) if isinstance(p_val, (int, float)) else None,
        "n_observations": int(coded.shape[0]),
        "n_conditions": int(len(cols)),
        "conditions": cols,
    }


def _handle_point_biserial(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    outcome = str(kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    group = str(kwargs.get("group") or kwargs.get("predictor") or col_b).strip()
    if not outcome or outcome not in df.columns or not group or group not in df.columns:
        return {"error": "Для point-biserial нужны outcome (numeric) и group (binary)"}

    local = df[[outcome, group]].copy().dropna()
    local[outcome] = pd.to_numeric(local[outcome], errors="coerce")
    local = local.dropna(subset=[outcome])
    codes, levels = _to_binary_codes(local[group].astype(str))
    local = local.assign(_bin=codes).dropna()
    if local.shape[0] < 4:
        return {"error": "Недостаточно данных для point-biserial"}

    r, p_val = stats.pointbiserialr(local["_bin"].to_numpy(dtype=float), local[outcome].to_numpy(dtype=float))
    return {
        "method": "point_biserial",
        "stat_value": float(r),
        "p_value": float(p_val),
        "effect_size": float(r),
        "effect_size_name": "point_biserial",
        "effect_size_interpretation": interpret_effect_size(float(r), "point_biserial"),
        "significant": bool(float(p_val) < alpha),
        "levels": levels,
        "n_observations": int(local.shape[0]),
    }


def _handle_partial_correlation(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    x = str(kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    y = str(kwargs.get("group") or kwargs.get("predictor") or col_b).strip()
    covariates = kwargs.get("covariates")
    if not isinstance(covariates, list):
        covariates = []
    covars = [str(c) for c in covariates if isinstance(c, str) and c in df.columns]
    method = str(kwargs.get("correlation_method") or "pearson").strip().lower()
    if method not in {"pearson", "spearman"}:
        method = "pearson"
    if not x or x not in df.columns or not y or y not in df.columns:
        return {"error": "Для partial_correlation нужны x и y переменные"}
    if not covars:
        return {"error": "Для partial_correlation нужна хотя бы одна ковариата"}

    cols = [x, y, *covars]
    local = df[cols].copy().dropna()
    if local.shape[0] < 5:
        return {"error": "Недостаточно данных для partial_correlation"}

    res = pg.partial_corr(data=local, x=x, y=y, covar=covars, method=method)
    row = res.iloc[0]
    r = float(row.get("r"))
    p_val = float(row.get("p-val"))
    ci_l, ci_u = _extract_ci_bounds(row.get("CI95%"))
    return {
        "method": "partial_correlation",
        "stat_value": r,
        "p_value": p_val,
        "effect_size": r,
        "effect_size_name": "partial_r",
        "effect_size_ci_lower": ci_l,
        "effect_size_ci_upper": ci_u,
        "effect_size_interpretation": interpret_effect_size(r, "r"),
        "significant": bool(p_val < alpha),
        "covariates": covars,
        "n_observations": int(local.shape[0]),
    }


def _handle_cronbach_alpha(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    variables = _resolve_numeric_variables(df, kwargs, fallback_cols=[col_a, col_b], min_vars=2)
    local = df[variables].copy().dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для Cronbach's alpha"}
    alpha_val, ci = pg.cronbach_alpha(local)
    ci_l = float(ci[0]) if isinstance(ci, (list, tuple)) and len(ci) == 2 else None
    ci_u = float(ci[1]) if isinstance(ci, (list, tuple)) and len(ci) == 2 else None
    return {
        "method": "cronbach_alpha",
        "stat_value": float(alpha_val),
        "p_value": None,
        "significant": None,
        "effect_size": float(alpha_val),
        "effect_size_name": "cronbach_alpha",
        "effect_size_ci_lower": ci_l,
        "effect_size_ci_upper": ci_u,
        "n_observations": int(local.shape[0]),
        "n_variables": int(len(variables)),
        "variables": variables,
    }


def _handle_ancova(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(kwargs.get("alpha", 0.05))
    show_ci = bool(kwargs.get("ci", True))
    outcome = str(kwargs.get("outcome") or kwargs.get("target") or col_a).strip()
    group = str(kwargs.get("group") or kwargs.get("group_col") or col_b).strip()
    covariates = kwargs.get("covariates")
    if not isinstance(covariates, list):
        covariates = []
    covars = [str(c) for c in covariates if isinstance(c, str) and c in df.columns and c != outcome and c != group]
    if not outcome or outcome not in df.columns:
        return {"error": "outcome column not found for ANCOVA"}
    if not group or group not in df.columns:
        return {"error": "group column not found for ANCOVA"}
    if not covars:
        return {"error": "ANCOVA requires at least one covariate"}

    cols = [outcome, group, *covars]
    local = df[cols].copy().dropna()
    local[outcome] = pd.to_numeric(local[outcome], errors="coerce")
    local = local.dropna(subset=[outcome])
    if local.shape[0] < 6:
        return {"error": "Недостаточно данных для ANCOVA"}

    anc = pg.ancova(data=local, dv=outcome, between=group, covar=covars)
    row_group = anc[anc["Source"] == group]
    if row_group.empty:
        row_group = anc.iloc[[0]]
    r = row_group.iloc[0]
    p_val = float(r.get("p-unc")) if r.get("p-unc") is not None else None
    eff = float(r.get("np2")) if r.get("np2") is not None else None

    eff_ci_lower = None
    eff_ci_upper = None
    bootstrap_payload: Optional[Dict[str, Any]] = None
    bootstrap_enabled = bool(kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(kwargs.get("bootstrap_samples"), default=1000)
    if bootstrap_enabled:
        try:
            bootstrap_payload = _bootstrap_ancova_payload(
                local,
                outcome=outcome,
                group=group,
                covars=covars,
                n_boot=bootstrap_samples,
            )
            if show_ci and isinstance(bootstrap_payload, dict):
                metrics = bootstrap_payload.get("metrics") if isinstance(bootstrap_payload.get("metrics"), dict) else {}
                effect_metric = metrics.get("effect_size") if isinstance(metrics.get("effect_size"), dict) else {}
                if effect_metric:
                    eff_ci_lower = effect_metric.get("ci_lower")
                    eff_ci_upper = effect_metric.get("ci_upper")
        except Exception as e:
            logger.warning(f"bootstrap_ci failed for ancova: {e}")
            bootstrap_payload = {
                "enabled": True,
                "samples": int(bootstrap_samples),
                "ci_level": 0.95,
                "metrics": {},
                "error": str(e),
            }

    return {
        "method": "ancova",
        "stat_value": float(r.get("F")) if r.get("F") is not None else None,
        "p_value": p_val,
        "significant": bool(p_val < alpha) if isinstance(p_val, (int, float)) else None,
        "effect_size": eff,
        "effect_size_name": "np2" if eff is not None else None,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "effect_size_interpretation": interpret_effect_size(eff, "np2") if eff is not None else None,
        "covariates": covars,
        "anova_table": anc.to_dict("records"),
        "n_observations": int(local.shape[0]),
        "bootstrap": bootstrap_payload,
    }


def _handle_pca(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    variables = _resolve_numeric_variables(df, kwargs, fallback_cols=[col_a, col_b], min_vars=2)
    local = df[variables].copy().dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для PCA"}

    scale = bool(kwargs.get("scale", True))
    x = local.to_numpy(dtype=float)
    if scale:
        x = StandardScaler().fit_transform(x)

    n_max = int(min(x.shape[0], x.shape[1]))
    n_components_raw = kwargs.get("n_components", kwargs.get("n_factors"))
    if isinstance(n_components_raw, str) and n_components_raw.strip().lower() in {"", "auto", "default"}:
        n_components_raw = None
    try:
        n_components = int(n_components_raw) if n_components_raw is not None else None
    except Exception:
        n_components = None
    if n_components is None:
        probe = PCA(n_components=n_max)
        probe.fit(x)
        eigenvalues = probe.explained_variance_
        kaiser = int(np.sum(eigenvalues > 1.0))
        n_components = kaiser if kaiser > 0 else min(2, n_max)
    n_components = max(1, min(n_max, int(n_components)))

    model = PCA(n_components=n_components)
    scores = model.fit_transform(x)
    loadings = model.components_.T
    explained_ratio = model.explained_variance_ratio_

    components: List[Dict[str, Any]] = []
    for i in range(int(n_components)):
        components.append(
            {
                "component": f"PC{i + 1}",
                "explained_variance_ratio": float(explained_ratio[i]),
                "eigenvalue": float(model.explained_variance_[i]),
                "loadings": {variables[j]: float(loadings[j, i]) for j in range(len(variables))},
            }
        )

    preview_n = min(500, scores.shape[0])
    scores_preview: List[Dict[str, Any]] = []
    for i in range(preview_n):
        row = {"row": int(i)}
        for j in range(int(n_components)):
            row[f"PC{j + 1}"] = float(scores[i, j])
        scores_preview.append(row)

    return {
        "method": "pca",
        "p_value": None,
        "significant": None,
        "stat_value": float(np.sum(explained_ratio)),
        "n_observations": int(local.shape[0]),
        "n_variables": int(len(variables)),
        "n_components": int(n_components),
        "variables": variables,
        "explained_variance_ratio": [float(v) for v in explained_ratio.tolist()],
        "explained_variance_total": float(np.sum(explained_ratio)),
        "components": components,
        "scores_preview": scores_preview,
    }


def _handle_efa(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    variables = _resolve_numeric_variables(df, kwargs, fallback_cols=[col_a, col_b], min_vars=3)
    local = df[variables].copy().dropna()
    if local.shape[0] < 6:
        return {"error": "Недостаточно данных для EFA"}

    scale = bool(kwargs.get("scale", True))
    rotation = str(kwargs.get("rotation", "varimax")).strip().lower()
    x = local.to_numpy(dtype=float)
    if scale:
        x = StandardScaler().fit_transform(x)

    n_max = int(min(x.shape[0], x.shape[1]))
    n_factors_raw = kwargs.get("n_factors", kwargs.get("n_components"))
    if isinstance(n_factors_raw, str) and n_factors_raw.strip().lower() in {"", "auto", "default"}:
        n_factors_raw = None
    try:
        n_factors = int(n_factors_raw) if n_factors_raw is not None else None
    except Exception:
        n_factors = None
    if n_factors is None:
        probe = PCA(n_components=n_max)
        probe.fit(x)
        eigenvalues = probe.explained_variance_
        kaiser = int(np.sum(eigenvalues > 1.0))
        n_factors = kaiser if kaiser > 0 else min(2, n_max)
    n_factors = max(1, min(n_max, int(n_factors)))

    model = FactorAnalysis(n_components=n_factors, random_state=42)
    scores = model.fit_transform(x)
    loadings = model.components_.T
    if rotation in {"varimax", "promax", "oblimin"}:
        # sklearn FactorAnalysis does not ship rotations; apply varimax as robust default.
        loadings = _varimax(loadings)
        rotation = "varimax"

    communalities = np.sum(np.square(loadings), axis=1)
    uniquenesses = np.clip(1.0 - communalities, 0.0, 1.0)

    factors: List[Dict[str, Any]] = []
    for i in range(int(n_factors)):
        factors.append(
            {
                "factor": f"F{i + 1}",
                "loadings": {variables[j]: float(loadings[j, i]) for j in range(len(variables))},
            }
        )

    return {
        "method": "efa",
        "p_value": None,
        "significant": None,
        "stat_value": float(np.mean(communalities)),
        "n_observations": int(local.shape[0]),
        "n_variables": int(len(variables)),
        "n_factors": int(n_factors),
        "rotation": rotation,
        "variables": variables,
        "communalities": {variables[i]: float(communalities[i]) for i in range(len(variables))},
        "uniquenesses": {variables[i]: float(uniquenesses[i]) for i in range(len(variables))},
        "factors": factors,
        "scores_preview": [
            {"row": int(i), **{f"F{j + 1}": float(scores[i, j]) for j in range(int(n_factors))}}
            for i in range(min(500, scores.shape[0]))
        ],
    }


def _handle_kmeans(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    variables = _resolve_numeric_variables(df, kwargs, fallback_cols=[col_a, col_b], min_vars=1)
    local = df[variables].copy().dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для k-means"}

    scale = bool(kwargs.get("scale", True))
    x = local.to_numpy(dtype=float)
    if scale:
        x = StandardScaler().fit_transform(x)

    n_clusters_raw = kwargs.get("n_clusters", kwargs.get("k", 3))
    try:
        n_clusters = int(n_clusters_raw)
    except Exception:
        n_clusters = 3
    n_clusters = max(2, min(20, n_clusters))
    if x.shape[0] <= n_clusters:
        return {"error": "Число кластеров должно быть меньше числа наблюдений"}

    random_state = int(kwargs.get("random_state", 42))
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(x)

    silhouette = None
    if n_clusters > 1 and x.shape[0] > n_clusters:
        try:
            silhouette = float(silhouette_score(x, labels))
        except Exception:
            silhouette = None

    centers = model.cluster_centers_
    cluster_sizes = {str(i): int(np.sum(labels == i)) for i in range(n_clusters)}

    projection = PCA(n_components=min(2, x.shape[1])).fit_transform(x)
    preview_n = min(1000, x.shape[0])
    points = []
    for i in range(preview_n):
        row = {"row": int(i), "cluster": int(labels[i]), "x": float(projection[i, 0])}
        row["y"] = float(projection[i, 1]) if projection.shape[1] > 1 else 0.0
        points.append(row)

    return {
        "method": "kmeans",
        "p_value": None,
        "significant": None,
        "stat_value": float(model.inertia_),
        "n_observations": int(local.shape[0]),
        "n_variables": int(len(variables)),
        "n_clusters": int(n_clusters),
        "variables": variables,
        "cluster_sizes": cluster_sizes,
        "cluster_centers": [
            {variables[j]: float(centers[i, j]) for j in range(len(variables))}
            for i in range(n_clusters)
        ],
        "silhouette": silhouette,
        "inertia": float(model.inertia_),
        "plot_data": points,
        "cluster_assignments": [int(v) for v in labels.tolist()],
    }


def _handle_hierarchical_clustering(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    variables = _resolve_numeric_variables(df, kwargs, fallback_cols=[col_a, col_b], min_vars=1)
    local = df[variables].copy().dropna()
    if local.shape[0] < 3:
        return {"error": "Недостаточно данных для иерархической кластеризации"}

    scale = bool(kwargs.get("scale", True))
    x = local.to_numpy(dtype=float)
    if scale:
        x = StandardScaler().fit_transform(x)

    linkage_method = str(kwargs.get("linkage_method", kwargs.get("linkage", "ward"))).strip().lower() or "ward"
    if linkage_method not in {"ward", "complete", "average", "single"}:
        linkage_method = "ward"

    n_clusters_raw = kwargs.get("n_clusters")
    distance_threshold_raw = kwargs.get("distance_threshold")
    n_clusters = None
    distance_threshold = None
    try:
        if n_clusters_raw is not None and str(n_clusters_raw).strip():
            n_clusters = max(2, min(20, int(n_clusters_raw)))
    except Exception:
        n_clusters = None
    try:
        if distance_threshold_raw is not None and str(distance_threshold_raw).strip():
            distance_threshold = float(distance_threshold_raw)
            if distance_threshold <= 0:
                distance_threshold = None
    except Exception:
        distance_threshold = None

    if n_clusters is None and distance_threshold is None:
        n_clusters = min(3, max(2, int(np.sqrt(max(4, x.shape[0])))))

    model = AgglomerativeClustering(
        n_clusters=n_clusters,
        distance_threshold=distance_threshold,
        linkage=linkage_method,
    )
    labels = model.fit_predict(x)
    n_out = int(len(np.unique(labels)))

    silhouette = None
    if n_out > 1 and x.shape[0] > n_out:
        try:
            silhouette = float(silhouette_score(x, labels))
        except Exception:
            silhouette = None

    z = scipy_linkage(x, method=linkage_method)
    leaves = [int(v) for v in leaves_list(z).tolist()]
    z_rows = [[float(v) for v in row] for row in z.tolist()]

    projection = PCA(n_components=min(2, x.shape[1])).fit_transform(x)
    points = []
    for i in range(min(1000, x.shape[0])):
        row = {"row": int(i), "cluster": int(labels[i]), "x": float(projection[i, 0])}
        row["y"] = float(projection[i, 1]) if projection.shape[1] > 1 else 0.0
        points.append(row)

    return {
        "method": "hierarchical_clustering",
        "p_value": None,
        "significant": None,
        "stat_value": silhouette,
        "n_observations": int(local.shape[0]),
        "n_variables": int(len(variables)),
        "n_clusters": int(n_out),
        "variables": variables,
        "linkage_method": linkage_method,
        "distance_threshold": distance_threshold,
        "cluster_assignments": [int(v) for v in labels.tolist()],
        "cluster_sizes": {str(i): int(np.sum(labels == i)) for i in sorted(np.unique(labels).tolist())},
        "dendrogram": {
            "linkage_matrix": z_rows,
            "leaves": leaves,
        },
        "plot_data": points,
        "silhouette": silhouette,
    }


def run_analysis(
    df: pd.DataFrame,
    method_id: str,
    col_a: str,
    col_b: str,
    is_paired: bool = False,
    alpha: float = 0.05,
    **kwargs,
) -> Dict[str, Any]:
    """
    Dispatch analysis to выбранному движку (python | r).
    """
    engine = kwargs.pop("engine", None)
    if engine is None:
        engine = kwargs.pop("stats_engine", None)
    if engine is None:
        engine = kwargs.pop("analysis_engine", None)
    plot_engine = kwargs.get("plot_engine")

    engine_norm = str(engine or "").strip().lower()
    if engine_norm in {"r", "r_engine", "rstats"}:
        try:
            from app.stats.r_engine import run_analysis_r
            return run_analysis_r(
                df,
                method_id,
                col_a,
                col_b,
                is_paired=is_paired,
                alpha=alpha,
                python_fallback=_run_analysis_python,
                plot_engine=plot_engine,
                **kwargs,
            )
        except Exception:
            # fallback to python engine if R fails
            return _run_analysis_python(
                df,
                method_id,
                col_a,
                col_b,
                is_paired=is_paired,
                alpha=alpha,
                **kwargs,
            )

    return _run_analysis_python(
        df,
        method_id,
        col_a,
        col_b,
        is_paired=is_paired,
        alpha=alpha,
        **kwargs,
    )
