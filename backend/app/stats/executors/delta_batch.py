from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


async def execute_delta_batch_analysis(
    df: pd.DataFrame,
    config: dict,
    alpha: float,
    *,
    runtime_kwargs: dict | None = None,
) -> dict:
    from app.api.v2 import (
        _analysis_runtime_kwargs,
        _build_batch_multiplicity_trace,
        _normalize_correction,
        convert_numpy_to_native,
        run_batch_analysis,
    )

    group = config.get("group")
    pairs = config.get("pairs")
    if not group or not isinstance(pairs, list) or not pairs:
        raise ValueError("delta_batch_analysis требует group и pairs")
    if group not in df.columns:
        raise ValueError(f"delta_batch_analysis: колонка group не найдена: {group}")

    method_id_batch = config.get("method_id") or config.get("method") or "auto"
    multiplicity = _normalize_correction(config.get("multiplicity_correction")) or "fdr_bh"
    post_hoc = config.get("post_hoc")
    post_hoc_correction = _normalize_correction(config.get("post_hoc_correction"))
    auto_fallback = bool(config.get("auto_fallback", True))
    alternative = config.get("alternative")
    runtime_kwargs = runtime_kwargs if isinstance(runtime_kwargs, dict) else _analysis_runtime_kwargs(config)

    local = df.copy()
    delta_cols: List[str] = []
    pair_meta: Dict[str, Dict[str, Any]] = {}

    for idx, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            continue
        baseline = pair.get("baseline")
        follow = pair.get("follow")
        if not baseline or not follow:
            continue
        if baseline not in df.columns or follow not in df.columns:
            continue
        delta_col = f"delta_{idx+1}"
        local[delta_col] = pd.to_numeric(local[follow], errors="coerce") - pd.to_numeric(local[baseline], errors="coerce")
        delta_cols.append(delta_col)
        pair_meta[delta_col] = {
            "baseline": baseline,
            "follow": follow,
            "label": pair.get("label"),
        }

    if not delta_cols:
        raise ValueError("delta_batch_analysis: не удалось сформировать Δ-колонки")

    items = run_batch_analysis(
        local,
        delta_cols,
        group_col=group,
        method_id=method_id_batch,
        alpha=alpha,
        auto_fallback=auto_fallback,
        multiplicity_correction=multiplicity,
        post_hoc=post_hoc,
        post_hoc_correction=post_hoc_correction,
        engine=config.get("engine"),
        **({"alternative": alternative} if alternative else {}),
        **runtime_kwargs,
    )

    for item in items:
        if not isinstance(item, dict):
            continue
        meta = pair_meta.get(item.get("target"))
        if meta:
            item.update(meta)

    return {
        "type": "batch_analysis",
        "mode": "delta",
        "group": group,
        "method_id": method_id_batch,
        "items": convert_numpy_to_native(items),
        "pairs": list(pair_meta.values()),
        "multiplicity_correction": multiplicity,
        "multiplicity_trace": _build_batch_multiplicity_trace(
            items,
            alpha=float(alpha),
            correction=multiplicity,
            scope="delta",
        ),
        "post_hoc": post_hoc,
        "post_hoc_correction": post_hoc_correction,
    }
