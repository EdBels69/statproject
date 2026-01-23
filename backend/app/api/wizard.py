from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.datasets import DATA_DIR
from app.modules.parsers import get_dataframe
from app.stats.engine import run_batch_analysis
from app.stats.engine import run_analysis


router = APIRouter()


class WizardRecommendRequest(BaseModel):
    goal: Literal[
        "compare_groups",
        "compare_timepoints",
        "relationship",
        "survival",
        "prediction",
    ] = Field(
        ..., description="High-level research goal"
    )
    structure: Optional[Literal["independent", "paired"]] = Field(
        None, description="Group structure for compare_groups"
    )
    data_type: Optional[Literal["numeric", "categorical"]] = Field(
        None, description="Outcome data type"
    )
    groups: Optional[Literal["2", ">2"]] = Field(None, description="Group count bucket")
    normal_distribution: bool = Field(
        True, description="User assumption about normality for numeric outcomes"
    )


class WizardRecommendation(BaseModel):
    method_id: str
    name: str
    description: str
    assumptions: List[str] = Field(default_factory=list)


@router.post("/recommend", response_model=WizardRecommendation)
async def recommend(payload: WizardRecommendRequest):
    goal = payload.goal

    if goal == "compare_timepoints":
        return WizardRecommendation(
            method_id="kw_timepoints_all_numeric",
            name="Краскела–Уоллиса по каждой точке времени (все количественные)",
            description=(
                "На каждой точке времени сравнивает группы по всем числовым переменным "
                "непараметрическим тестом Краскела–Уоллиса."
            ),
            assumptions=["Независимость наблюдений внутри точки времени"],
        )

    if goal == "relationship":
        if payload.data_type == "categorical":
            return WizardRecommendation(
                method_id="chi_square",
                name="χ² (критерий хи-квадрат)",
                description="Оценивает ассоциацию между двумя категориальными переменными.",
                assumptions=["Достаточная наполняемость ячеек таблицы сопряжённости"],
            )
        return WizardRecommendation(
            method_id="pearson" if payload.normal_distribution else "spearman",
            name="Корреляция Пирсона" if payload.normal_distribution else "Корреляция Спирмена",
            description=(
                "Оценивает силу связи между двумя числовыми переменными. "
                "Пирсон — для линейной связи и нормальности; Спирмен — более устойчивый ранговый вариант."
            ),
            assumptions=(
                ["Линейность", "Отсутствие сильных выбросов", "Нормальность"]
                if payload.normal_distribution
                else ["Монотонность", "Устойчивость к выбросам"]
            ),
        )

    if goal == "survival":
        return WizardRecommendation(
            method_id="survival_km",
            name="Каплан–Майер (выживаемость)",
            description="Оценивает время до события с учётом цензурирования.",
            assumptions=["Корректно закодированное событие (1/0)", "Независимое цензурирование"],
        )

    if goal == "prediction":
        if payload.data_type == "categorical":
            return WizardRecommendation(
                method_id="logistic_regression",
                name="Логистическая регрессия",
                description="Многофакторная модель для прогнозирования бинарного исхода.",
                assumptions=["Корректная кодировка исхода", "Отсутствие сильной мультиколлинеарности"],
            )
        return WizardRecommendation(
            method_id="linear_regression",
            name="Линейная регрессия",
            description="Многофакторная модель для прогнозирования числового исхода.",
            assumptions=["Линейность", "Гомоскедастичность", "Независимость ошибок"],
        )

    if goal != "compare_groups":
        return WizardRecommendation(
            method_id="consult_statistician",
            name="Нужна уточняющая постановка",
            description="Не удалось автоматически подобрать метод под выбранную цель.",
            assumptions=[],
        )

    if payload.data_type == "categorical":
        return WizardRecommendation(
            method_id="chi_square",
            name="χ² (критерий хи-квадрат)",
            description="Сравнение распределений категориального исхода между группами.",
            assumptions=["Достаточная наполняемость ячеек", "Независимость наблюдений"],
        )

    if payload.groups == "2":
        if payload.structure == "paired":
            if payload.normal_distribution:
                return WizardRecommendation(
                    method_id="t_test_rel",
                    name="Парный t‑тест",
                    description="Сравнение двух связанных измерений (до/после) для числового исхода.",
                    assumptions=["Нормальность разностей"],
                )
            return WizardRecommendation(
                method_id="wilcoxon",
                name="Уилкоксон (парный)",
                description="Непараметрическое сравнение двух связанных измерений.",
                assumptions=["Симметрия распределения разностей (желательно)", "Парные наблюдения"],
            )

        if payload.normal_distribution:
            return WizardRecommendation(
                method_id="t_test_ind",
                name="t‑тест для независимых выборок",
                description="Сравнение средних двух независимых групп для числового исхода.",
                assumptions=["Нормальность", "Однородность дисперсий (для классического t‑теста)"],
            )
        return WizardRecommendation(
            method_id="mann_whitney",
            name="Манна–Уитни",
            description="Непараметрическое сравнение двух независимых групп.",
            assumptions=["Независимость наблюдений"],
        )

    if payload.structure == "paired":
        if payload.normal_distribution:
            return WizardRecommendation(
                method_id="rm_anova",
                name="RM ANOVA (повторные измерения)",
                description="Сравнение более двух связанных измерений для числового исхода.",
                assumptions=["Нормальность", "Сферичность (возможна коррекция)"],
            )
        return WizardRecommendation(
            method_id="friedman",
            name="Фридман (повторные измерения)",
            description="Непараметрическое сравнение более двух связанных измерений.",
            assumptions=["Парные/повторные наблюдения"],
        )

    if payload.normal_distribution:
        return WizardRecommendation(
            method_id="anova",
            name="ANOVA (однофакторная)",
            description="Сравнение средних более чем двух независимых групп.",
            assumptions=["Нормальность", "Однородность дисперсий"],
        )
    return WizardRecommendation(
        method_id="kruskal",
        name="Краскел–Уоллис",
        description="Непараметрическое сравнение более чем двух независимых групп.",
        assumptions=["Независимость наблюдений"],
    )


class WizardApplyRequest(BaseModel):
    dataset_id: str
    recommendation: Dict[str, Any]
    variables: Dict[str, Any]
    test_config: Optional[Dict[str, Any]] = None
    alpha: float = 0.05


@router.post("/apply", response_model=Dict[str, Any])
async def apply(payload: WizardApplyRequest):
    method_id = str(payload.recommendation.get("method_id") or "").strip()
    if not method_id:
        raise HTTPException(status_code=400, detail="recommendation.method_id is required")

    target = str(payload.variables.get("target") or "").strip()
    group = str(payload.variables.get("group") or "").strip() or None

    test_config = payload.test_config if isinstance(payload.test_config, dict) else {}
    multiplicity_correction = str(
        test_config.get("multiplicity_correction")
        or payload.variables.get("multiplicity_correction")
        or "fdr_bh"
    ).strip().lower()
    post_hoc = str(test_config.get("post_hoc") or payload.variables.get("post_hoc") or "none").strip().lower()
    post_hoc_correction = str(
        test_config.get("post_hoc_correction")
        or payload.variables.get("post_hoc_correction")
        or "none"
    ).strip().lower()
    alternative = str(test_config.get("alternative") or payload.variables.get("alternative") or "").strip().lower() or None
    auto_fallback = test_config.get("auto_fallback", payload.variables.get("auto_fallback", None))

    try:
        df = get_dataframe(payload.dataset_id, DATA_DIR)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось загрузить датасет: {str(e)}")

    timepoint_filter_col = str(payload.variables.get("timepoint") or "").strip()
    timepoint_filter_val = payload.variables.get("timepoint_value", None)
    if timepoint_filter_col and timepoint_filter_val is not None:
        if timepoint_filter_col not in df.columns:
            raise HTTPException(status_code=400, detail="variables.timepoint column not found")
        val_str = str(timepoint_filter_val)
        df = df[df[timepoint_filter_col].astype(str) == val_str]

    try:
        if method_id in {"rm_anova", "friedman"}:
            raw_outcome_cols = payload.variables.get("outcome_cols")
            if isinstance(raw_outcome_cols, list):
                outcome_cols = [str(c).strip() for c in raw_outcome_cols if str(c).strip()]
            elif isinstance(raw_outcome_cols, str):
                outcome_cols = [c.strip() for c in raw_outcome_cols.split(",") if c.strip()]
            else:
                outcome_cols = []

            subject_col = str(payload.variables.get("subject_col") or "").strip() or None
            group_col = str(payload.variables.get("group_col") or group or "").strip() or None

            min_points = 2 if method_id == "rm_anova" else 3
            if not outcome_cols or len(outcome_cols) < min_points:
                raise HTTPException(status_code=400, detail=f"variables.outcome_cols requires at least {min_points} columns")
            missing_cols = [c for c in outcome_cols if c not in df.columns]
            if missing_cols:
                raise HTTPException(status_code=400, detail=f"Outcome columns not found: {', '.join(missing_cols[:10])}")

            if method_id == "rm_anova":
                if not subject_col:
                    raise HTTPException(status_code=400, detail="variables.subject_col is required for rm_anova")
                if subject_col not in df.columns:
                    raise HTTPException(status_code=400, detail="variables.subject_col column not found")

            if group_col and group_col not in df.columns:
                raise HTTPException(status_code=400, detail="variables.group_col column not found")

            kwargs: Dict[str, Any] = {"outcome_cols": outcome_cols}
            if subject_col:
                kwargs["subject_col"] = subject_col
            if group_col:
                kwargs["group_col"] = group_col

            out = run_analysis(df, method_id, target or "", group or "", alpha=payload.alpha, **kwargs)
            return {"results": out}

        if method_id == "kw_timepoints_all_numeric":
            timepoint = str(payload.variables.get("timepoint") or "").strip()
            if not timepoint:
                raise HTTPException(status_code=400, detail="variables.timepoint is required")
            if not group:
                raise HTTPException(status_code=400, detail="variables.group is required")
            if timepoint not in df.columns:
                raise HTTPException(status_code=400, detail="variables.timepoint column not found")
            if group not in df.columns:
                raise HTTPException(status_code=400, detail="variables.group column not found")

            numeric_targets: List[str] = []
            for col in df.columns:
                if col in {timepoint, group}:
                    continue
                if col is None:
                    continue
                if hasattr(df[col], "dtype") and pd.api.types.is_numeric_dtype(df[col]):
                    numeric_targets.append(str(col))
            numeric_targets = sorted(list(dict.fromkeys(numeric_targets)))
            if not numeric_targets:
                raise HTTPException(
                    status_code=400,
                    detail="Не найдено числовых колонок для сравнения (кроме timepoint/group)",
                )

            slices: Dict[str, Any] = {}
            for s in sorted(df[timepoint].dropna().unique()):
                sub_df = df[df[timepoint] == s]
                items = run_batch_analysis(
                    sub_df,
                    numeric_targets,
                    group_col=group,
                    method_id="kruskal",
                    alpha=payload.alpha,
                    auto_fallback=False,
                    multiplicity_correction=multiplicity_correction,
                    post_hoc=post_hoc,
                    post_hoc_correction=post_hoc_correction,
                )
                slices[str(s)] = {
                    "type": "batch_analysis",
                    "method_id": "kruskal",
                    "group": group,
                    "items": items,
                    "multiplicity_correction": multiplicity_correction,
                    "post_hoc": post_hoc,
                    "post_hoc_correction": post_hoc_correction,
                }

            return {
                "results": {
                    "type": "timepoint_batch_analysis",
                    "method_id": "kruskal",
                    "group": group,
                    "split_by": timepoint,
                    "targets": numeric_targets,
                    "slices": slices,
                    "multiplicity_correction": multiplicity_correction,
                    "post_hoc": post_hoc,
                    "post_hoc_correction": post_hoc_correction,
                }
            }

        all_numeric = bool(payload.variables.get("all_numeric"))
        if all_numeric:
            if not group:
                raise HTTPException(status_code=400, detail="variables.group is required")
            if group not in df.columns:
                raise HTTPException(status_code=400, detail="variables.group column not found")

            exclude_cols = {group}
            timepoint = str(payload.variables.get("timepoint") or "").strip()
            if timepoint:
                exclude_cols.add(timepoint)
            event = str(payload.variables.get("event") or "").strip()
            if event:
                exclude_cols.add(event)

            numeric_targets: List[str] = []
            for col in df.columns:
                if col in exclude_cols:
                    continue
                if hasattr(df[col], "dtype") and pd.api.types.is_numeric_dtype(df[col]):
                    numeric_targets.append(str(col))
            numeric_targets = sorted(list(dict.fromkeys(numeric_targets)))
            if not numeric_targets:
                raise HTTPException(
                    status_code=400,
                    detail="Не найдено числовых колонок для сравнения (кроме исключённых)",
                )

            items = run_batch_analysis(
                df,
                numeric_targets,
                group_col=group,
                method_id=method_id,
                alpha=payload.alpha,
                auto_fallback=(bool(auto_fallback) if auto_fallback is not None else False),
                multiplicity_correction=multiplicity_correction,
                post_hoc=post_hoc,
                post_hoc_correction=post_hoc_correction,
                **({"alternative": alternative} if alternative else {}),
            )
            return {
                "results": {
                    "type": "batch_analysis",
                    "method_id": method_id,
                    "group": group,
                    "items": items,
                    "multiplicity_correction": multiplicity_correction,
                    "post_hoc": post_hoc,
                    "post_hoc_correction": post_hoc_correction,
                }
            }

        paired_method_ids = {"t_test_rel", "wilcoxon", "rm_anova", "friedman"}
        is_paired = method_id in paired_method_ids

        if not target:
            raise HTTPException(status_code=400, detail="variables.target is required")

        if method_id in {"pearson", "spearman"}:
            if not group:
                raise HTTPException(status_code=400, detail="variables.group is required for correlation")
            out = run_analysis(df, method_id, target, group, alpha=payload.alpha)
            return {"results": out}

        if method_id == "chi_square":
            if not group:
                raise HTTPException(status_code=400, detail="variables.group is required for chi-square")
            out = run_analysis(df, method_id, target, group, alpha=payload.alpha)
            return {"results": out}

        if method_id == "survival_km":
            event = str(payload.variables.get("event") or "").strip()
            if not event:
                raise HTTPException(status_code=400, detail="variables.event is required for survival")
            kwargs: Dict[str, Any] = {}
            if group:
                kwargs["group_col"] = group
            out = run_analysis(df, method_id, target, event, alpha=payload.alpha, **kwargs)
            return {"results": out}

        if method_id in {"linear_regression", "logistic_regression"}:
            raw_predictors = payload.variables.get("predictors")
            predictors: List[str] = []
            if isinstance(raw_predictors, str):
                predictors = [p.strip() for p in raw_predictors.split(",") if p.strip()]
            elif isinstance(raw_predictors, list):
                predictors = [str(p).strip() for p in raw_predictors if str(p).strip()]
            if not predictors:
                raise HTTPException(status_code=400, detail="variables.predictors is required for regression")
            out = run_analysis(
                df,
                method_id,
                target,
                group or "",
                alpha=payload.alpha,
                predictors=predictors,
            )
            return {"results": out}

        if not group:
            raise HTTPException(status_code=400, detail="variables.group is required")

        analysis_kwargs: Dict[str, Any] = {
            "post_hoc": post_hoc,
            "post_hoc_correction": post_hoc_correction,
        }
        if alternative:
            analysis_kwargs["alternative"] = alternative
        if auto_fallback is not None:
            analysis_kwargs["auto_fallback"] = bool(auto_fallback)

        out = run_analysis(
            df,
            method_id,
            target,
            group,
            is_paired=is_paired,
            alpha=payload.alpha,
            **analysis_kwargs,
        )
        return {"results": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")
