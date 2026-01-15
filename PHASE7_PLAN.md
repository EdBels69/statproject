# Phase 7: UX Overhaul — StatTech-Style Interface

> **Цель:** Интуитивный, "свежий" UI как в StatTech  
> **Проблема:** Текущий UI — "лепнина", сложно понять flow

---

## Ключевая идея: Table-Centric Variable Config

### Как в StatTech

```
┌──────────┬──────────┬──────────┬──────────┐
│ Номер    │ Фамилия  │ Возраст  │ Группа   │ ← Заголовки
├──────────┼──────────┼──────────┼──────────┤
│ [▼ Тип]  │ [▼ Тип]  │ [▼ Тип]  │ [▼ Тип]  │ ← Dropdown типа
├──────────┼──────────┼──────────┼──────────┤
│ 1        │ Иванов   │ 45       │ A        │
│ 2        │ Петров   │ 32       │ B        │
└──────────┴──────────┴──────────┴──────────┘
```

### Типы переменных

- **Не определено** (серый)
- **Идентификатор** (например ID пациента)
- **Количественная** (numeric)
- **Категориальная** (groups)
- **Дата**

---

## Task 7.1: Data Table with Inline Type Selectors

### Компонент: `DataTableWithTypes.jsx`

```jsx
// Под каждым заголовком — dropdown для выбора типа
<table>
  <thead>
    <tr>
      {columns.map(col => (
        <th key={col.name}>
          <div className="text-sm font-semibold">{col.name}</div>
          <select 
            value={col.type} 
            onChange={e => setColumnType(col.name, e.target.value)}
            className="mt-1 w-full text-xs"
          >
            <option value="">Не определено</option>
            <option value="id">Идентификатор</option>
            <option value="numeric">Количественная</option>
            <option value="categorical">Категориальная</option>
            <option value="date">Дата</option>
          </select>
        </th>
      ))}
    </tr>
  </thead>
  <tbody>
    {rows.map(row => ...)}
  </tbody>
</table>
```

---

## Task 7.2: Variable List View (Row → Column)

### Идея: Первая строка Excel → Вертикальный список

```
┌─────────────────────────────────────────────────────┐
│ ПЕРЕМЕННЫЕ                                  [⚙️]    │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ Возраст                                         │ │
│ │ [Количественная ▼]  [📊 Target ▼]               │ │
│ │ n=150 • M=45.2 • SD=12.3                        │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Группа                                          │ │
│ │ [Категориальная ▼]  [🔀 Factor ▼]               │ │
│ │ n=150 • 2 категории: A(75), B(75)               │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Пол                                             │ │
│ │ [Категориальная ▼]  [— Не использовать]         │ │
│ │ n=150 • М(80), Ж(70)                            │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Роли переменных

- **Target** (зависимая) — оранжевый
- **Factor/Group** (независимая) — чёрный
- **Covariate** — серый
- **Не использовать** — скрыта

---

## Task 7.3: Dependencies Modal (как StatTech)

### Gear icon на каждом столбце → Modal

```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Настройки: Систолическое АД                      │
├─────────────────────────────────────────────────────┤
│ ОБЩИЕ  │  ГРУППЫ  │  ЗАВИСИМОСТИ  │  МОДЕЛИ        │
├─────────────────────────────────────────────────────┤
│ Тип: Количественная                                 │
│                                                     │
│ ЗАВИСИМЫЕ ПЕРЕМЕННЫЕ:                               │
│ ☑ Курение                                           │
│ ☑ Возраст                                           │
│ ☐ Пол                                               │
│ ☐ ID пациента                                       │
│                                                     │
│                               [Отмена] [Сохранить]  │
└─────────────────────────────────────────────────────┘
```

---

## Task 7.4: Fresh Design (не "лепнина")

### Принципы

1. **Больше воздуха** — padding 16-24px
2. **Меньше бордеров** — только hover-state
3. **Контраст** — black text, white bg, orange accents
4. **Чёткая иерархия** — kicker labels (10px uppercase)

### Компоненты

```css
/* Карточка переменной */
.variable-card {
  background: white;
  border: 1px solid transparent;
  padding: 16px 20px;
  transition: border-color 0.15s;
}
.variable-card:hover {
  border-color: var(--border-color);
}

/* Dropdown в заголовке */
.column-type-select {
  appearance: none;
  background: var(--bg-secondary);
  border: none;
  padding: 4px 8px;
  font-size: 10px;
  text-transform: uppercase;
  cursor: pointer;
}
```

---

## Новый Flow

```
1. UPLOAD     → Загрузка Excel/CSV
                ↓
2. PREPARE    → Таблица с inline type selectors
                ↓
3. DESIGN     → Variable List View (Target, Factor выбор)
                ↓
4. ANALYZE    → Автовыбор тестов + кастомизация
                ↓
5. RESULTS    → Таблицы + Графики + AI
                ↓
6. EXPORT     → DOCX / PDF
```

---

## Files to Modify/Create

| Task | Files |
|------|-------|
| 7.1 | `components/DataTableWithTypes.jsx` (NEW) |
| 7.2 | `components/VariableListView.jsx` (NEW) |
| 7.3 | `components/ColumnSettingsModal.jsx` (NEW) |
| 7.4 | `index.css` updates, spacing/padding |
| Flow | `pages/DataPreparation.jsx` refactor |

---

## Success Criteria

- [ ] Таблица показывает dropdown типа под каждым заголовком
- [ ] Variable list view с карточками
- [ ] Gear icon → modal с вкладками
- [ ] Больше воздуха, меньше визуального шума
- [ ] Рабочий flow от загрузки до результатов
