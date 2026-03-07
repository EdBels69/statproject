from __future__ import annotations

import pandas as pd


async def execute_bland_altman(
    df: pd.DataFrame,
    config: dict,
    alpha: float,
    *,
    runtime_kwargs: dict | None = None,
) -> dict:
    from app.api.v2 import (
        _analysis_runtime_kwargs,
        _ensure_method,
        _maybe_add_conclusion,
        convert_numpy_to_native,
        run_analysis_async,
    )

    method_1 = config.get("method_1") or config.get("outcome") or config.get("target")
    method_2 = config.get("method_2") or config.get("group")
    if not method_1 or not method_2:
        raise ValueError("bland_altman требует method_1 и method_2")

    runtime_kwargs = runtime_kwargs if isinstance(runtime_kwargs, dict) else _analysis_runtime_kwargs(config)
    result = await run_analysis_async(
        df,
        "bland_altman",
        str(method_1),
        str(method_2),
        alpha,
        method_1=str(method_1),
        method_2=str(method_2),
        engine=config.get("engine"),
        **runtime_kwargs,
    )
    payload = convert_numpy_to_native({**result, "type": "agreement"})
    payload = _ensure_method(payload, "bland_altman")
    payload = _maybe_add_conclusion(payload, {"target": str(method_1), "group": str(method_2)})
    return payload
