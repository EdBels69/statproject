---
description: Как добавить новый статистический метод в проект
---

# Добавление нового статистического метода

## Шаги

### 1. Backend: Создать handler в engine.py

// turbo

```bash
# Открыть файл
code backend/app/stats/engine.py
```

Добавить функцию `_handle_{method_name}` по образцу существующих.

### 2. Backend: Зарегистрировать метод

// turbo

```bash
code backend/app/stats/registry.py
```

Добавить в `METHODS` словарь:

```python
"new_method": {
    "id": "new_method",
    "name": "Название метода",
    "description": "Описание когда использовать",
    "type": "parametric",  # или nonparametric
    "category": "comparison"  # comparison, correlation, regression, etc.
}
```

### 3. Frontend: Добавить в панель тестов

// turbo

```bash
code frontend/src/app/components/analysis/TestSelectionPanel.jsx
```

Добавить в соответствующую категорию.

### 4. Написать тест

// turbo

```bash
# Создать test_new_method.py
touch backend/tests/test_new_method.py
```

Написать минимальный тест по образцу `test_anova_tukey.py`.

### 5. Проверить

// turbo

```bash
cd backend && python3 -m pytest tests/test_new_method.py -v
```

### 6. Закоммитить

```bash
git add -A
git commit -m "feat: добавлен метод {название}"
```
