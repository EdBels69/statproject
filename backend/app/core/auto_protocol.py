"""
auto_protocol.py — Генератор полного протокола анализа.

Пользователь назначает роли (target, group, covariates) →
этот модуль автоматически генерирует комплексный протокол:

1. Table 1 — описательные статистики по группам
2. Основное сравнение (target by group) — авто-выбор теста
3. Подгрупповые анализы (target by group, стратифицируя по каждой ковариате)
4. Попарные корреляции всех числовых переменных
5. Множественная регрессия (target ~ group + covariates)
6. Корреляционная матрица с кластеризацией
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


def generate_full_protocol(
    df: pd.DataFrame,
    target: str,
    group: str,
    covariates: Optional[List[str]] = None,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Главная функция: на вход — данные и роли, на выход — полный протокол.
    """
    covariates = covariates or []
    steps = []
    step_counter = 0

    def _step_id(prefix: str) -> str:
        nonlocal step_counter
        step_counter += 1
        return f"{step_counter:02d}_{prefix}"

    # ── Определяем типы переменных ────────────────────────────────────────
    target_is_numeric = pd.api.types.is_numeric_dtype(df[target]) if target in df.columns else False
    group_is_categorical = not pd.api.types.is_numeric_dtype(df[group]) if group in df.columns else True

    n_groups = df[group].nunique() if group in df.columns else 0

    numeric_cols = [c for c in [target] + covariates if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    categorical_covs = [c for c in covariates if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]
    numeric_covs = [c for c in covariates if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]

    # ═══════════════════════════════════════════════════════════════════════
    # 1. TABLE 1 — описательные статистики по группам
    # ═══════════════════════════════════════════════════════════════════════
    if target_is_numeric and group in df.columns:
        steps.append({
            "id": _step_id("table1"),
            "type": "descriptive_compare",
            "target": target,
            "group": group,
            "_label": f"Описательные статистики {target} по группам {group}",
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 2. ОСНОВНОЕ СРАВНЕНИЕ — target by group (авто-тест)
    # ═══════════════════════════════════════════════════════════════════════
    if target in df.columns and group in df.columns:
        steps.append({
            "id": _step_id("primary"),
            "type": "compare",
            "target": target,
            "group": group,
            "_label": f"Основное сравнение: {target} по {group}",
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 3. ПОДГРУППОВЫЕ АНАЛИЗЫ — target by group, стратификация по ковариатам
    # ═══════════════════════════════════════════════════════════════════════
    for cov in categorical_covs:
        if cov == group:
            continue
        cov_vals = df[cov].dropna().unique()
        if 1 < len(cov_vals) <= 10:  # только осмысленные подгруппы
            steps.append({
                "id": _step_id(f"subgroup_{cov}"),
                "type": "batch_compare_by_factor",
                "target": target,
                "group": group,
                "split_by": cov,
                "_label": f"Подгрупповой анализ: {target} по {group}, стратификация по {cov}",
            })

    # Если числовые ковариаты — разобьём на 2 группы (≤median, >median) для подгруппового анализа
    for cov in numeric_covs[:3]:  # ограничиваем 3 ковариатами
        if cov == target or cov == group:
            continue
        median_val = df[cov].median()
        # Создаём временную бинарную переменную — протокол это опишет
        steps.append({
            "id": _step_id(f"subgroup_{cov}_median"),
            "type": "batch_compare_by_factor",
            "target": target,
            "group": group,
            "split_by": cov,
            "_label": f"Подгрупповой анализ: {target} по {group}, стратификация по {cov} (медиана)",
            "_note": f"Нужно бинировать {cov} по медиане = {median_val:.2f}",
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 4. СРАВНЕНИЯ target по КАЖДОЙ категориальной ковариате отдельно
    # ═══════════════════════════════════════════════════════════════════════
    for cov in categorical_covs:
        if cov == group:
            continue
        if target_is_numeric:
            steps.append({
                "id": _step_id(f"compare_{cov}"),
                "type": "compare",
                "target": target,
                "group": cov,
                "_label": f"Сравнение: {target} по {cov}",
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 5. КОРРЕЛЯЦИИ — все числовые переменные попарно
    # ═══════════════════════════════════════════════════════════════════════
    if len(numeric_cols) >= 2:
        # Попарные корреляции target с каждой числовой ковариатой
        for cov in numeric_covs:
            if cov == target:
                continue
            steps.append({
                "id": _step_id(f"corr_{cov}"),
                "type": "correlation",
                "target": target,
                "group": cov,
                "_label": f"Корреляция: {target} vs {cov}",
            })

    # ═══════════════════════════════════════════════════════════════════════
    # 6. КЛАСТЕРНАЯ КОРРЕЛЯЦИЯ — матрица всех числовых переменных
    # ═══════════════════════════════════════════════════════════════════════
    all_numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    # Берём только те что в roles + ковариатах, или до 15 переменных
    corr_vars = list(dict.fromkeys([target] + numeric_covs + [c for c in all_numeric if c not in [target] + numeric_covs][:10]))
    corr_vars = [c for c in corr_vars if c in df.columns]

    if len(corr_vars) >= 3:
        steps.append({
            "id": _step_id("corr_matrix"),
            "type": "clustered_correlation",
            "variables": corr_vars,
            "method": "spearman",  # robustный по умолчанию
            "_label": f"Корреляционная матрица ({len(corr_vars)} переменных)",
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 7. РЕГРЕССИЯ — target ~ group + covariates
    # ═══════════════════════════════════════════════════════════════════════
    if target_is_numeric and len(numeric_covs) > 0:
        predictors = []
        if group_is_categorical and group in df.columns:
            predictors.append(group)
        predictors.extend(numeric_covs)

        if len(predictors) >= 1:
            steps.append({
                "id": _step_id("regression"),
                "type": "regression",
                "target": target,
                "predictors": predictors,
                "kind": "linear",
                "_label": f"Множественная регрессия: {target} ~ {' + '.join(predictors)}",
            })

    # Если target бинарный — логистическая регрессия
    if not target_is_numeric or (target_is_numeric and df[target].nunique() == 2):
        predictors = []
        if group in df.columns:
            predictors.append(group)
        predictors.extend(numeric_covs[:5])
        if len(predictors) >= 1:
            steps.append({
                "id": _step_id("logistic"),
                "type": "regression",
                "target": target,
                "predictors": predictors,
                "kind": "logistic",
                "_label": f"Логистическая регрессия: {target} ~ {' + '.join(predictors)}",
            })

    # ═══════════════════════════════════════════════════════════════════════
    # Формируем протокол
    # ═══════════════════════════════════════════════════════════════════════
    protocol = {
        "name": f"Полный анализ: {target} по {group}",
        "goal": "comprehensive",
        "variables": {
            "target": target,
            "group": group,
            "covariates": covariates,
        },
        "steps": steps,
        "n_steps": len(steps),
        "description": _make_description(target, group, covariates, steps),
    }

    return protocol


def _make_description(target: str, group: str, covariates: List[str], steps: List[Dict]) -> str:
    """Человекочитаемое описание протокола."""
    lines = [
        f"Комплексный анализ переменной «{target}» в зависимости от «{group}».",
    ]
    if covariates:
        lines.append(f"Ковариаты: {', '.join(covariates)}.")

    step_types = {}
    for s in steps:
        t = s.get("_label") or s.get("type")
        step_types.setdefault(s["type"], []).append(t)

    lines.append(f"Протокол включает {len(steps)} шагов:")
    type_labels = {
        "descriptive_compare": "Описательная статистика (Table 1)",
        "compare": "Сравнение групп",
        "batch_compare_by_factor": "Подгрупповые анализы",
        "correlation": "Корреляции",
        "clustered_correlation": "Корреляционная матрица",
        "regression": "Регрессионный анализ",
    }
    for t, items in step_types.items():
        label = type_labels.get(t, t)
        lines.append(f"  • {label}: {len(items)} шаг(ов)")

    return "\n".join(lines)
