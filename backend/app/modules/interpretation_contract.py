from typing import Any, Dict, Optional

import numpy as np


INTERPRETATION_KEYS = (
    "claim",
    "evidence",
    "clinical_meaning",
    "limitations",
    "actionable_next_step",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        num = float(value)
        if not np.isfinite(num):
            return None
        return num
    except Exception:
        return None


def _fmt_p(value: Any) -> str:
    p = _safe_float(value)
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def is_inferential_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    rtype = str(payload.get("type") or "").strip().lower()
    if rtype in {
        "compare",
        "hypothesis_test",
        "correlation",
        "regression",
        "survival",
        "mixed_effects",
        "clustered_correlation",
        "batch_analysis",
        "timepoint_batch_analysis",
        "delta_batch_analysis",
        "responders",
    }:
        return True
    if payload.get("p_value") is not None:
        return True
    if isinstance(payload.get("items"), list) and payload.get("items"):
        return True
    return False


def is_interpretation_contract_complete(contract: Any) -> bool:
    if not isinstance(contract, dict):
        return False
    for key in INTERPRETATION_KEYS:
        value = contract.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def _method_label(payload: Dict[str, Any]) -> str:
    method = payload.get("method")
    if isinstance(method, dict):
        text = _as_text(method.get("name") or method.get("id"))
        if text:
            return text
    if isinstance(method, str) and method.strip():
        return method.strip()
    method_id = _as_text(payload.get("method_id"))
    if method_id:
        return method_id
    return "statistical test"


def _extract_signal_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    p_value = _safe_float(payload.get("p_value"))
    effect = _safe_float(payload.get("effect_size"))
    power = _safe_float(payload.get("power"))
    alpha = _safe_float(payload.get("alpha"))
    significant = payload.get("significant")
    if not isinstance(significant, bool) and p_value is not None and alpha is not None:
        significant = bool(p_value < alpha)

    # Batch payload may not have top-level p_value.
    batch_items = payload.get("items")
    if isinstance(batch_items, list) and batch_items:
        total = 0
        sig = 0
        min_p = None
        for item in batch_items:
            if not isinstance(item, dict):
                continue
            total += 1
            p = _safe_float(item.get("p_value") if item.get("p_value") is not None else item.get("p_raw"))
            if p is not None:
                min_p = p if min_p is None else min(min_p, p)
            if bool(item.get("significant")) or bool(item.get("sig")):
                sig += 1
        if total > 0 and p_value is None:
            p_value = min_p
        return {
            "significant": bool(sig > 0),
            "batch_total": int(total),
            "batch_significant": int(sig),
            "p_value": p_value,
            "effect_size": effect,
            "power": power,
            "alpha": alpha,
        }

    return {
        "significant": bool(significant) if isinstance(significant, bool) else False,
        "batch_total": 0,
        "batch_significant": 0,
        "p_value": p_value,
        "effect_size": effect,
        "power": power,
        "alpha": alpha,
    }


def build_interpretation_contract(
    payload: Dict[str, Any],
    *,
    variables: Optional[Dict[str, Any]] = None,
    locale: str = "ru",
) -> Dict[str, str]:
    payload = payload if isinstance(payload, dict) else {}
    vars_map = variables if isinstance(variables, dict) else {}
    is_ru = str(locale).strip().lower().startswith("ru")

    target = _as_text(
        vars_map.get("target")
        or vars_map.get("outcome")
        or payload.get("target")
        or payload.get("outcome")
    ) or ("показатель" if is_ru else "outcome")
    group = _as_text(
        vars_map.get("group")
        or vars_map.get("predictor")
        or payload.get("group")
        or payload.get("group_column")
    )
    method = _method_label(payload)
    summary = _extract_signal_summary(payload)
    p_value = summary.get("p_value")
    effect = summary.get("effect_size")
    power = summary.get("power")
    batch_total = int(summary.get("batch_total") or 0)
    batch_significant = int(summary.get("batch_significant") or 0)
    significant = bool(summary.get("significant"))

    if batch_total > 0:
        if is_ru:
            claim = (
                f"В пакетном анализе показателя '{target}' значимые результаты получены для "
                f"{batch_significant} из {batch_total} тестов."
            )
        else:
            claim = (
                f"Batch analysis for '{target}' found significant results in "
                f"{batch_significant} of {batch_total} tests."
            )
    else:
        if is_ru:
            if significant:
                claim = f"Для показателя '{target}' выявлен статистически значимый эффект."
            else:
                claim = f"Для показателя '{target}' статистически значимый эффект не подтверждён."
        else:
            if significant:
                claim = f"A statistically significant effect was found for '{target}'."
            else:
                claim = f"No statistically significant effect was confirmed for '{target}'."

    if is_ru:
        evidence_parts = [f"Метод: {method}"]
        if group:
            evidence_parts.append(f"Группировка: {group}")
        evidence_parts.append(f"p={_fmt_p(p_value)}")
        if effect is not None:
            evidence_parts.append(f"effect={effect:.3f}")
        evidence = "; ".join(evidence_parts) + "."
    else:
        evidence_parts = [f"Method: {method}"]
        if group:
            evidence_parts.append(f"Grouping: {group}")
        evidence_parts.append(f"p={_fmt_p(p_value)}")
        if effect is not None:
            evidence_parts.append(f"effect={effect:.3f}")
        evidence = "; ".join(evidence_parts) + "."

    base_conclusion = _as_text(payload.get("ai_interpretation") or payload.get("conclusion"))
    if is_ru:
        if base_conclusion:
            clinical_meaning = base_conclusion
        elif significant:
            clinical_meaning = (
                "Эффект может иметь клиническое значение, но требует проверки на устойчивость и учет конфаундеров."
            )
        else:
            clinical_meaning = (
                "Текущее сравнение не дало убедительных клинических различий; возможно, эффект мал или данных недостаточно."
            )
    else:
        if base_conclusion:
            clinical_meaning = base_conclusion
        elif significant:
            clinical_meaning = "The effect may be clinically relevant, but robustness and confounding should be assessed."
        else:
            clinical_meaning = "Current comparison shows no clear clinical difference; the effect may be small or underpowered."

    limitations_bits = []
    if p_value is None:
        limitations_bits.append(
            "нет валидного p-value" if is_ru else "no valid p-value available"
        )
    if power is not None and power < 0.8:
        limitations_bits.append(
            f"низкая мощность ({power:.2f})" if is_ru else f"low power ({power:.2f})"
        )
    if not limitations_bits:
        limitations_bits.append(
            "результат требует внешней валидации" if is_ru else "result requires external validation"
        )
    limitations = "; ".join(limitations_bits) + "."

    if is_ru:
        if significant:
            actionable_next_step = (
                "Провести чувствительный анализ (стратификация/ковариаты), затем проверить воспроизводимость на фиксированной выборке."
            )
        else:
            actionable_next_step = (
                "Уточнить гипотезу и усилить дизайн: увеличить N, добавить релевантные ковариаты и повторить анализ."
            )
    else:
        if significant:
            actionable_next_step = "Run sensitivity analyses (stratification/covariates) and validate on a fixed cohort."
        else:
            actionable_next_step = "Refine the hypothesis and strengthen design: increase N, add covariates, and rerun."

    return {
        "claim": claim,
        "evidence": evidence,
        "clinical_meaning": clinical_meaning,
        "limitations": limitations,
        "actionable_next_step": actionable_next_step,
    }


def normalize_interpretation_contract(
    raw_contract: Any,
    payload: Dict[str, Any],
    *,
    variables: Optional[Dict[str, Any]] = None,
    locale: str = "ru",
) -> Dict[str, str]:
    generated = build_interpretation_contract(payload, variables=variables, locale=locale)
    out: Dict[str, str] = {}
    src = raw_contract if isinstance(raw_contract, dict) else {}
    for key in INTERPRETATION_KEYS:
        val = _as_text(src.get(key))
        out[key] = val if val else generated.get(key, "")
    return out

