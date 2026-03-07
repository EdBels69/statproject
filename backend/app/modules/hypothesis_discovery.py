from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set


DEFAULT_MAX_ITEMS = 8


def _as_text_list(value: Any, *, limit: int = 20) -> List[str]:
    items: List[str] = []
    if isinstance(value, list):
        for raw in value:
            text = str(raw).strip() if raw is not None else ""
            if text:
                items.append(text)
    elif value is not None:
        text = str(value).strip()
        if text:
            items.append(text)
    if not items:
        return []

    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _normalize_mode(preferences: Optional[Dict[str, Any]]) -> str:
    prefs = preferences if isinstance(preferences, dict) else {}
    mode = str(prefs.get("analysis_mode") or prefs.get("mode") or "exploratory").strip().lower()
    if mode in {"publication", "confirmatory", "focused", "exploratory"}:
        return mode
    if mode in {"publish", "manuscript"}:
        return "publication"
    if mode in {"standard", "targeted"}:
        return "focused"
    return "exploratory"


def _read_subgroups(preferences: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(preferences, dict):
        return []

    raw = preferences.get("subgroup_columns")
    if isinstance(raw, list):
        return _as_text_list(raw, limit=12)

    text = str(raw or "").strip()
    if not text:
        return []
    return _as_text_list([part.strip() for part in text.split(",")], limit=12)


def _pick_design(dataset_meta: Dict[str, Any]) -> Dict[str, Any]:
    study_design = dataset_meta.get("study_design") if isinstance(dataset_meta, dict) else None
    if isinstance(study_design, dict) and isinstance(study_design.get("design"), dict):
        return study_design.get("design") or {}
    return {}


def _pick_summary(dataset_meta: Dict[str, Any]) -> Dict[str, Any]:
    summary = dataset_meta.get("summary") if isinstance(dataset_meta, dict) else None
    return summary if isinstance(summary, dict) else {}


def _pick_numeric_candidates(dataset_meta: Dict[str, Any], design: Dict[str, Any]) -> List[str]:
    from_design = _as_text_list(design.get("outcomes"), limit=24)
    from_meta = _as_text_list(dataset_meta.get("numeric_cols"), limit=24) if isinstance(dataset_meta, dict) else []
    return _as_text_list(from_design + from_meta, limit=24)


def _pick_categorical_candidates(dataset_meta: Dict[str, Any], design: Dict[str, Any]) -> List[str]:
    from_design = _as_text_list(design.get("categorical_outcomes"), limit=24)
    from_meta = _as_text_list(dataset_meta.get("categorical_cols"), limit=24) if isinstance(dataset_meta, dict) else []
    return _as_text_list(from_design + from_meta, limit=24)


def _coerce_max_items(value: Any) -> int:
    try:
        return max(1, min(20, int(value)))
    except Exception:
        return DEFAULT_MAX_ITEMS


def build_hypothesis_discovery(
    *,
    dataset_meta: Optional[Dict[str, Any]],
    preferences: Optional[Dict[str, Any]] = None,
    protocol: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    meta = dataset_meta if isinstance(dataset_meta, dict) else {}
    mode = _normalize_mode(preferences)
    design = _pick_design(meta)
    summary = _pick_summary(meta)
    n_rows = summary.get("n_rows")
    try:
        n_rows = int(n_rows) if n_rows is not None else None
    except Exception:
        n_rows = None

    group_col = str(design.get("group_column") or "").strip() or None
    time_col = str(design.get("time_column") or "").strip() or None
    subject_col = str(design.get("subject_column") or "").strip() or None
    design_type = str(design.get("design_type") or "").strip() or None

    numeric = _pick_numeric_candidates(meta, design)
    categorical = _pick_categorical_candidates(meta, design)
    subgroups = _read_subgroups(preferences)

    top_numeric = numeric[0] if numeric else None
    second_numeric = numeric[1] if len(numeric) > 1 else None
    top_categorical = categorical[0] if categorical else None

    max_items = _coerce_max_items((preferences or {}).get("hypotheses_max") if isinstance(preferences, dict) else None)
    findings: List[Dict[str, Any]] = []
    seen_keys: Set[str] = set()

    def _append(
        *,
        hypothesis_id: str,
        title: str,
        h0: str,
        h1: str,
        rationale: str,
        suggested_method: str,
        variables: Dict[str, Any],
        priority: str,
    ) -> None:
        if len(findings) >= max_items:
            return
        key = f"{hypothesis_id}|{title}|{suggested_method}".lower()
        if key in seen_keys:
            return
        seen_keys.add(key)
        findings.append(
            {
                "id": hypothesis_id,
                "title": title,
                "h0": h0,
                "h1": h1,
                "rationale": rationale,
                "suggested_method": suggested_method,
                "priority": priority,
                "variables": variables,
            }
        )

    if group_col and top_numeric:
        _append(
            hypothesis_id="h_group_numeric",
            title=f"Сравнить {top_numeric} между группами {group_col}",
            h0=f"Распределение/среднее {top_numeric} не различается между уровнями {group_col}.",
            h1=f"{top_numeric} различается минимум между двумя уровнями {group_col}.",
            rationale="В дизайне задана группирующая переменная и числовой исход.",
            suggested_method="t_test_ind / mann_whitney / anova",
            variables={"outcome": top_numeric, "group": group_col},
            priority="high",
        )

    if group_col and time_col and subject_col and top_numeric:
        _append(
            hypothesis_id="h_time_group_interaction",
            title=f"Проверить Time x Group эффект для {top_numeric}",
            h0=f"Взаимодействие {time_col} x {group_col} для {top_numeric} отсутствует.",
            h1=f"Эффект времени для {top_numeric} зависит от {group_col}.",
            rationale="Дизайн содержит время, группу и идентификатор субъекта.",
            suggested_method="mixed_effects",
            variables={"outcome": top_numeric, "time": time_col, "group": group_col, "subject": subject_col},
            priority="high",
        )

    if group_col and top_categorical:
        _append(
            hypothesis_id="h_group_categorical",
            title=f"Оценить связь {group_col} и {top_categorical}",
            h0=f"{group_col} и {top_categorical} независимы.",
            h1=f"Между {group_col} и {top_categorical} есть ассоциация.",
            rationale="Есть категориальный исход и группирующая переменная.",
            suggested_method="chi_square / fisher_exact",
            variables={"outcome": top_categorical, "group": group_col},
            priority="medium",
        )

    if top_numeric and second_numeric:
        _append(
            hypothesis_id="h_numeric_association",
            title=f"Проверить связь между {top_numeric} и {second_numeric}",
            h0=f"Линейной/монотонной связи между {top_numeric} и {second_numeric} нет.",
            h1=f"Между {top_numeric} и {second_numeric} есть статистическая связь.",
            rationale="В наборе определены как минимум два числовых исхода.",
            suggested_method="pearson / spearman",
            variables={"x": top_numeric, "y": second_numeric},
            priority="medium",
        )

    if time_col and top_numeric:
        _append(
            hypothesis_id="h_time_trend",
            title=f"Проверить тренд {top_numeric} во времени ({time_col})",
            h0=f"Во времени ({time_col}) для {top_numeric} систематического тренда нет.",
            h1=f"Для {top_numeric} есть значимый временной тренд.",
            rationale="Определен временной столбец и числовой исход.",
            suggested_method="time_series_analysis / mixed_effects",
            variables={"outcome": top_numeric, "time": time_col},
            priority="medium",
        )

    if mode == "exploratory" and len(numeric) >= 3:
        _append(
            hypothesis_id="h_latent_structure",
            title="Выявить латентную структуру числовых исходов",
            h0="Данные не содержат устойчивой латентной факторной структуры.",
            h1="В данных есть интерпретируемая латентная структура.",
            rationale="Эксплораторный режим и достаточное число числовых переменных.",
            suggested_method="pca / efa",
            variables={"variables": numeric[:8]},
            priority="low",
        )
        _append(
            hypothesis_id="h_patient_clusters",
            title="Проверить наличие кластеров наблюдений",
            h0="Четких кластеров в многомерном пространстве исходов нет.",
            h1="Наблюдения образуют статистически различимые кластеры.",
            rationale="Эксплораторный профиль допускает сегментацию без confirmatory утверждений.",
            suggested_method="kmeans / hierarchical_clustering",
            variables={"variables": numeric[:8]},
            priority="low",
        )

    if group_col and top_numeric and subgroups:
        for subgroup in subgroups[:2]:
            _append(
                hypothesis_id=f"h_subgroup_{subgroup}",
                title=f"Оценить эффект {group_col} на {top_numeric} в подгруппе {subgroup}",
                h0=f"Эффект {group_col} на {top_numeric} не зависит от {subgroup}.",
                h1=f"Эффект {group_col} на {top_numeric} различается между уровнями {subgroup}.",
                rationale="Пользователь явно задал подгруппы для стратификации анализа.",
                suggested_method="batch_analysis / timepoint_batch_analysis",
                variables={"outcome": top_numeric, "group": group_col, "subgroup": subgroup},
                priority="medium",
            )

    if subject_col and len(numeric) >= 2:
        _append(
            hypothesis_id="h_within_subject_change",
            title=f"Проверить внутри-субъектную динамику по {subject_col}",
            h0="Внутри-субъектные изменения между измерениями отсутствуют.",
            h1="Внутри-субъектные изменения статистически значимы.",
            rationale="Найден идентификатор субъекта и минимум два числовых исхода.",
            suggested_method="rm_anova / friedman / paired_wide",
            variables={"subject": subject_col, "outcome_cols": numeric[:4]},
            priority="medium",
        )

    # Optional protocol-derived hypothesis anchors.
    if isinstance(protocol, list):
        for idx, step in enumerate(protocol[: max_items * 2]):
            if len(findings) >= max_items:
                break
            if not isinstance(step, dict):
                continue
            method = str(step.get("method") or "").strip().lower()
            cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
            outcome = str(cfg.get("outcome") or cfg.get("target") or "").strip()
            group = str(cfg.get("group") or "").strip()
            if method in {"t_test_ind", "anova", "mann_whitney", "anova_welch", "kruskal"} and outcome and group:
                _append(
                    hypothesis_id=f"h_protocol_{idx+1}",
                    title=f"Protocol step {step.get('id') or idx+1}: differences in {outcome} by {group}",
                    h0=f"{outcome} does not differ across {group} levels.",
                    h1=f"{outcome} differs across {group} levels.",
                    rationale="Derived from compiled protocol step.",
                    suggested_method=method,
                    variables={"outcome": outcome, "group": group, "step_id": step.get("id")},
                    priority="medium",
                )

    return {
        "schema": "clinimetria.hypothesis_discovery",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "analysis_mode": mode,
        "design_type": design_type,
        "n_rows": n_rows,
        "count": len(findings),
        "items": findings,
    }
