# AI Prompt: Clinimetria v2.0 Development

**Версия**: 2.0  
**Дата**: 2026-01-27

---

## КОНТЕКСТ

Clinimetria — веб-приложение для статистического анализа клинических данных.

### Стек

- **Frontend**: React + Vite + react-i18next
- **Backend**: FastAPI + Python + scikit-learn + statsmodels
- **Reports**: python-docx, xhtml2pdf, jinja2

### Текущее состояние

- ✅ Базовые тесты (t-test, ANOVA, correlation, regression)
- ✅ Mixed Effects Models (LMM)
- ✅ Clustered Correlation
- ⏳ Частичная локализация (смешанный RU/EN)
- ❌ ML-методы (clustering, boosting)
- ❌ Факторный анализ

---

## ЗАДАЧИ v2.0

### 1. Двуязычность (Priority: HIGH)

```bash
# Структура
frontend/src/
  locales/
    ru.json      # Русский словарь
    en.json      # English dictionary
  lib/i18n.js    # Конфигурация
  hooks/useTranslation.js
```

**Правила:**

- Все UI-тексты через `t('key')`
- Переключатель языка в Header
- Сохранение в localStorage

### 2. ML-методы (Priority: HIGH)

```python
# backend/app/stats/methods/ml/
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.decomposition import PCA
```

**Реализовать:**

- `gradient_boosting.py` — XGBoost wrapper
- `random_forest.py` — RF classification/regression
- `kmeans.py` — K-Means clustering
- `hierarchical.py` — Ward linkage
- `pca.py` — Principal Component Analysis

### 3. Факторный анализ (Priority: MEDIUM)

```python
from factor_analyzer import FactorAnalyzer
from factor_analyzer.factor_analyzer import calculate_kmo
```

**Реализовать:**

- KMO test
- Bartlett's test
- Scree plot
- Factor loadings table

### 4. UI полировка (Priority: MEDIUM)

- Skeleton loaders
- Error boundaries
- Empty states
- Tooltips

---

## КЛЮЧЕВЫЕ ФАЙЛЫ

| Путь | Назначение |
|------|------------|
| `frontend/src/app/pages/AnalysisDesign.jsx` | Главная страница Конструктор |
| `frontend/src/lib/i18n.js` | Конфигурация локализации |
| `backend/app/core/protocol_engine.py` | Движок анализа |
| `backend/app/stats/registry.py` | Реестр методов |

---

## СТРУКТУРА НОВОГО МЕТОДА

```python
# backend/app/stats/methods/ml/kmeans.py

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import pandas as pd
import numpy as np

class KMeansMethod:
    """K-Means Clustering"""
    
    id = "kmeans"
    name = "K-Means Clustering"
    category = "clustering"
    
    @staticmethod
    def run(df: pd.DataFrame, config: dict) -> dict:
        features = config.get("features", [])
        n_clusters = config.get("n_clusters", 3)
        
        X = df[features].dropna()
        model = KMeans(n_clusters=n_clusters, random_state=42)
        labels = model.fit_predict(X)
        
        return {
            "labels": labels.tolist(),
            "centers": model.cluster_centers_.tolist(),
            "inertia": model.inertia_,
            "silhouette": silhouette_score(X, labels),
            "n_clusters": n_clusters
        }
```

---

## ПРАВИЛА

1. **Все тексты через t()** — никаких хардкод строк
2. **Методы регистрировать в registry** — единая точка входа
3. **Результаты JSON-serializable** — numpy → list
4. **Документация на русском** — docstrings

---

## ВЕРИФИКАЦИЯ

```bash
# Frontend
cd frontend && npm run build

# Backend тесты
cd backend && pytest tests/ -v

# Локализация
grep -r "\"[А-Яа-я]" frontend/src --include="*.jsx" # Не должно быть
```

---

## ПРИОРИТЕТЫ

1. 🔴 Двуязычность (переключатель + словари)
2. 🔴 K-Means + Hierarchical Clustering
3. 🔴 PCA + Factor Analysis
4. 🟡 Gradient Boosting
5. 🟡 UI polish
