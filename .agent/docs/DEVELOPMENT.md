---
name: Development Guide
description: Как запускать, тестировать и разрабатывать StatProject
---

# 🛠️ Development Guide

> Инструкции для AI-агентов и разработчиков

---

## 🚀 Quick Start

### Требования

- Python 3.11+
- Node.js 18+
- npm 9+

### Установка и запуск

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Frontend (другой терминал)
cd frontend
npm install
npm run dev

# 3. Открыть http://localhost:5173
```

### Или через скрипт

```bash
./start.sh   # Запустить всё
./stop.sh    # Остановить
```

---

## 🧪 Тестирование

### Backend тесты

```bash
cd backend

# Все тесты
python -m pytest tests/ -v

# Конкретный файл
python -m pytest tests/test_engine.py -v

# С покрытием
python -m pytest tests/ --cov=app --cov-report=html
```

### Ключевые тестовые файлы

| Файл | Что тестирует |
|------|---------------|
| `test_engine.py` | Статистические методы |
| `test_engine_integration.py` | Полный pipeline |
| `test_api_datasets.py` | API endpoints |
| `test_reporting.py` | Генерация отчётов |

### Добавление теста

```python
# tests/test_new_feature.py
import pytest
from app.stats.engine import run_analysis

def test_new_method():
    df = pd.DataFrame(...)
    result = run_analysis(df, "new_method", "col_a", "col_b")
    
    assert result["p_value"] is not None
    assert "effect_size" in result
```

---

## 📝 Code Style

### Python

```python
# Типизация обязательна
def analyze(df: pd.DataFrame, method: str) -> Dict[str, Any]:
    """
    Docstring обязателен для публичных функций.
    
    Args:
        df: Данные для анализа
        method: Метод анализа
        
    Returns:
        Dict с результатами
    """
    pass

# Используй f-strings
message = f"Result: {value:.3f}"

# Константы CAPS_SNAKE_CASE
MAX_ITERATIONS = 100

# Классы PascalCase
class StudyConfig:
    pass
```

### JavaScript/React

```jsx
// Компоненты — функциональные
export function DataTable({ data, onSelect }) {
  const [selected, setSelected] = useState(null);
  
  return (
    <div className="p-4">
      {/* JSX */}
    </div>
  );
}

// Хуки — use* prefix
function useDatasets() {
  // ...
}
```

---

## 🔧 Типичные задачи разработки

### Добавить новый статистический метод

1. **Добавить логику в engine.py**:

   ```python
   # backend/app/stats/engine.py
   
   def _handle_new_method(df, col_a, col_b, kwargs):
       # Ваша логика
       return {
           "method": "new_method",
           "p_value": p,
           "statistic": stat,
           "effect_size": es,
           ...
       }
   ```

2. **Добавить в run_analysis()**:

   ```python
   elif method_id == "new_method":
       return _handle_new_method(df, col_a, col_b, kwargs)
   ```

3. **Добавить визуализацию в reporting.py**

4. **Добавить тест**

### Добавить новый API endpoint

```python
# backend/app/api/new_endpoint.py
from fastapi import APIRouter, HTTPException
from app.schemas.new_schema import NewRequest, NewResponse

router = APIRouter(prefix="/api/new", tags=["new"])

@router.post("/action", response_model=NewResponse)
async def new_action(request: NewRequest):
    # Логика
    return NewResponse(...)
```

Зарегистрировать в `main.py`:

```python
from app.api import new_endpoint
app.include_router(new_endpoint.router)
```

### Добавить новую страницу frontend

1. **Создать компонент**:

   ```jsx
   // frontend/src/app/pages/NewPage.jsx
   export function NewPage() {
     return <div>New Page</div>;
   }
   ```

2. **Добавить route в App.jsx**:

   ```jsx
   <Route path="/new-page" element={<NewPage />} />
   ```

---

## 🐛 Debugging

### Backend

```python
# Логирование
import logging
logger = logging.getLogger(__name__)
logger.info(f"Processing {dataset_id}")

# Breakpoint
import pdb; pdb.set_trace()
```

### API тестирование

```bash
# HTTPie
http POST localhost:8000/api/datasets/upload file@data.xlsx

# cURL
curl -X GET http://localhost:8000/api/datasets
```

### Frontend

```javascript
console.log('Debug:', data);

// React DevTools (F12 → Components)
```

---

## 📦 Dependencies

### Backend (requirements.txt)

| Package | Назначение |
|---------|------------|
| fastapi | Web framework |
| uvicorn | ASGI server |
| pandas | Data manipulation |
| numpy | Numerical computing |
| scipy | Statistical tests |
| pingouin | Advanced statistics |
| statsmodels | Regression, LMM |
| python-docx | Word generation |
| matplotlib, seaborn | Plots |
| httpx | HTTP client (for LLM) |

### Frontend (package.json)

| Package | Назначение |
|---------|------------|
| react | UI framework |
| vite | Build tool |
| tailwindcss | Styling |
| react-router-dom | Routing |
| axios | HTTP client |

---

## 🔄 Git Workflow

```bash
# Новая фича
git checkout -b feature/new-feature
# ... работа ...
git add -A
git commit -m "feat: описание"
git push origin feature/new-feature

# Баг фикс
git checkout -b fix/bug-description
git commit -m "fix: описание"
```

### Commit Messages

```
feat: новая функциональность
fix: исправление бага
docs: документация
refactor: рефакторинг без изменения поведения
test: добавление тестов
chore: обновление зависимостей, конфигов
```

---

## 🚢 Deployment

```bash
# Docker (production)
docker-compose up -d

# Или через скрипт
./deploy.sh
```

См. `DEPLOYMENT.md` для деталей.
