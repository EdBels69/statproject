---
description: Как добавить новый статистический метод в проект
---

# Добавление статистического метода

## Предварительные условия

- Метод должен быть научно обоснован
- Должен существовать в scipy/pingouin/statsmodels

## Шаги

### 1. Добавить логику в engine.py

```bash
# Открыть файл
code backend/app/stats/engine.py
```

Добавить функцию-обработчик:

```python
def _handle_new_method(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Новый статистический метод.
    """
    # 1. Подготовка данных
    data_a = df[col_a].dropna()
    data_b = df[col_b].dropna()
    
    # 2. Выполнение теста
    stat, p_value = scipy.stats.new_test(data_a, data_b)
    
    # 3. Effect size
    effect_size = compute_effect_size(data_a, data_b)
    
    # 4. Интерпретация
    interpretation = interpret_effect_size(effect_size, "cohens_d")
    
    return {
        "method": "new_method",
        "method_name": "Название метода",
        "statistic": float(stat),
        "p_value": float(p_value),
        "effect_size": float(effect_size),
        "effect_size_name": "Cohen's d",
        "effect_size_interpretation": interpretation,
        "conclusion": "significant" if p_value < 0.05 else "not_significant"
    }
```

### 2. Зарегистрировать в run_analysis()

Найти switch-case в `run_analysis()` и добавить:

```python
elif method_id == "new_method":
    return _handle_new_method(df, col_a, col_b, kwargs)
```

### 3. Добавить визуализацию (опционально)

В `backend/app/modules/reporting.py` добавить case для нового метода.

### 4. Написать тест

```python
# backend/tests/test_engine.py

def test_new_method():
    df = pd.DataFrame({
        "group": ["A"] * 20 + ["B"] * 20,
        "value": np.random.randn(40)
    })
    
    result = run_analysis(df, "new_method", "value", "group")
    
    assert result["method"] == "new_method"
    assert "p_value" in result
    assert result["p_value"] >= 0 and result["p_value"] <= 1
```

// turbo

### 5. Запустить тесты

```bash
cd backend && python -m pytest tests/test_engine.py -v -k "new_method"
```

## Чеклист

- [ ] Функция `_handle_new_method` создана
- [ ] Зарегистрирована в `run_analysis()`
- [ ] Возвращает: method, p_value, effect_size, interpretation
- [ ] Тест написан и проходит
- [ ] Документация обновлена (опционально)
