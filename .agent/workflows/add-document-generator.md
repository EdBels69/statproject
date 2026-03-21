---
description: Как создать новый тип отчёта/документа
---

# Создание нового генератора документов

## Когда использовать

- Нужен новый тип отчёта (презентация, статья, etc.)
- Нужен новый формат (HTML, PDF, etc.)

## Шаги

### 1. Создать генератор

```bash
touch backend/app/generators/new_generator.py
```

```python
# backend/app/generators/new_generator.py
from typing import Dict, Any
from pathlib import Path
from .base import AbstractGenerator

class NewDocumentGenerator(AbstractGenerator):
    """Генератор нового типа документа."""
    
    def __init__(self, study_config: Dict, results: Dict):
        self.study_config = study_config
        self.results = results
        self.template_path = Path(__file__).parent / "templates" / "new_template.docx"
    
    def generate(self, output_path: str) -> str:
        """
        Генерировать документ.
        
        Returns:
            Путь к созданному файлу
        """
        # 1. Подготовка данных
        data = self._prepare_data()
        
        # 2. Загрузка шаблона
        # ...
        
        # 3. Заполнение
        # ...
        
        # 4. Сохранение
        # ...
        
        return output_path
    
    def _prepare_data(self) -> Dict[str, Any]:
        """Подготовить данные для шаблона."""
        return {
            "title": self.study_config.get("title"),
            "results": self.results,
            # ...
        }
```

### 2. Добавить шаблон

```bash
# Создать шаблон документа
touch backend/app/generators/templates/new_template.docx
```

### 3. Добавить API endpoint

```python
# backend/app/api/reports.py

@router.post("/generate-new")
async def generate_new_report(request: GenerateRequest):
    generator = NewDocumentGenerator(
        study_config=request.study_config,
        results=request.results
    )
    
    output_path = generator.generate(f"output/new_report_{request.id}.docx")
    
    return {"path": output_path}
```

### 4. Добавить frontend UI (опционально)

```jsx
// frontend/src/app/components/ReportTypeSelector.jsx

const reportTypes = [
  { id: "standard", label: "Стандартный отчёт" },
  { id: "article", label: "Научная статья" },
  { id: "new_type", label: "Новый тип" },  // Добавить
];
```

// turbo

### 5. Тестировать

```bash
cd backend && python -c "
from app.generators.new_generator import NewDocumentGenerator
gen = NewDocumentGenerator({}, {})
print('Generator created:', gen)
"
```

## Чеклист

- [ ] Генератор создан в `generators/`
- [ ] Наследует от AbstractGenerator
- [ ] Шаблон добавлен в `templates/`
- [ ] API endpoint создан
- [ ] Frontend обновлён (опционально)
