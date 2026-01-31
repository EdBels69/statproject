# AI Prompt для редизайна AnalysisDesign

**Версия**: 1.0  
**Дата**: 2026-01-27

---

## КОНТЕКСТ ПРОЕКТА

StatWizard — веб-приложение для статистического анализа клинических данных.  
**Stack**: React + Vite (frontend), FastAPI + Python (backend)

### Текущая проблема

Страница **Конструктор** (`AnalysisDesign.jsx`) — монолит 2573 строк:

- Неработающие UI-элементы (табы слева)
- 3 drop-зоны вместо простых dropdown
- Огромные пустые пространства
- 2 дублирующих предпросмотра

---

## ЗАДАЧА

Провести **полный редизайн** страницы AnalysisDesign:

### 1. Декомпозиция

Разбить монолит на компоненты:

```
components/analysis/
  ProtocolBuilder.jsx    # Центральная логика протокола
  VariableSelector.jsx   # Панель переменных
  TestCatalog.jsx        # Каталог стат-тестов
  TemplatePanel.jsx      # Шаблоны анализа
  ResultsViewer.jsx      # Отображение результатов
```

### 2. Новый лейаут

**Двухколоночный** вместо трёхколоночного:

- Левая 70%: табы [Настройка | Протокол | Результаты]
- Правая 30%: список переменных с поиском

### 3. UX-упрощения

- **Dropdown** вместо drag-and-drop для ролей
- **Автоподбор тестов** по выбору Target + Group
- **Один предпросмотр** вместо двух
- **Кнопка "Выполнить"** всегда видна

---

## КЛЮЧЕВЫЕ ФАЙЛЫ

| Файл | Назначение |
|------|------------|
| `frontend/src/app/pages/AnalysisDesign.jsx` | Главный файл (редизайн) |
| `frontend/src/lib/api.js` | API-клиент |
| `frontend/src/app/components/ui/` | UI-компоненты |
| `backend/app/api/analysis.py` | Backend endpoints |

---

## DESIGN TOKENS

```css
--text-primary: #1a1a1a
--text-secondary: #6b7280
--text-muted: #9ca3af
--border-color: #e5e7eb
--bg-primary: #ffffff
--bg-secondary: #f9fafb
--bg-tertiary: #f3f4f6
--accent: #f97316 (orange)
```

---

## API ENDPOINTS

```
GET  /api/analysis/datasets           # Список датасетов
GET  /api/analysis/datasets/{id}      # Данные датасета
POST /api/analysis/run                # Запуск анализа
POST /api/analysis/universal          # Универсальный анализ
POST /api/analysis/universal/export/{format}  # Экспорт
```

---

## ПРАВИЛА

1. **JSX**: React functional components + hooks
2. **Стили**: CSS переменные var(--token), НЕ Tailwind inline
3. **Типы**: Пропсы с деструктуризацией и дефолтами
4. **i18n**: useTranslation() для текстов
5. **Модульность**: Один компонент = одна ответственность

---

## ПРИОРИТЕТЫ

1. ✅ MVP: Настройка → Выполнить → Результаты
2. ⏳ Потом: Шаблоны, AI-рекомендации
3. ⏳ Бэклог: Сохранение протоколов

---

## ВЕРИФИКАЦИЯ

```bash
# Frontend компилируется
cd frontend && npm run build

# Нет ошибок TypeScript
npm run lint

# Страница открывается
open http://localhost:5173/design/{dataset_id}
```
