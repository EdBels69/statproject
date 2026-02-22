# Prompt Templates

Цель: не писать длинный промпт вручную каждый раз, а заполнять короткую JSON-спеку и рендерить готовый промпт автоматически.

## Файлы
- `ANALYSIS_PROMPT_TEMPLATE.md` — базовый шаблон.
- `covid_glycemia_spec.example.json` — пример заполненной спеки.
- `backend/scripts/render_analysis_prompt.py` — рендерер.

## Быстрый запуск
```bash
python3 backend/scripts/render_analysis_prompt.py \
  --spec docs/prompt_templates/covid_glycemia_spec.example.json \
  --template docs/prompt_templates/ANALYSIS_PROMPT_TEMPLATE.md \
  --out docs/exports/covid_prompt_rendered.md
```

## Что менять в своей спеке
- `dataset` — файл/лист.
- `research_goal` и `research_questions`.
- `outcome` — как кодировать исход.
- `exposures`, `covariates`, `comorbidities`, `treatments`.
- `models`, `sensitivity`, `plots`.
- `required_outputs` и `style_constraints`.

## Практический принцип
- Спека = "что анализируем".
- Шаблон = "как структурировать задачу".
- Рендерер = "превратить это в единый длинный промпт".

