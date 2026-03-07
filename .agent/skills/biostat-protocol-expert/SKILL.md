---
name: Biostat Protocol Expert
description: Максимально экспертная биостатистика + инженерная отладка LLM. Invoke when нужен протокол анализа, дизайн исследования или стабильный JSON для /api/v2/ai/analyze-design.
---

# Biostat Protocol Expert

## Когда использовать

Используй этот навык, когда пользователь хочет:

- Сформировать дизайн исследования (RCT/наблюдательное/кросс‑секционное/продольное)
- Подобрать корректную статистическую обработку и политику множественных сравнений
- Получить исполнимый протокол для системы (список шагов method/config)
- Дебажить LLM‑промпты так, чтобы выход всегда был валидным JSON и без “галлюцинаций” колонок

## Вход (минимум)

1) Цель/гипотезы (текст)
2) Описание данных:
- что является группами (treatment/arm)
- есть ли повторные измерения (visits/time)
- что является субъектом (subject_id)
- какие исходы первичные/вторичные
3) Ограничения:
- alpha
- предпочтения (двусторонний/односторонний тест)
- политика post-hoc и коррекции

Если есть только датасет без объяснений — сначала запросить “подтверждение критических полей” (group/time/subject/primary endpoints).

## Выход

### A) Draft (план + вопросы)

- 2–4 кандидата дизайна
- список вопросов на подтверждение
- черновой `proposed_protocol[]`

### B) Final (после подтверждения)

- финальный `protocol[]` (method/config)
- `globals` (alternative, post_hoc, post_hoc_correction)
- краткие `notes` с рисками/ограничениями

## Канон протокола для Clinimetria (v2)

Каждый шаг:

```json
{
  "id": "step_1",
  "name": "…",
  "method": "descriptive_compare | auto | t_test_ind | t_test_welch | mann_whitney | t_test_rel | wilcoxon | anova | anova_welch | kruskal | chi_square | pearson | spearman | linear_regression | logistic_regression | mixed_effects | clustered_correlation | responders | anova_twoway | rm_anova | friedman",
  "config": {}
}
```

Критично:
- Никаких выдуманных колонок
- `mixed_effects` требует: outcome, time, group, subject
- `responders` требует: outcome_columns[], time_labels[], group, subject, threshold, direction

## Решающее дерево (биостатистика)

1) Тип исхода:
- continuous → t-test/ANOVA или непараметрика
- binary → chi-square / logistic
- ordinal → часто Mann–Whitney/Kruskal

2) Число групп:
- 2 группы → t_test_ind/t_test_welch или mann_whitney
- 3+ групп → anova/anova_welch или kruskal (+ post-hoc)

3) Повторные измерения:
- есть subject_id + визиты → mixed_effects или rm_anova/friedman (если простая структура)

4) Множественные сравнения:
- много исходов → FDR (BH/BKY)
- post-hoc по группам → Tukey (ANOVA) / Dunn (Kruskal)

5) Отчётность:
- всегда N по группам/визитам, effect size и CI, допущения и предупреждения

## Инженерная отладка LLM (стабильный JSON)

Если модель возвращает невалидный JSON или “галлюцинирует” колонки:

1) Ужесточить контракт вывода: “Return ONLY JSON. No markdown. No commentary.”
2) Добавить явный whitelist методов и обязательные поля для config
3) Передавать в prompt компактные метаданные (не таблицу значений)
4) Добавить самопроверку в prompt: модель обязана валидировать, что каждая колонка существует в dataset_meta.columns
5) Делать двухфазный выход: Draft (questions) → Confirm → Final

## Пример (Draft)

```json
{
  "status": "draft",
  "protocol_name": "RCT: 4 arms × visits",
  "design_candidates": [
    {
      "id": "A",
      "title": "4 группы × визиты + post-hoc + mixed effects",
      "why": ["Повторные измерения", "4 группы лечения"],
      "risks": ["Много исходов → нужен FDR", "Пропуски по визитам"],
      "requires_confirmation": ["group_column", "subject_id", "visits", "primary_endpoints", "multiplicity"]
    }
  ],
  "questions": [
    {"id": "group_column", "type": "select", "label": "Колонка группировки", "options": ["GROUP"], "default": "GROUP"}
  ],
  "proposed_protocol": [
    {"id": "t1", "name": "Описательная статистика", "method": "descriptive_compare", "config": {"target": "…", "group": "GROUP"}}
  ]
}
```

## Пример (Final)

```json
{
  "status": "completed",
  "protocol_name": "…",
  "globals": {"alternative": "two-sided", "post_hoc": "dunn", "post_hoc_correction": "bh"},
  "protocol": [
    {"id": "step_1", "name": "…", "method": "mixed_effects", "config": {"outcome": "…", "time": "…", "group": "…", "subject": "…"}}
  ],
  "notes": ["…"]
}
```

