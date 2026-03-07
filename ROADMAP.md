# 🗺️ ROADMAP.md — План развития Clinimetria

> **Для AI-агентов:** Используй этот документ как руководство к действию.  
> **Правило:** Можешь реализовывать задачи самостоятельно без ревью пользователя, если:
>
> 1. Задача помечена как `🟢 AUTO` (автоматическое выполнение разрешено)
> 2. Все тесты проходят после изменений
> 3. Нет breaking changes в API
> 4. **Следуешь стандартам из `SCIENTIFIC_STANDARDS.md`**

---

## 📅 ВЕРСИИ И СРОКИ

| Версия | Название | Статус | Ключевые фичи |
|--------|----------|--------|---------------|
| v0.9 | MVP | ✅ Готово | 26 методов, импутация, AI рекомендации |
| v1.0 | Scientific | ✅ Готово | Parquet, Pingouin, Effect sizes, AI-интерпретации, **Copilot Engine** |
| v1.1 | Visualization | 📋 Планируется | Publication-ready графики, Plot export |
| v1.2 | UX | 📋 Планируется | ag-grid, Variable Workspace, Templates |
| v1.3 | AI | 📋 Планируется | AI-консультант, Batch ML, Multi-dataset |
| v1.4 | Copilot Pro | 📋 Планируется | Multi-turn refinement, Protocol caching, Batch reports |

---

## 🔬 ФАЗА 0: Scientific Python Standards (ПРИОРИТЕТ)

### Статус: 🔄 В работе — ДЕЛАТЬ ПЕРВЫМ

---

#### TASK-SCI-001: Добавить Pingouin 🟢 AUTO

**Файлы:**

- `backend/requirements.txt`
- `backend/app/stats/engine.py`

**Что сделать:**

1. Добавить в requirements.txt: `pingouin>=0.5.3`
2. Заменить ручные расчёты на pingouin:

```python
import pingouin as pg

# Вместо ручного t-test
result = pg.ttest(group1, group2)  # Возвращает d, CI, power, BF10
```

**Критерии готовности:**

- [x] pingouin установлен
- [x] t-test использует pg.ttest
- [x] ANOVA использует pg.anova
- [x] Тесты проходят

---

#### TASK-SCI-002: Parquet вместо CSV 🟢 AUTO

**Файлы:**

- `backend/requirements.txt`
- `backend/app/core/pipeline.py`
- `backend/app/modules/parsers.py`

**Что сделать:**

1. Добавить: `pyarrow>=14.0.0`
2. Заменить:

```python
# Было
df.to_csv(path)
df = pd.read_csv(path)

# Стало
df.to_parquet(path, engine='pyarrow')
df = pd.read_parquet(path)
```

**Критерии готовности:**

- [x] pyarrow установлен
- [x] Processed data сохраняется в .parquet
- [x] Чтение ускорено в 5x+

---

#### TASK-SCI-003: Оптимизация типов данных 🟢 AUTO

**Файлы:**

- `backend/app/modules/smart_scanner.py`

**Что сделать:**

```python
def optimize_dtypes(df):
    for col in df.columns:
        if df[col].dtype == 'int64':
            df[col] = df[col].astype('int32')
        elif df[col].dtype == 'float64':
            df[col] = df[col].astype('float32')
        elif df[col].dtype == 'object' and df[col].nunique() < 50:
            df[col] = df[col].astype('category')
    return df
```

**Критерии готовности:**

- [x] Функция optimize_dtypes создана
- [x] Вызывается после parse_file
- [x] Экономия памяти 50%+

---

## 📊 ФАЗА 0.5: Visualization Standards

### Статус: 📋 Планируется

---

#### TASK-VIS-001: Matplotlib Publication Config 🟢 AUTO

**Файлы:**

- `backend/app/modules/plot_config.py` (новый)
- `backend/app/modules/reporting.py`

**Что сделать:**

```python
PUBLICATION_CONFIG = {
    'figure.dpi': 300,
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 1.0,
}
plt.rcParams.update(PUBLICATION_CONFIG)
sns.set_theme(style="whitegrid", palette="colorblind")
```

**Критерии готовности:**

- [x] Конфиг создан
- [x] Все графики используют 300 DPI
- [x] Colorblind-safe палитра
- [x] SVG/PDF экспорт

---

#### TASK-VIS-002: Стандартные графики для тестов 🟢 AUTO

**Файлы:**

- `backend/app/modules/plot_templates.py` (новый)

**Что сделать:**

1. `plot_group_comparison(df, x, y)` — Box + Strip
2. `plot_correlation_matrix(corr_matrix)` — Heatmap
3. `plot_distribution(data)` — Histogram + KDE
4. `plot_regression(x, y, model)` — Scatter + Line

**Критерии готовности:**

- [x] 4 шаблона созданы
- [x] Используют publication config
- [x] Тесты визуализации

---

## 🔥 ФАЗА 1: Production Ready (v1.0)

### Статус: 🔄 В работе

### Приоритет: P0 — Критические задачи

---

#### TASK-001: Исправить Effect Size интерпретацию 🟢 AUTO

**Файлы:**

- `backend/app/modules/text_generator.py`
- `backend/app/stats/engine.py`

**Что сделать:**

1. В `text_generator.py` добавить функцию `interpret_effect_size(effect_type, value)`:

```python
def interpret_effect_size(effect_type: str, value: float) -> str:
    """
    Интерпретировать размер эффекта.
    
    effect_type: 'cohens_d' | 'eta_squared' | 'r' | 'odds_ratio'
    """
    if effect_type == "cohens_d":
        if abs(value) < 0.2: return "незначительный эффект"
        if abs(value) < 0.5: return "малый эффект"
        if abs(value) < 0.8: return "средний эффект"
        return "большой эффект"
    # ... аналогично для других
```

1. В `engine.py` добавить `effect_size_interpretation` в результат каждого теста

**Критерии готовности:**

- [x] Функция `interpret_effect_size` работает для всех типов
- [x] Результат анализа содержит `effect_size_interpretation`
- [x] Тест `test_effect_size_interpretation` проходит

**Тест:**

```bash
python3 -m pytest tests/test_effect_size_verification.py -v
```

---

#### TASK-002: Добавить Eta-squared для ANOVA 🟢 AUTO

**Файлы:**

- `backend/app/stats/engine.py`

**Что сделать:**

1. В `_handle_group_comparison` для ANOVA добавить:

```python
# После расчёта F-статистики
ss_between = sum(n * (mean - grand_mean)**2 for n, mean in group_stats)
ss_total = sum((x - grand_mean)**2 for x in all_values)
eta_squared = ss_between / ss_total
```

1. Добавить в результат:

```python
"effect_size": eta_squared,
"effect_size_type": "eta_squared",
"effect_size_interpretation": interpret_effect_size("eta_squared", eta_squared)
```

**Критерии готовности:**

- [x] ANOVA возвращает `eta_squared`
- [x] Интерпретация: 0.01=малый, 0.06=средний, 0.14=большой
- [x] Тест проходит

---

#### TASK-003: JASP-style конфигуратор тестов 🟢 AUTO

**Файлы:**

- `frontend/src/app/components/TestConfigModal.jsx`

**Что сделать:**

1. Добавить вкладки: "Основные" | "Дополнительно" | "Post-hoc"
2. В "Основные":
   - Alpha level (slider 0.01 - 0.10, default 0.05)
   - Confidence interval (checkbox, default ON)
   - Descriptives (checkbox, default ON)
3. В "Дополнительно":
   - Effect size (dropdown: Cohen's d / Hedges' g / Glass's delta)
   - Missing values (dropdown: Listwise / Pairwise)
4. В "Post-hoc" (для ANOVA):
   - Tukey (default ON)
   - Bonferroni (checkbox)
   - Holm (checkbox)

**Критерии готовности:**

- [ ] Все опции отображаются
- [ ] Значения передаются в API
- [ ] Backend обрабатывает все опции

---

#### TASK-004: AI-интерпретация с шаблонами 🟢 AUTO

**Файлы:**

- `backend/app/modules/text_generator.py`

**Что сделать:**

1. Создать шаблоны для каждого типа теста:

```python
INTERPRETATION_TEMPLATES = {
    "t_test_ind": {
        "significant": "Выявлены статистически значимые различия между группами {group1} и {group2} (t({df}) = {t_value:.2f}, p {p_display}). Размер эффекта Cohen's d = {d:.2f} ({effect_interpretation}). {group_higher} показала {higher_lower} значения (M = {mean1:.2f} vs M = {mean2:.2f}).",
        "not_significant": "Статистически значимых различий между группами {group1} и {group2} не выявлено (t({df}) = {t_value:.2f}, p = {p_value:.3f})."
    },
    # ... для всех методов
}
```

1. Добавить форматирование p-value:
   - p < 0.001 → "p < 0.001"
   - p < 0.01 → "p < 0.01"
   - p < 0.05 → "p < 0.05"
   - иначе → "p = X.XXX"

**Критерии готовности:**

- [x] Шаблоны для всех 26 методов
- [x] APA-style форматирование
- [x] Тест на корректность вывода

---

### Приоритет: P1 — Важные задачи

---

#### TASK-005: Расширенные описательные статистики 🟢 AUTO

**Файлы:**

- `backend/app/stats/engine.py` (функция `compute_descriptive_compare`)

**Что добавить в вывод:**

- `se` (standard error) ✅ уже есть
- `variance` ✅ уже есть
- `mode` ✅ уже есть
- `skewness` ✅ уже есть
- `kurtosis` ✅ уже есть
- `cv` (coefficient of variation) = sd / mean * 100
- `geometric_mean` (для лог-нормальных данных)

**Критерии готовности:**

- [x] Все метрики в выводе
- [x] Округление до 3 знаков
- [x] NaN → null в JSON

---

#### TASK-006: Фронтенд — таблица результатов с effect sizes 🟢 AUTO

**Файлы:**

- `frontend/src/app/pages/Analyze.jsx` или `Profile.jsx`

**Что сделать:**

1. Добавить колонку "Effect Size" в таблицу результатов
2. Добавить колонку "Interpretation" с цветовой кодировкой:
   - Малый эффект → жёлтый
   - Средний эффект → оранжевый
   - Большой эффект → зелёный

**Критерии готовности:**

- [x] Колонки отображаются
- [x] Цветовая кодировка работает
- [x] Tooltip с объяснением

---

## 🚀 ФАЗА 2: User Experience (v1.1)

### Статус: 📋 Планируется

---

#### TASK-007: ag-grid для редактирования данных

**Приоритет:** P1  
**Время:** 3-5 дней  
**Автовыполнение:** 🟡 REVIEW (требует ревью UI)

**Файлы:**

- `frontend/src/app/components/EditableDataGrid.jsx`
- `frontend/src/app/pages/steps/StepData.jsx`
- `backend/app/api/datasets.py`

**Что сделать:**

1. `npm install ag-grid-react ag-grid-community`
2. Создать компонент с:
   - Редактирование ячеек
   - Undo/Redo
   - Copy/Paste
   - Column resize
3. Backend endpoint: `POST /datasets/{id}/update_cells`

**Критерии готовности:**

- [x] Ячейки редактируемые
- [x] Изменения сохраняются на backend
- [x] Undo работает (Ctrl+Z)

---

#### TASK-008: Variable Workspace для 100+ переменных

**Приоритет:** P1  
**Время:** 5-7 дней  
**Автовыполнение:** 🟡 REVIEW

**Файлы:**

- `frontend/src/app/components/VariableWorkspace.jsx`
- `frontend/src/app/components/workspace/FilterPill.jsx`
- `frontend/src/app/components/workspace/VariableRow.jsx`

**Что сделать:**

1. `npm install @tanstack/react-virtual fuse.js`
2. Виртуализированный список (для performance)
3. Поиск с fuzzy matching
4. Фильтры: тип, роль, пропуски
5. Группировка переменных

---

#### TASK-009: Protocol Templates (сохранение/загрузка)

**Приоритет:** P2  
**Время:** 2-3 дня  
**Автовыполнение:** 🟢 AUTO

**Файлы:**

- `backend/app/api/analysis.py`
- `frontend/src/app/components/ProtocolTemplateSelector.jsx`

**Endpoints:**

```
POST /protocols/save    { name, protocol }
GET  /protocols/list    → [{ name, steps, created }]
GET  /protocols/{name}  → { protocol }
```

---

#### TASK-010: Plot Customization

**Приоритет:** P2  
**Время:** 2-3 дня  
**Автовыполнение:** 🟢 AUTO

**Файлы:**

- `frontend/src/app/components/PlotConfigPanel.jsx`

**Опции:**

- Цвета групп (color picker)
- Заголовок, подписи осей
- Показывать p-value
- Экспорт: PNG, SVG, PDF

---

## 🤖 ФАЗА 3: AI Enhancement (v1.2)

### Статус: 📋 Планируется

---

#### TASK-011: AI-консультант (чат)

**Приоритет:** P1  
**Время:** 1 неделя  
**Автовыполнение:** 🟡 REVIEW

**Описание:**
Чат-интерфейс где пользователь может спросить:

- "Почему этот тест лучше?"
- "Что означает p-value?"
- "Как интерпретировать Cohen's d?"

**Реализация:**

- OpenAI API или локальная LLM
- Контекст: текущий датасет, результаты анализа
- Вывод: объяснение простыми словами

---

#### TASK-012: AI-заключение для публикации

**Приоритет:** P2  
**Автовыполнение:** 🟢 AUTO

**Описание:**
Генерировать готовый текст для раздела "Results" научной статьи:

```
The independent samples t-test revealed a statistically significant 
difference between the treatment (M = 45.2, SD = 8.3) and control 
(M = 38.1, SD = 7.9) groups, t(58) = 3.42, p = .001, d = 0.89 (large effect).
```

---

#### TASK-013: Multi-dataset сравнение

**Приоритет:** P3  
**Автовыполнение:** 🟢 AUTO

**Описание:**
Загрузить несколько датасетов и сравнить между ними.

---

## 📋 BACKLOG (без приоритета)

| ID | Задача | Сложность |
|----|--------|-----------|
| B-001 | Bayesian statistics (JASP-style) | Высокая |
| B-002 | Power analysis | Средняя |
| B-003 | Sample size calculator | Низкая |
| B-004 | Forest plot для meta-analysis | Высокая |
| B-005 | Экспорт в Word (docx) | Средняя |
| B-006 | Dark mode | Низкая |
| B-007 | Keyboard shortcuts | Низкая |
| B-008 | Localization (EN/RU/DE) | Средняя |

---

## 🔧 КАК РАБОТАТЬ С ROADMAP

### Для AI-агента

1. **Выбери задачу** из текущей фазы (сверху вниз по приоритету)
2. **Проверь статус автовыполнения:**
   - 🟢 AUTO → делай сам
   - 🟡 REVIEW → спроси пользователя
3. **Выполни по чеклисту** в описании задачи
4. **Запусти тесты:** `cd backend && python3 -m pytest tests/ -v`
5. **Закоммить:** `git commit -m "feat: TASK-XXX описание"`
6. **Обнови этот файл:** отметь `[x]` в критериях готовности

### После завершения задачи

```bash
# 1. Проверка
cd backend && python3 -m pytest tests/ -v

# 2. Коммит
git add -A
git commit -m "feat: TASK-XXX краткое описание"

# 3. Обновить ROADMAP.md — отметить задачу как ✅
```

---

## 📊 ПРОГРЕСС

| Фаза | Всего задач | Готово | % |
|------|-------------|--------|---|
| v1.0 | 6 | 6 | 100% |
| v1.1 | 4 | 2 | 50% |
| v1.2 | 3 | 0 | 0% |
| Copilot | 5 | 5 | 100% |
| Backlog | 8 | 1 | 12% |

---

*Последнее обновление: 2026-02-09*  
*Версия документа: 1.1*

---

## 🤖 ФАЗА COPILOT: LLM-Powered Statistical Analysis (ГОТОВО)

### Статус: ✅ Завершено

---

#### TASK-COP-001: Copilot Engine ✅

**Файлы:**

- `backend/app/copilot/engine.py`

**Реализовано:**

- LLM оркестрация: User Request → Plan → Code → Execute → Interpret
- Self-healing loop (3 попытки исправить код)
- SSE Streaming для real-time UI
- Session management с persistence

---

#### TASK-COP-002: Safe Code Executor ✅

**Файлы:**

- `backend/app/copilot/executor.py`

**Реализовано:**

- AST-валидация кода перед выполнением
- Whitelist импортов (pandas, numpy, scipy, statsmodels, pingouin)
- Blacklist опасных вызовов (eval, exec, subprocess)
- Resource limits (CPU, Memory, Timeout)
- Streaming output

---

#### TASK-COP-003: Expert Statistical Utilities ✅

**Файлы:**

- `backend/app/copilot/clinical_utils.py`

**Реализовано:**

- `analyze_continuous()` — полный статистический battery
- `analyze_categorical()` — Chi-square/Fisher
- `fit_mixed_models()` — Linear Mixed Effects
- `discover_longitudinal_groups()` — автодетект паттернов V1/V2/V3
- Publication-ready графики (300 DPI)

---

#### TASK-COP-004: DOCX Report Generator ✅

**Файлы:**

- `backend/app/copilot/report.py`

**Реализовано:**

- Профессиональный Word-отчёт с глоссарием
- Рекурсивный рендер вложенных результатов
- Вставка графиков PNG
- Секции: Design, Results, Interpretation, Appendix

---

#### TASK-COP-005: API Endpoints ✅

**Файлы:**

- `backend/app/copilot/router.py`

**Endpoints:**

- `POST /api/v2/copilot/analyze` — полный цикл анализа
- `POST /api/v2/copilot/plan` — только планирование
- `POST /api/v2/copilot/execute` — выполнение плана
- `POST /api/v2/copilot/execute_stream` — SSE streaming
- `POST /api/v2/copilot/refine` — итеративное уточнение
- `GET /api/v2/copilot/session/{id}` — состояние сессии
- `POST /api/v2/copilot/report` — скачать DOCX

---

### Тестовое покрытие Copilot

| Файл | Тестов | Статус |
|------|--------|--------|
| `test_copilot_engine.py` | 14 | ✅ |
| `test_copilot_report.py` | 13 | ✅ |
| `test_auto_discovery.py` | 2 | ✅ |

**Всего: 29 тестов**
