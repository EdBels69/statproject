"""Executor dispatch registry for v2 protocol execution."""
from __future__ import annotations

import importlib
from typing import Callable, Dict, Optional, Tuple


# method_id -> (module_path, function_name)
EXECUTOR_REGISTRY: Dict[str, Tuple[str, str]] = {
    "paired_wide": ("app.stats.executors.paired_wide", "execute_paired_wide"),
    "bland_altman": ("app.stats.executors.bland_altman", "execute_bland_altman"),
    "delta_batch_analysis": ("app.stats.executors.delta_batch", "execute_delta_batch_analysis"),
    "mixed_effects": ("app.stats.executors.mixed_effects", "execute_mixed_effects"),
    "responder_analysis": ("app.stats.executors.responder_analysis", "execute_responder_analysis"),
}

# Methods handled directly by stats.engine.run_analysis
ENGINE_METHODS = {
    "t_test_ind",
    "t_test_rel",
    "mann_whitney",
    "wilcoxon",
    "chi_square",
    "fisher_exact",
    "anova",
    "anova_welch",
    "kruskal",
    "t_test_one",
    "bayes_t_test_ind",
    "bayes_t_test_rel",
    "bayes_t_test_one",
    "bayes_correlation",
    "pearson",
    "spearman",
    "kendall",
    "linear_regression",
    "logistic_regression",
    "roc_analysis",
    "shapiro_wilk",
    "dagostino_pearson",
    "anderson_darling",
    "kolmogorov_smirnov",
    "levene",
    "bartlett",
    "fligner",
}

_EXECUTOR_CACHE: Dict[str, Callable] = {}


def get_executor(method_id: str) -> Optional[Callable]:
    """Return executor callable for method_id or None if not registered."""
    if method_id in _EXECUTOR_CACHE:
        return _EXECUTOR_CACHE[method_id]

    entry = EXECUTOR_REGISTRY.get(str(method_id or ""))
    if entry is None:
        return None

    module_path, function_name = entry
    try:
        module = importlib.import_module(module_path)
        fn = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        raise ImportError(f"Cannot load executor for {method_id}: {exc}") from exc

    _EXECUTOR_CACHE[method_id] = fn
    return fn


def is_engine_method(method_id: str) -> bool:
    """Check whether method_id is expected to run via stats.engine."""
    return str(method_id or "") in ENGINE_METHODS


def is_registered(method_id: str) -> bool:
    """Check whether method_id has a dedicated executor in the registry."""
    return str(method_id or "") in EXECUTOR_REGISTRY
