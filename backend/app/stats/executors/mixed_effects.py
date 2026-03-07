from __future__ import annotations

import pandas as pd


async def execute_mixed_effects(
    df: pd.DataFrame,
    config: dict,
    alpha: float,
) -> dict:
    from app.api.v2 import _run_in_process_pool, _run_mixed_effects_sync, convert_numpy_to_native, run_analysis_async

    outcome = config.get("outcome")
    time_col = config.get("time")
    group_col = config.get("group")
    subject_col = config.get("subject")
    covariates = config.get("covariates", [])
    random_slope = config.get("random_slope", False)
    engine_mode = str(config.get("engine") or "").strip().lower()

    if engine_mode in {"r", "r_engine", "rstats"}:
        result = await run_analysis_async(
            df,
            "mixed_effects",
            outcome,
            group_col,
            alpha,
            group_col=group_col,
            time_col=time_col,
            subject_col=subject_col,
            covariates=covariates,
            random_slope=random_slope,
            engine=config.get("engine"),
        )
    else:
        result = await _run_in_process_pool(
            _run_mixed_effects_sync,
            df,
            outcome,
            time_col,
            group_col,
            subject_col,
            covariates,
            random_slope,
            alpha,
        )

    payload = {
        "type": "mixed_effects",
        "method": {"id": "mixed_effects", "name": "Mixed Effects"},
        **convert_numpy_to_native(result),
    }

    p_value = payload.get("interaction_p_value")
    if p_value is None:
        interaction = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else None
        p_value = interaction.get("min_p_value") if interaction else None
    if p_value is None:
        p_value = payload.get("p_value")
    payload["p_value"] = p_value
    payload["significant"] = bool(p_value < alpha) if isinstance(p_value, (int, float)) else None

    interaction = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else None
    interpretation = interaction.get("interpretation") if interaction else None
    if isinstance(interpretation, str) and interpretation.strip():
        payload["conclusion"] = interpretation.strip()

    return payload
