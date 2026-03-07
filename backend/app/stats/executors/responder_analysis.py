"""Responder analysis: proportion of patients meeting a threshold improvement."""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact


def execute_responder_analysis(
    df: pd.DataFrame,
    config: Dict[str, Any],
    alpha: float = 0.05,
    *,
    runtime_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute responder rates by group.

    Config keys:
        baseline (str): name of baseline column
        follow (str): name of follow-up column
        group (str): name of grouping column
        threshold (float): absolute delta threshold. Default = 0 (any improvement).
        direction (str): "decrease" (follow < baseline → improved) or "increase". Default "decrease".
        threshold_pct (float | None): if set, use relative threshold instead of absolute.
            E.g. 0.20 means ≥20% change.
    """
    _ = runtime_kwargs  # reserved for parity with other executors

    baseline_col = str(config.get("baseline") or "")
    follow_col = str(config.get("follow") or "")
    group_col = str(config.get("group") or "")
    threshold = float(config.get("threshold") or 0.0)
    direction = str(config.get("direction") or "decrease").lower().strip()
    threshold_pct = config.get("threshold_pct")

    errors = []

    # Validate columns
    for col in [baseline_col, follow_col]:
        if col and col not in df.columns:
            errors.append(f"Column not found: {col}")
    if errors:
        return {"type": "responder_analysis", "error": "; ".join(errors), "errors": errors}

    # Build working dataframe
    subset_cols = [c for c in [baseline_col, follow_col, group_col] if c and c in df.columns]
    work = df[subset_cols].dropna().copy()
    if len(work) < 4:
        return {"type": "responder_analysis", "error": "Too few complete cases after dropna", "errors": []}

    try:
        work["_baseline"] = pd.to_numeric(work[baseline_col], errors="coerce")
        work["_follow"] = pd.to_numeric(work[follow_col], errors="coerce")
        work = work.dropna(subset=["_baseline", "_follow"])
        work["_delta"] = work["_follow"] - work["_baseline"]

        # Determine responder
        if threshold_pct is not None:
            try:
                pct = float(threshold_pct)
                # relative change = delta / |baseline|
                work["_rel_change"] = work["_delta"] / work["_baseline"].abs().replace(0, np.nan)
                if direction == "decrease":
                    work["_responder"] = (work["_rel_change"] <= -pct).astype(int)
                else:
                    work["_responder"] = (work["_rel_change"] >= pct).astype(int)
            except Exception:
                work["_responder"] = 0
        else:
            if direction == "decrease":
                work["_responder"] = (work["_delta"] <= -threshold).astype(int)
            else:
                work["_responder"] = (work["_delta"] >= threshold).astype(int)

        # Overall responder rate
        n_total = len(work)
        n_resp_total = int(work["_responder"].sum())
        pct_total = 100 * n_resp_total / max(1, n_total)

        # By group
        groups_data = []
        group_responder_counts = []
        group_nonresponder_counts = []

        if group_col and group_col in work.columns:
            for grp, gdf in work.groupby(group_col):
                n_g = len(gdf)
                n_r = int(gdf["_responder"].sum())
                pct_r = 100 * n_r / max(1, n_g)
                groups_data.append(
                    {
                        "group": str(grp),
                        "n": n_g,
                        "n_responders": n_r,
                        "n_nonresponders": n_g - n_r,
                        "pct_responders": round(pct_r, 1),
                    }
                )
                group_responder_counts.append(n_r)
                group_nonresponder_counts.append(n_g - n_r)
        else:
            groups_data.append(
                {
                    "group": "Overall",
                    "n": n_total,
                    "n_responders": n_resp_total,
                    "n_nonresponders": n_total - n_resp_total,
                    "pct_responders": round(pct_total, 1),
                }
            )

        # Statistical test between groups
        p_value = None
        test_name = None
        if len(groups_data) == 2:
            ct = np.array(
                [
                    [group_responder_counts[0], group_nonresponder_counts[0]],
                    [group_responder_counts[1], group_nonresponder_counts[1]],
                ]
            )
            if ct.min() < 5:
                _, p_value = fisher_exact(ct)
                test_name = "Fisher's exact test"
            else:
                _, p_value, _, _ = chi2_contingency(ct, correction=False)
                test_name = "Chi-square test"
        elif len(groups_data) > 2:
            ct = np.array([[r["n_responders"], r["n_nonresponders"]] for r in groups_data])
            _, p_value, _, _ = chi2_contingency(ct, correction=False)
            test_name = "Chi-square test"

        # Build table
        table_rows = [["Группа", "N", "Ответили", "Не ответили", "%"]]
        for g in groups_data:
            table_rows.append(
                [
                    str(g["group"]),
                    str(g["n"]),
                    str(g["n_responders"]),
                    str(g["n_nonresponders"]),
                    f"{g['pct_responders']:.1f}%",
                ]
            )
        table_rows.append(
            [
                "Итого",
                str(n_total),
                str(n_resp_total),
                str(n_total - n_resp_total),
                f"{pct_total:.1f}%",
            ]
        )

        # Threshold description
        if threshold_pct is not None:
            thr_desc = f"≥{float(threshold_pct) * 100:.0f}% {'снижение' if direction == 'decrease' else 'прирост'}"
        else:
            thr_desc = f"{'снижение' if direction == 'decrease' else 'прирост'} ≥{threshold}"

        payload = {
            "type": "responder_analysis",
            "method": {"id": "responder_analysis", "name": "Responder Analysis"},
            "baseline": baseline_col,
            "follow": follow_col,
            "group": group_col,
            "threshold_description": thr_desc,
            "groups": groups_data,
            "n_total": n_total,
            "n_responders_total": n_resp_total,
            "pct_responders_total": round(pct_total, 1),
            "p_value": float(p_value) if p_value is not None else None,
            "test_name": test_name,
            "significant": (p_value is not None and float(p_value) < alpha),
            "table": table_rows,
            "plot_hint": "responder_bar",
            "waterfall_data": [
                {"delta": float(d), "responder": int(r)}
                for d, r in zip(work["_delta"].tolist(), work["_responder"].tolist())
            ],
        }
        return payload

    except Exception as e:
        return {"type": "responder_analysis", "error": str(e), "errors": [str(e)]}
