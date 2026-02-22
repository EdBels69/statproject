---
description: Как провести полный статистический анализ клинического исследования и получить Word-отчёт
---

# Анализ клинического исследования (полный pipeline)

## Предварительные требования

1. Backend должен быть остановлен (скрипт работает standalone)
2. Файл данных: `docs/Первичка для анализа работа.xlsx`
3. Python environment с установленными зависимостями

## Шаги

### 1. Перейти в директорию backend

// turbo

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend
```

### 2. Запустить анализ

// turbo

```bash
python3 scripts/run_diamag_analysis.py
```

### 3. Найти сгенерированный отчёт

// turbo

```bash
ls -la output/*.docx
```

### 4. Открыть отчёт для проверки

```bash
open output/diamag_report_*.docx
```

## Что делает скрипт

1. **Загрузка данных**: Читает Excel, обрабатывает пропуски
2. **Table 1**: Базовые характеристики пациентов по группам
3. **Первичные endpoints**: УШОБП часть 2 и 3
   - Kruskal-Wallis / ANOVA
   - Mixed Effects Model (время × группа)
   - Bayes Factor
   - Effect sizes
4. **Вторичные endpoints**: DASS-21, Epworth, Апатия, Stroop, TMT, PDQ-39
5. **Респондеры**: Доля улучшившихся, Fisher exact test
6. **Безопасность**: Сравнение АД
7. **Word-отчёт**: Все таблицы и графики

## При ошибках

- Проверь путь к Excel файлу
- Убедись что pingouin установлен: `pip install pingouin`
- Смотри traceback в терминале

## Ключевые файлы

| Файл | Описание |
|------|----------|
| `scripts/run_diamag_analysis.py` | Основной скрипт анализа |
| `app/stats/engine.py` | Статистические тесты |
| `app/modules/reporting.py` | Генерация отчётов |
| `output/diamag_report_*.docx` | Результирующий отчёт |
