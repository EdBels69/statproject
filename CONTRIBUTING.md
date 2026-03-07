# 📖 Правила работы с проектом Clinimetria

> Этот файл дополняет AGENTS.md и содержит детальные правила для AI-агентов.

---

## 🎯 Про пользователя

| Характеристика | Значение |
|----------------|----------|
| Уровень программирования | Начинающий (почти ноль) |
| JavaScript/Python | Не знает синтаксис |
| Понимание концепций | Хорошее |
| Способ работы | Через AI-агентов |
| Язык общения | Русский |

## 📝 Как общаться

### ✅ Делай так

1. **Пиши код сам** — не проси пользователя ничего редактировать
2. **Объясняй ЧТО сделал** — не КАК это работает технически
3. **Используй простые слова** — избегай программистского жаргона
4. **Предлагай варианты** — если нужен выбор, опиши pros/cons простым языком
5. **Делай коммиты сам** — с понятными сообщениями на русском

### ❌ Не делай так

1. Не показывай большие блоки кода в сообщениях
2. Не проси "вставить это в файл X"
3. Не используй технические термины без объяснения
4. Не спрашивай "какой подход предпочитаете — X или Y" без объяснения разницы

---

## 🏗 Структура проекта

```
statproject/
├── AGENTS.md              # 👈 Главные правила для агентов
├── CONTRIBUTING.md        # 👈 Этот файл
├── review.md              # Текущий статус проекта
│
├── backend/               # Python FastAPI API
│   ├── app/
│   │   ├── api/           # HTTP endpoints
│   │   ├── stats/         # Статистика (26 методов)
│   │   ├── core/          # Ядро системы
│   │   └── modules/       # Утилиты
│   └── tests/             # Pytest тесты
│
├── frontend/              # React + Vite UI
│   └── src/
│       ├── app/
│       │   ├── components/  # UI компоненты
│       │   └── pages/       # Страницы
│       └── lib/             # Утилиты
│
└── .agent/workflows/      # Workflow-файлы для агентов
    ├── add-stat-method.md
    ├── start-project.md
    ├── run-tests.md
    └── deploy.md
```

---

## 🎨 Дизайн-система

### Цвета

```css
/* Основные */
--color-primary: #3B82F6;      /* Синий — действия */
--color-success: #22C55E;      /* Зелёный — p < 0.05 */
--color-warning: #F59E0B;      /* Жёлтый — предупреждения */
--color-danger: #EF4444;       /* Красный — ошибки */

/* Фон и текст */
--color-bg: #F8FAFC;           /* Фон страницы */
--color-card: #FFFFFF;         /* Карточки */
--color-text: #1E293B;         /* Основной текст */
--color-muted: #64748B;        /* Вторичный текст */
--color-border: #E2E8F0;       /* Границы */
```

### Размеры

```css
/* Отступы */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;

/* Радиусы */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;

/* Тени */
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px rgba(0,0,0,0.1);
```

### Шрифты

- **UI**: Inter, -apple-system, sans-serif
- **Код/числа**: SF Mono, Monaco, monospace
- **Размеры**: 12px (мелкий), 14px (обычный), 16px (крупный)

---

## 📊 JAMOVI-style UI принципы

### 1. Таблица данных (Data View)

- Редактируемые ячейки
- Нумерация строк слева
- Заголовки колонок с типами
- Фильтрация и сортировка

### 2. Панель переменных (Variable Panel)

- Список всех переменных
- Иконки типов (числовой, текст, дата)
- Drag-and-drop в зоны анализа
- Поиск и фильтрация

### 3. Панель тестов (Test Panel)

- Категории: Сравнение, Корреляция, Регрессия...
- По клику — конфигуратор теста
- AI-рекомендации

### 4. Результаты (Results Panel)

- APA-стиль таблиц
- Графики (интерактивные)
- AI-интерпретация
- Экспорт в PDF/HTML

---

## 🔧 Код-конвенции

### Python

```python
# Документация функций
def calculate_effect_size(group1: pd.Series, group2: pd.Series) -> float:
    """
    Calculate Cohen's d effect size.
    
    Args:
        group1: First group data
        group2: Second group data
        
    Returns:
        Effect size value (0.2=small, 0.5=medium, 0.8=large)
    """
    pass

# Именование
snake_case           # функции и переменные
PascalCase           # классы
UPPER_SNAKE_CASE     # константы
```

### JavaScript/React

```jsx
// Компоненты — PascalCase
function VariableSelector({ variables, onSelect }) {
  // Хуки — camelCase, начиная с use
  const [selected, setSelected] = useState(null);
  
  // Обработчики — handleEventName
  const handleSelect = (variable) => {
    setSelected(variable);
    onSelect(variable);
  };
  
  return <div>...</div>;
}

// Экспорт
export default VariableSelector;
```

### CSS классы

```css
/* БЭМ-подобное именование */
.variable-selector { }
.variable-selector__list { }
.variable-selector__item { }
.variable-selector__item--selected { }
```

---

## 🧪 Тестирование

### Покрытие

| Область | Требование |
|---------|------------|
| Статметоды | 100% (каждый метод) |
| API endpoints | Основные сценарии |
| Data Prep | Happy path + edge cases |
| UI | Ручное + E2E (Playwright) |

### Структура теста

```python
def test_что_тестируем():
    # Arrange — подготовка данных
    df = pd.DataFrame(...)
    
    # Act — выполнение
    result = function_under_test(df)
    
    # Assert — проверка
    assert result["p_value"] < 0.05
```

---

## 📦 Зависимости

### Backend (Python)

| Пакет | Версия | Назначение |
|-------|--------|------------|
| fastapi | 0.109+ | Web framework |
| pandas | 2.0+ | Data manipulation |
| scipy | 1.11+ | Statistics |
| statsmodels | 0.14+ | Advanced stats |
| scikit-learn | 1.3+ | ML, MICE imputation |
| matplotlib | 3.8+ | Plotting |
| seaborn | 0.13+ | Statistical plots |

### Frontend (React)

| Пакет | Назначение |
|-------|------------|
| react | UI framework |
| vite | Build tool |
| recharts | Charts |
| react-router-dom | Routing |

---

## 🚀 Релизный процесс

### Версионирование

```
v{major}.{minor}.{patch}

major — Breaking changes
minor — Новые функции
patch — Исправления багов

Пример: v1.2.3
```

### Чеклист перед релизом

- [ ] Все тесты проходят
- [ ] Нет deprecation warnings в нашем коде
- [ ] review.md обновлён
- [ ] Docker build успешен
- [ ] Проверено на <http://localhost>

---

## 📞 Контакты

- **Владелец**: Эдуард
- **Репозиторий**: GitHub (private)
- **Документация**: README.md, AGENTS.md, review.md

---

*Последнее обновление: 2026-01-13*
