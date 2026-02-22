---
name: Clinical Trial Analysis
description: Как провести полный статистический анализ клинического исследования с генерацией Word-отчёта
---

# 🏥 Clinical Trial Analysis Skill

## Когда использовать

Этот навык применяется когда пользователь хочет:

- Проанализировать данные клинического исследования
- Получить Word-отчёт со статистикой
- Провести анализ с несколькими временными точками
- Сравнить группы лечения

## Структура данных

### Типичный Excel файл клинического исследования

| Колонка | Описание | Пример |
|---------|----------|--------|
| `Группа` | Номер группы лечения | 1, 2, 3, 4 |
| `ID` | Уникальный ID пациента | "001", "002" |
| `Возраст` | Возраст при включении | 65 |
| `Пол` | М/Ж | "М", "Ж" |
| `*_V1`, `*_V2`, ... | Показатели по визитам | Числа |

### Ключевые концепции

- **Primary endpoint**: Главный показатель эффективности
- **Secondary endpoints**: Вторичные показатели
- **Визиты**: V1 (скрининг), V2 (baseline), V3-V6 (follow-up)
- **Респондеры**: Пациенты с улучшением ≥ порога

## Готовый скрипт

Для анализа данных ДИАМАГ используй готовый скрипт:

```bash
cd backend
python3 scripts/run_diamag_analysis.py
```

**Скрипт делает:**

1. Загружает Excel
2. Генерирует Table 1 (baseline)
3. Kruskal-Wallis для каждого endpoint
4. Bayes Factor
5. Анализ респондеров
6. Word-отчёт с графиками

## Как адаптировать под другой датасет

### Шаг 1: Изменить конфигурацию endpoints

В файле `backend/scripts/run_diamag_analysis.py` найди `ENDPOINTS_CONFIG`:

```python
ENDPOINTS_CONFIG = {
    "endpoint_id": {
        "name": "Полное название показателя",
        "short_name": "Короткое имя",
        "columns": {
            "V2": "Название колонки V2 в Excel",
            "V3": "Название колонки V3 в Excel",
            # ...
        },
        "primary": True,  # или False для вторичных
    },
}
```

### Шаг 2: Изменить путь к файлу

```python
EXCEL_PATH = PROJECT_ROOT.parent / "docs" / "ТВОЙ_ФАЙЛ.xlsx"
```

### Шаг 3: Изменить колонки группы и ID

```python
GROUP_COL = "Группа"  # Имя колонки с группами
ID_COL = "ID"         # Имя колонки с ID пациентов
```

## Статистические методы

### Межгрупповое сравнение (одна точка)

```python
from scipy import stats

# Kruskal-Wallis (непараметрический, 3+ группы)
stat, p_value = stats.kruskal(group1_values, group2_values, group3_values)

# Mann-Whitney U (непараметрический, 2 группы)
stat, p_value = stats.mannwhitneyu(group1_values, group2_values)
```

### Продольный анализ (Mixed Effects)

```python
import statsmodels.formula.api as smf

# Linear Mixed Model: outcome ~ group * time + (1|subject)
formula = "value ~ C(group) * C(visit)"
model = smf.mixedlm(formula, df, groups=df["subject_id"])
result = model.fit()
```

### Bayes Factor

```python
def compute_bayes_factor(p_value):
    """BF10 из p-value (Sellke bound)"""
    import numpy as np
    if p_value <= 0 or p_value >= 1:
        return np.nan
    return -1 / (np.e * p_value * np.log(p_value))
```

### Effect Size

| Тест | Effect Size | Формула |
|------|-------------|---------|
| t-test | Cohen's d | (M1-M2) / SD_pooled |
| ANOVA | η² (eta-squared) | SS_between / SS_total |
| Kruskal-Wallis | ε² (epsilon-squared) | (H - k + 1) / (N - k) |
| Корреляция | r | Pearson/Spearman |

## Генерация Word

```python
from docx import Document
from docx.shared import Inches

doc = Document()

# Заголовок
doc.add_heading("СТАТИСТИЧЕСКИЙ ОТЧЁТ", level=1)

# Таблица
table = doc.add_table(rows=1, cols=3, style="Table Grid")
# ... заполнение

# График
doc.add_picture("plot.png", width=Inches(5.5))

# Сохранить
doc.save("report.docx")
```

## Чеклист анализа

- [ ] Загрузить данные и проверить структуру
- [ ] Table 1: N, возраст, пол по группам
- [ ] Первичный endpoint: описательные + тест
- [ ] Вторичные endpoints
- [ ] Effect sizes для всех тестов
- [ ] Bayes Factor
- [ ] Графики (boxplot, spaghetti)
- [ ] Респондеры (если применимо)
- [ ] Word-отчёт

## Частые ошибки

### 1. Pingouin Mixed ANOVA: "Subject IDs cannot overlap"

**Причина:** Одинаковые ID у разных групп (например, ID=1 есть в группах 1 и 2)

**Решение:** Используй statsmodels вместо pingouin:

```python
import statsmodels.formula.api as smf
model = smf.mixedlm("value ~ C(group) * C(time)", df, groups=df["subject"])
```

### 2. KeyError при чтении Excel

**Причина:** Опечатка в названии колонки

**Решение:** Проверь точные имена:

```python
print(df.columns.tolist())
```

### 3. Empty DataFrame при фильтрации

**Причина:** Нет данных для визита или группы

**Решение:** Проверь наличие данных:

```python
print(df.groupby(["group", "visit"]).size())
```

## Ссылки на файлы проекта

- [run_diamag_analysis.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/scripts/run_diamag_analysis.py) — главный скрипт
- [engine.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/app/stats/engine.py) — статистические методы
- [reporting.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting.py) — генерация отчётов

## Для продолжения работы

Если тебе нужно продолжить анализ:

1. Прочитай `task.md` в артефактах — там актуальный чеклист
2. Проверь скрипт: `python3 scripts/run_diamag_analysis.py`
3. Смотри Word: `open output/diamag_report_*.docx`
