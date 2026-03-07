from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


async def execute_paired_wide(
    df: pd.DataFrame,
    config: dict,
    alpha: float,
    *,
    runtime_kwargs: dict | None = None,
) -> dict:
    from app.api.v2 import (
        _analysis_runtime_kwargs,
        _as_bool,
        _bootstrap_ci_paired,
        _safe_bootstrap_samples,
        convert_numpy_to_native,
    )

    baseline = config.get("baseline")
    follow = config.get("follow")
    method_used = str(config.get("method") or config.get("method_id") or "t_test_rel").strip()
    alternative = config.get("alternative") or "two-sided"
    runtime_kwargs = runtime_kwargs if isinstance(runtime_kwargs, dict) else _analysis_runtime_kwargs(config)
    if not baseline or not follow:
        raise ValueError("paired_wide требует baseline и follow")
    if baseline not in df.columns or follow not in df.columns:
        raise ValueError("paired_wide: колонка baseline/follow не найдена")

    local = df[[baseline, follow]].copy()
    local[baseline] = pd.to_numeric(local[baseline], errors="coerce")
    local[follow] = pd.to_numeric(local[follow], errors="coerce")
    local = local.dropna(subset=[baseline, follow])
    if local.empty:
        raise ValueError("paired_wide: нет данных после фильтрации пропусков")

    x = local[baseline]
    y = local[follow]
    delta = y - x
    n = int(delta.shape[0])

    stat_val = None
    p_val = None
    eff_size = None
    eff_size_name = None
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    bf10 = None

    try:
        import pingouin as pg  # type: ignore
        import warnings as py_warnings

        if method_used == "wilcoxon":
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore", RuntimeWarning)
                res = pg.wilcoxon(x, y, alternative=alternative)
            stat_val = float(res["W-val"].iloc[0]) if "W-val" in res.columns else float(res["W"].iloc[0])
            p_val = float(res["p-val"].iloc[0])
            if "RBC" in res.columns:
                candidate = float(res["RBC"].iloc[0])
                if np.isfinite(candidate):
                    eff_size = candidate
                    eff_size_name = "rbc"
        else:
            method_used = "t_test_rel"
            with py_warnings.catch_warnings():
                py_warnings.simplefilter("ignore", RuntimeWarning)
                res = pg.ttest(x, y, paired=True, alternative=alternative, correction=False)
            stat_val = float(res["T"].iloc[0])
            p_val = float(res["p-val"].iloc[0])
            if "cohen-d" in res.columns:
                candidate = float(res["cohen-d"].iloc[0])
                if np.isfinite(candidate):
                    eff_size = candidate
                    eff_size_name = "cohen-d"
            if "CI95%" in res.columns:
                ci = res["CI95%"].iloc[0]
                if isinstance(ci, (list, tuple)) and len(ci) == 2:
                    lo = float(ci[0])
                    hi = float(ci[1])
                    if np.isfinite(lo) and np.isfinite(hi):
                        eff_ci_lower, eff_ci_upper = lo, hi
            if "power" in res.columns:
                try:
                    candidate = float(res["power"].iloc[0])
                    power = candidate if np.isfinite(candidate) else None
                except Exception:
                    power = None
            if "BF10" in res.columns:
                try:
                    candidate = float(res["BF10"].iloc[0])
                    bf10 = candidate if np.isfinite(candidate) else None
                except Exception:
                    bf10 = None
    except Exception as e:
        raise ValueError(f"paired_wide: ошибка вычисления ({e})")

    engine_mode = str(config.get("engine") or "").strip().lower()
    if engine_mode in {"r", "r_engine", "rstats"}:
        try:
            from app.stats.r_engine import run_analysis_r

            r_method = "wilcoxon" if method_used == "wilcoxon" else "t_test_rel"
            r_res = run_analysis_r(
                df,
                r_method,
                baseline,
                follow,
                is_paired=True,
                alpha=alpha,
                python_fallback=None,
                alternative=alternative,
            )
            if isinstance(r_res, dict):
                if r_res.get("p_value") is not None:
                    p_val = r_res.get("p_value")
                if r_res.get("stat_value") is not None:
                    stat_val = r_res.get("stat_value")
                if r_res.get("effect_size") is not None:
                    eff_size = r_res.get("effect_size")
                    eff_size_name = r_res.get("effect_size_name") or eff_size_name
        except Exception as e:
            logger.warning(f"paired_wide R engine failed: {e}")

    if eff_size is None and n > 1:
        try:
            sd = float(delta.std(ddof=1))
            mean_d = float(delta.mean())
            if sd != 0:
                eff_size = mean_d / sd
                eff_size_name = eff_size_name or "cohen-d"
        except Exception:
            pass

    bootstrap_payload = None
    bootstrap_enabled = bool(runtime_kwargs.get("bootstrap_ci", False))
    bootstrap_samples = _safe_bootstrap_samples(runtime_kwargs.get("bootstrap_samples"), default=1000)
    if bootstrap_enabled:
        bootstrap_payload = {
            "enabled": True,
            "samples": int(bootstrap_samples),
            "ci_level": 0.95,
            "metrics": {},
        }
        try:
            x_arr = x.to_numpy(dtype=float)
            y_arr = y.to_numpy(dtype=float)
            ci_mean_diff = _bootstrap_ci_paired(
                x_arr,
                y_arr,
                stat_fn=lambda a, b: float(np.mean(b - a)),
                n_boot=bootstrap_samples,
            )
            if ci_mean_diff is not None:
                bootstrap_payload["metrics"]["mean_diff"] = ci_mean_diff

            ci_effect = _bootstrap_ci_paired(
                x_arr,
                y_arr,
                stat_fn=lambda a, b: (
                    float(np.mean(b - a) / np.std(b - a, ddof=1))
                    if np.std(b - a, ddof=1) not in {0.0, -0.0}
                    else None
                ),
                n_boot=bootstrap_samples,
            )
            if ci_effect is not None:
                bootstrap_payload["metrics"]["effect_size"] = {**ci_effect, "name": "cohen_d_paired"}
                if _as_bool(config.get("ci"), default=True):
                    eff_ci_lower = float(ci_effect["ci_lower"])
                    eff_ci_upper = float(ci_effect["ci_upper"])
        except Exception as e:
            logger.warning(f"paired_wide bootstrap failed: {e}")

    def _desc(s: "pd.Series") -> dict:
        arr = s.dropna()
        if arr.empty:
            return {}
        return {
            "n": int(len(arr)),
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)) if len(arr) > 1 else None,
            "median": float(arr.median()),
            "q1": float(arr.quantile(0.25)),
            "q3": float(arr.quantile(0.75)),
            "min": float(arr.min()),
            "max": float(arr.max()),
        }

    descriptive = {
        baseline: _desc(x),
        follow: _desc(y),
        "delta": _desc(delta),
    }

    raw_pairs = []
    for bv, fv in zip(x.tolist(), y.tolist()):
        try:
            raw_pairs.append({"baseline": float(bv), "follow": float(fv)})
        except Exception:
            pass
    raw_pairs = raw_pairs[:200]

    waterfall_data = []
    if raw_pairs:
        try:
            for p in raw_pairs:
                bv = p.get("baseline")
                fv = p.get("follow")
                if bv is not None and fv is not None:
                    waterfall_data.append({"delta": float(fv) - float(bv)})
        except Exception:
            waterfall_data = []

    payload = {
        "type": "hypothesis_test",
        "method": {"id": "paired_wide", "name": "Paired Wide"},
        "test_used": method_used,
        "baseline": baseline,
        "follow": follow,
        "n": n,
        "stat_value": stat_val,
        "p_value": p_val,
        "significant": bool(p_val is not None and p_val < alpha),
        "effect_size": eff_size,
        "effect_size_name": eff_size_name,
        "effect_ci_lower": eff_ci_lower,
        "effect_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10,
        "delta_summary": {
            "mean": float(delta.mean()) if n else None,
            "median": float(delta.median()) if n else None,
            "std": float(delta.std(ddof=1)) if n > 1 else None,
            "min": float(delta.min()) if n else None,
            "max": float(delta.max()) if n else None,
        },
        "descriptive": descriptive,
        "raw_pairs": raw_pairs,
        "plot_hint": "paired_dot",
        "bootstrap": bootstrap_payload,
    }

    if len(waterfall_data) >= 2:
        payload["waterfall_data"] = waterfall_data
        payload["waterfall_result"] = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "waterfall",
            "baseline": baseline,
            "follow": follow,
            "waterfall_data": waterfall_data,
        }

    return convert_numpy_to_native(payload)
