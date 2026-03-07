# 🎯 CODEX_PLAN.md — Декомпозиция v2.py (DeepAnalyze-style)

> **Правила работы:**
>
> 1. **Одна задача за раз.** Не трогай файлы, к которым задача не относится.
> 2. **Перед каждым изменением** — `cd backend && python3 -m pytest tests/ -x -q`. Если красные → не начинай, доложи.
> 3. **После каждого изменения** — `cd backend && python3 -m pytest tests/ -x -q`. Все зелёные или откати.
> 4. **НЕ удаляй из v2.py пока не убедишься** что re-export из v2.py работает. Другие модули ИМПОРТИРУЮТ из v2.py.
> 5. **НЕ трогай** `frontend/`, `ROADMAP.md`, файлы в `workspace/`.
> 6. **Backward compatibility через re-export:** после извлечения функций в новый файл, оставь в v2.py строку `from app.api.<new_module> import <func>` чтобы внешний код продолжал работать.

---

## Контекст

`backend/app/api/v2.py` — **6217 строк, 92 функции, 8 Pydantic классов, 10 роутов, 28 elif dispatch, 52 imports.**

Цель: декомпозировать на 5 модулей по паттерну DeepAnalyze:

```
backend/app/api/
├── v2.py                → тонкая обёртка (re-exports для backward compat)
├── schemas.py           [NEW] ← Pydantic models
├── helpers.py           [NEW] ← Pure-function helpers (normalize, clamp, etc.)
├── builders.py          [NEW] ← Plan/report/cleaning builders  
├── executor_dispatch.py [NEW] ← Registry-based dispatch (вместо 28 elif)
└── routes.py            [NEW] ← Thin async route handlers
```

---

## ЗАДАНИЕ 1: Извлечение Pydantic schemas → `schemas.py`

**Цель:** Вынести 8 Pydantic моделей в отдельный файл.

**Файлы:**

- `backend/app/api/schemas.py` [NEW]
- `backend/app/api/v2.py` — удалить классы, добавить re-export

### Шаги

1. Создай `backend/app/api/schemas.py`:

```python
"""Pydantic models for V2 API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MixedEffectsRequest(BaseModel):
    dataset_id: str
    time_column: str
    value_column: str
    group_column: str
    subject_column: str
    alpha: float = 0.05
    covariates: Optional[List[str]] = None


class ClusteredCorrelationRequest(BaseModel):
    dataset_id: str
    columns: List[str]
    method: str = "pearson"
    alpha: float = 0.05
    linkage: str = "ward"
    max_columns: int = 30


class ProtocolV2Request(BaseModel):
    dataset_id: str
    protocol: List[Dict[str, Any]]
    alpha: float = 0.05
    globals: Optional[Dict[str, Any]] = None


class AnalysisTemplateListResponse(BaseModel):
    templates: List[Dict[str, Any]]
    total: int
    analysis_modes: List[str]


class AnalysisTemplateDesignRequest(BaseModel):
    dataset_id: str
    template_id: Optional[str] = None
    goal: Optional[str] = None
    analysis_mode: Optional[str] = None
    language: str = "ru"


class AnalysisPlanRequest(BaseModel):
    dataset_id: str
    design: Dict[str, Any]
    language: str = "ru"


class AnalysisBriefRequest(BaseModel):
    dataset_id: str
    goal: Optional[str] = None
    language: str = "ru"


class ExecuteProtocolRequest(BaseModel):
    dataset_id: str
    run_id: Optional[str] = None
    protocol: Optional[List[Dict[str, Any]]] = None
    protocol_name: Optional[str] = None
    alpha: float = 0.05
    globals: Optional[Dict[str, Any]] = None
    format: str = "json"
    include_report: bool = True
    language: str = "ru"
```

1. Найди **все** Pydantic классы в `v2.py` (строки около 2482-2539 и 3648):

```
class MixedEffectsRequest(BaseModel):       → строка ~2482
class ClusteredCorrelationRequest(BaseModel): → строка ~2493
class ProtocolV2Request(BaseModel):          → строка ~2504
class AnalysisTemplateListResponse(BaseModel): → строка ~2511
class AnalysisTemplateDesignRequest(BaseModel): → строка ~2525
class AnalysisPlanRequest(BaseModel):        → строка ~2532
class AnalysisBriefRequest(BaseModel):       → строка ~2539
class ExecuteProtocolRequest(BaseModel):     → строка ~3648
```

**Важно:** Перед удалением классов из v2.py, изучи каждый класс — некоторые могут иметь дополнительные поля или `Field(...)` описания. Скопируй точные определения из v2.py в schemas.py, НЕ используй мою упрощённую версию выше как единственный источник.

1. **Удали** определения классов из `v2.py`. Вместо них добавь один import в начало v2.py:

```python
from app.api.schemas import (
    MixedEffectsRequest,
    ClusteredCorrelationRequest,
    ProtocolV2Request,
    AnalysisTemplateListResponse,
    AnalysisTemplateDesignRequest,
    AnalysisPlanRequest,
    AnalysisBriefRequest,
    ExecuteProtocolRequest,
)
```

Этот re-export гарантирует, что любой код `from app.api.v2 import MixedEffectsRequest` продолжит работать.

### Верификация

```bash
cd backend && python3 -c "from app.api.schemas import ExecuteProtocolRequest; print('OK')"
cd backend && python3 -c "from app.api.v2 import ExecuteProtocolRequest; print('Re-export OK')"
cd backend && python3 -m pytest tests/ -x -q
```

---

## ЗАДАНИЕ 2: Извлечение helpers → `helpers.py`

**Цель:** Pure helper functions (без side-effects, без imports из app.*).

**Файлы:**

- `backend/app/api/helpers.py` [NEW]
- `backend/app/api/v2.py` — удалить функции, добавить re-export

### Какие функции извлечь

Из v2.py (строки 89-800), извлечь следующие **чистые** функции:

```python
# helpers.py — чистые хелперы без зависимостей от app.*

_ensure_method(payload, method_id)                    # строка ~89
_maybe_add_conclusion(payload, variables)             # строка ~98
_canonical_method_id(raw_method)                      # строка ~110
_normalize_plan_step(item, idx)                       # строка ~150
_to_int_or_none(value)                                # строка ~176
_to_float_or_none(value)                              # строка ~185
_runtime_elapsed_ms(start_perf, end_perf)             # строка ~197
_runtime_percentile_ms(values, quantile)              # строка ~206
_normalize_role_models_payload(raw)                    # строка ~216
_benchmark_clamp01(value, fallback)                   # строка ~231
_normalize_benchmark_analysis_mode(value)             # строка ~241
_normalize_benchmark_validation_profile(value, ...)   # строка ~250
_score_benchmark_latency(elapsed_ms)                  # строка ~319
_score_benchmark_token_efficiency(token_total)        # строка ~326
_score_benchmark_step_coverage(step_count, expected)  # строка ~333
_score_benchmark_retry_efficiency(attempt_count)      # строка ~342
_llm_benchmark_auto_score(row)                        # строка ~349
_normalize_llm_benchmark_payload(raw)                 # строка ~398
_normalize_correction(value)                          # строка ~750
_as_bool(value, default)                              # строка ~775
_normalize_bootstrap_samples(value, default)          # строка ~790
_method_supports_bootstrap(raw_method)                # строка ~794
_method_supports_multiplicity(raw_method)             # строка ~799
_finite_float(value)                                  # строка ~1044
_as_str_list(value)                                   # строка ~2186
_normalize_analysis_mode(value)                       # строка ~2062
_normalize_validation_profile(value, ...)             # строка ~2073
_merge_plan_section(default_section, incoming)        # строка ~2468
```

### Шаги

1. Создай `backend/app/api/helpers.py` — скопируй точные определения из v2.py.

2. В начало `helpers.py` добавь нужные imports (только стандартные: `typing`, `numpy`, `hashlib`).

3. Проверь каждую функцию на зависимости от `app.*`:
   - Если зависит от `app.*` — **НЕ извлекай**, оставь в v2.py.
   - Если зависит только от стандартных библиотек или numpy — извлекай.

4. В v2.py добавь re-export:

```python
from app.api.helpers import (
    _ensure_method,
    _maybe_add_conclusion,
    _canonical_method_id,
    # ...все остальные
)
```

1. **Удали** оригинальные определения из v2.py.

### Верификация

```bash
cd backend && python3 -c "from app.api.helpers import _canonical_method_id; print(_canonical_method_id('Mann-Whitney U'))"
cd backend && python3 -m pytest tests/ -x -q
```

**❌ НЕ ДЕЛАЙ:**

- Не переименовывай функции
- Не меняй сигнатуры
- Не извлекай функции, которые зависят от app.* модулей (их трогать в Задании 4)

---

## ЗАДАНИЕ 3: Извлечение builders → `builders.py`

**Цель:** Функции, которые строят план, отчёт, cleaning — без роутов.

**Файлы:**

- `backend/app/api/builders.py` [NEW]
- `backend/app/api/v2.py` — удалить, re-export

### Какие функции извлечь

```python
# builders.py — constructors that build plans, reports, traces

_resolve_llm_benchmark_score_profile(row)             # строка ~261
_resolve_multiplicity_policy(...)                     # строка ~804
_attach_multiplicity_policy_to_plan_globals(...)      # строка ~883
_resolve_bootstrap_policy(...)                        # строка ~905
_attach_bootstrap_policy_to_plan_globals(...)         # строка ~977
_analysis_runtime_kwargs(config)                      # строка ~1001
_build_batch_multiplicity_trace(...)                  # строка ~1054
_bootstrap_metric_preview(name, value, ...)           # строка ~1119
_build_bootstrap_trace_document(...)                  # строка ~1162
_count_adjusted_p_values(items)                       # строка ~1245
_build_multiplicity_trace_document(...)               # строка ~1260
_iter_result_payload_entries(results)                 # строка ~1424
_extract_step_p_value(payload)                        # строка ~1428
_repair_run_payload_multiplicity(...)                 # строка ~1432
_repair_run_payload_p_bounds(...)                     # строка ~1445
_attempt_verifier_reflection_repair(...)              # строка ~1456
_sha256_hex(content)                                  # строка ~1471
_build_environment_snapshot()                         # строка ~1475
_reproduce_script_template()                          # строка ~1513
_build_fallback_report_html(...)                      # строка ~1555
_create_run_reproducibility_artifacts(...)            # строка ~1568
_collect_dataset_columns(dataset_meta)                # строка ~1887
_filter_protocol_steps(protocol, dataset_meta)        # строка ~1901
_resolve_runtime_validation_policy(globals_in, ...)   # строка ~2086
_attach_validation_policy_to_plan_globals(...)        # строка ~2156
_infer_protocol_column_sets(protocol)                 # строка ~2196
_build_cleaning_plan(...)                             # строка ~2236
_build_cohort_plan(...)                               # строка ~2356
_build_report_spec(...)                               # строка ~2416
_safe_build_hypothesis_discovery(...)                 # строка ~630
_load_model_router_benchmark_capture_last(...)        # строка ~2554
```

### Шаги

1. Создай `backend/app/api/builders.py`.

2. Скопируй все перечисленные функции из v2.py.

3. В начало `builders.py` добавь необходимые imports. Эти функции ЗАВИСЯТ от `app.*`:
   - `from app.utils import convert_numpy_to_native`
   - `from app.stats.engine import ...` (если нужно)
   - `from app.modules.protocol_rules import ...` (если нужно)
   - Изучи import'ы конкретных функций перед переносом.

4. В v2.py добавь re-export и удали определения.

### Верификация

```bash
cd backend && python3 -c "from app.api.builders import _build_environment_snapshot; print(type(_build_environment_snapshot()))"
cd backend && python3 -m pytest tests/ -x -q
```

---

## ЗАДАНИЕ 4: Executor Registry → `executor_dispatch.py`

**Цель:** Заменить 28 `elif method_id == ...` на registry dict + dispatch function.

**Файлы:**

- `backend/app/api/executor_dispatch.py` [NEW]
- `backend/app/api/v2.py` — заменить dispatch chain

### Шаги

1. Создай `backend/app/api/executor_dispatch.py`:

```python
"""
Executor dispatch registry.
Maps method_id → executor function.
Replaces 28 elif method_id == ... chain in v2.py.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional

import pandas as pd


# Registry: method_id → (module_path, function_name)
# Each function must accept (df, config, alpha, **kwargs) and return Dict.
EXECUTOR_REGISTRY: Dict[str, tuple[str, str]] = {
    # --- Extracted executors ---
    "paired_wide": ("app.stats.executors.paired_wide", "execute_paired_wide"),
    "bland_altman": ("app.stats.executors.bland_altman", "execute_bland_altman"),
    "delta_batch_analysis": ("app.stats.executors.delta_batch", "execute_delta_batch"),
    "mixed_effects": ("app.stats.executors.mixed_effects", "execute_mixed_effects"),
    "responder_analysis": ("app.stats.executors.responder_analysis", "execute_responder_analysis"),
}

# Methods handled by engine.run_analysis (generic dispatcher in stats engine)
ENGINE_METHODS = {
    "t_test_ind", "t_test_rel", "mann_whitney", "wilcoxon",
    "chi_square", "fisher_exact", "anova", "kruskal_wallis",
    "welch_anova", "t_test_one", "bayes_t_test_ind", "bayes_t_test_rel",
    "bayes_t_test_one", "bayes_correlation", "correlation",
    "linear_regression", "logistic_regression", "roc_analysis",
    "shapiro_wilk", "dagostino_pearson", "anderson_darling",
    "kolmogorov_smirnov", "levene", "bartlett", "fligner",
}

# Lazy-loaded callable cache
_EXECUTOR_CACHE: Dict[str, Callable] = {}


def get_executor(method_id: str) -> Optional[Callable]:
    """
    Get executor function for a method_id.
    Returns None for methods handled by engine or custom inline logic.
    """
    if method_id in _EXECUTOR_CACHE:
        return _EXECUTOR_CACHE[method_id]

    entry = EXECUTOR_REGISTRY.get(method_id)
    if entry is None:
        return None

    module_path, func_name = entry
    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        _EXECUTOR_CACHE[method_id] = func
        return func
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Cannot load executor for {method_id}: {e}") from e


def is_engine_method(method_id: str) -> bool:
    """Check if method_id is handled by stats.engine.run_analysis."""
    return method_id in ENGINE_METHODS


def is_registered(method_id: str) -> bool:
    """Check if method_id has a registered executor."""
    return method_id in EXECUTOR_REGISTRY
```

1. В v2.py, найди dispatch chain (строки ~4250-4987). Этот блок выглядит так:

```python
                if method_id == "mixed_effects":
                    ...
                elif method_id == "clustered_correlation":
                    ...
                elif method_id == "paired_wide":
                    ...
```

1. **Перед** этим блоком добавь:

```python
from app.api.executor_dispatch import get_executor, is_engine_method

# Try registry-based dispatch first
executor_fn = get_executor(method_id)
if executor_fn is not None:
    runtime_kwargs = _analysis_runtime_kwargs(config)
    payload = executor_fn(df_step, config, request.alpha, runtime_kwargs=runtime_kwargs)
    payload = convert_numpy_to_native(payload)
    results.append({"step_id": step_id, "method": method_id, "status": "completed", "results": payload})
    results_map[step_id] = payload
    continue  # Skip the elif chain below
```

1. **НЕ УДАЛЯЙ** elif chain — пусть работает как fallback. Registry обрабатывает 5 executor'ов, остальные 23 elif остаются. Потом, по мере извлечения executor'ов из engine.py, будем добавлять их в registry.

### Верификация

```bash
cd backend && python3 -c "
from app.api.executor_dispatch import get_executor, is_engine_method, is_registered
print('paired_wide registered:', is_registered('paired_wide'))
print('mann_whitney is engine:', is_engine_method('mann_whitney'))
print('unknown:', is_registered('nonexistent'))
fn = get_executor('paired_wide')
print('executor loaded:', fn is not None)
"
cd backend && python3 -m pytest tests/ -x -q
```

**❌ НЕ ДЕЛАЙ:**

- Не удаляй elif chain — это fallback
- Не добавляй в registry методы, у которых нет отдельного executor файла
- Не меняй сигнатуры executor'ов

---

## ЗАДАНИЕ 5: Тесты на декомпозицию

**Файл:** `backend/tests/test_v2_decomposition.py` [NEW]

```python
"""Tests for v2.py decomposition — verify re-exports and registry work."""
import pytest


class TestSchemas:
    """Verify schemas are importable from both locations."""

    def test_import_from_schemas(self):
        from app.api.schemas import (
            ExecuteProtocolRequest,
            MixedEffectsRequest,
            AnalysisPlanRequest,
        )
        req = ExecuteProtocolRequest(dataset_id="test")
        assert req.dataset_id == "test"
        assert req.alpha == 0.05

    def test_reexport_from_v2(self):
        from app.api.v2 import ExecuteProtocolRequest
        req = ExecuteProtocolRequest(dataset_id="test")
        assert req.dataset_id == "test"


class TestHelpers:
    """Verify helper functions work from new location."""

    def test_canonical_method_id(self):
        from app.api.helpers import _canonical_method_id
        assert _canonical_method_id("Mann-Whitney U") == "mann_whitney"
        assert _canonical_method_id("t_test_ind") == "t_test_ind"

    def test_to_int_or_none(self):
        from app.api.helpers import _to_int_or_none
        assert _to_int_or_none(42) == 42
        assert _to_int_or_none("10") == 10
        assert _to_int_or_none(None) is None
        assert _to_int_or_none("abc") is None

    def test_finite_float(self):
        from app.api.helpers import _finite_float
        assert _finite_float(3.14) == pytest.approx(3.14)
        assert _finite_float(float("nan")) is None
        assert _finite_float(None) is None

    def test_as_bool(self):
        from app.api.helpers import _as_bool
        assert _as_bool(True) is True
        assert _as_bool("yes") is True
        assert _as_bool(0) is False

    def test_reexport_from_v2(self):
        from app.api.v2 import _canonical_method_id
        assert _canonical_method_id("t-test") == "t_test"


class TestBuilders:
    """Verify builder functions importable."""

    def test_build_environment_snapshot(self):
        from app.api.builders import _build_environment_snapshot
        snap = _build_environment_snapshot()
        assert isinstance(snap, dict)
        assert "python_version" in snap or "platform" in snap or len(snap) > 0

    def test_sha256_hex(self):
        from app.api.builders import _sha256_hex
        h = _sha256_hex(b"hello")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_reexport_from_v2(self):
        from app.api.v2 import _build_environment_snapshot
        snap = _build_environment_snapshot()
        assert isinstance(snap, dict)


class TestExecutorDispatch:
    """Verify executor registry."""

    def test_registry_contains_known_executors(self):
        from app.api.executor_dispatch import EXECUTOR_REGISTRY
        assert "paired_wide" in EXECUTOR_REGISTRY
        assert "bland_altman" in EXECUTOR_REGISTRY
        assert "responder_analysis" in EXECUTOR_REGISTRY

    def test_get_executor_loads(self):
        from app.api.executor_dispatch import get_executor
        fn = get_executor("paired_wide")
        assert fn is not None
        assert callable(fn)

    def test_get_executor_unknown_returns_none(self):
        from app.api.executor_dispatch import get_executor
        fn = get_executor("nonexistent_method_xyz")
        assert fn is None

    def test_is_engine_method(self):
        from app.api.executor_dispatch import is_engine_method
        assert is_engine_method("mann_whitney") is True
        assert is_engine_method("t_test_ind") is True
        assert is_engine_method("paired_wide") is False
```

### Верификация

```bash
cd backend && python3 -m pytest tests/test_v2_decomposition.py -v
cd backend && python3 -m pytest tests/ -x -q
```

---

## Порядок выполнения

```
Задание 1 (schemas.py) → тест → коммит
Задание 2 (helpers.py) → тест → коммит
Задание 3 (builders.py) → тест → коммит
Задание 4 (executor_dispatch.py) → тест → коммит
Задание 5 (тесты) → коммит
```

**Коммиты:**

```bash
git add -A && git commit -m "refactor: extract Pydantic schemas from v2.py → app/api/schemas.py"
git add -A && git commit -m "refactor: extract pure helpers from v2.py → app/api/helpers.py"
git add -A && git commit -m "refactor: extract builders from v2.py → app/api/builders.py"
git add -A && git commit -m "refactor: executor registry dispatch (app/api/executor_dispatch.py)"
git add -A && git commit -m "test: v2 decomposition tests (schemas, helpers, builders, dispatch)"
```

---

## Чего НЕ ДЕЛАТЬ

| ❌ Что | Почему плохо |
|--------|-------------|
| Удалить из v2.py без re-export | Ломает все import'ы из других модулей |
| Извлечь elif chain полностью | Нет executor'ов для 23 из 28 методов |
| Менять сигнатуры функций | Ломает все call sites |
| Переименовывать underscore prefix | Тесты и другой код могут import'ить _private |
| Трогать engine.py в этом плане | Отдельная задача, другой план |
| Менять frontend код | Он использует API endpoints, не Python imports |
| Менять tests/ (кроме добавления новых) | Существующие тесты — regression guard |

---

## Ожидаемый результат

| До | После |
|----|-------|
| v2.py: 6,217 строк | v2.py: ~3,000 строк (routes + elif fallback + re-exports) |
| Всё в одном файле | schemas.py: ~120, helpers.py: ~500, builders.py: ~1300, executor_dispatch.py: ~80 |
| 92 функции | ~40 в v2.py, ~30 в helpers, ~30 в builders |
| Невозможно тестировать helpers отдельно | Каждый модуль тестируется изолированно |
| Нет executor registry | Registry с lazy-load + fallback |

---

*Создано: 2026-03-04. Автор: Antigravity (DeepAnalyze-style decomposition).*
