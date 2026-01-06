# SYSTEM PROMPT: STAT TECH REDESIGN (LIGHT SAAS STYLE)
**Context:** Implementation of Branch `feature/stattech-redesign`
**Visual Reference:** Roo Code Cloud / z.ai (Light Mode)
**Paradigm:** Clean, Airy, Data-First, Enterprise Ready.

---

## 1. DESIGN TOKENS (THE SOURCE OF TRUTH)
*Жестко зафиксированные переменные. Никаких отступлений.*

**Color Palette (Light / Airy):**
*   **Background (App):** `#FFFFFF` (Pure White) — создаем ощущение чистоты.
*   **Background (Secondary/Sidebar):** `#F9FAFB` (Gray-50) — легкий оттенок для отделения зон.
*   **Border / Separator:** `#E5E7EB` (Gray-200) — тонкие, едва заметные границы.
*   **Text Primary:** `#111827` (Gray-900) — максимальный контраст для заголовков и ключевых данных.
*   **Text Secondary:** `#6B7280` (Gray-500) — для описаний, лейблов, метаданных.
*   **Accent (Primary Action):** `#2563EB` (Royal Blue) — кнопки, активные состояния, ключевые инсайты. (При ховере: `#1D4ED8`).
*   **Accent (Success):** `#10B981` (Emerald) — для успешных расчетов.
*   **Accent (Error):** `#EF4444` (Red) — только для системных ошибок.

**Typography:**
*   **Font Family:** `Inter`, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif.
*   **Font Weights:**
    *   Headers: `600` (SemiBold).
    *   Body: `400` (Regular).
    *   Data/Numbers: `500` (Medium) — чтобы цифры «держали» линию.
*   **Numbers:** `font-variant-numeric: tabular-nums;` — **Обязательно**.

**Spacing (Grid System):**
*   Базовая единица: `4px`.
*   Отступы между блоками: `16px` (small), `24px` (medium), `32px` (large).
*   Padding внутри карточек: `24px`.
*   Border Radius: `8px` или `12px` (Modern, friendly but strict).

**Shadows (Soft Depth):**
*   Small (Inputs/Cards): `0 1px 2px 0 rgba(0, 0, 0, 0.05)`
*   Medium (Floating panels): `0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)`
*   *No heavy black shadows.* Только легкая диффузия.

---

## 2. LAYOUT ARCHITECTURE
*Структура страницы в стиле z.ai / Roo Code.*

**Grid Template:**
```css
display: grid;
grid-template-columns: 260px 1fr; /* Sidebar | Main Content */
min-height: 100vh;
```

*   **Left Sidebar (Navigation):**
    *   Background: `#FFFFFF`.
    *   Border-right: `1px solid #E5E7EB`.
    *   Содержит: Логотип, Меню инструментов, Настройки профиля (снизу).
    *   Стиль ссылок: Текстовые, без фона. Активная ссылка — синий цвет текста + легкий синий фон (`#EFF6FF`) слева.

*   **Main Content Area:**
    *   Background: `#F9FAFB` (или белый, если предпочитается "чистый лист").
    *   Padding: `32px`.
    *   Max-width контейнера: `1200px` (центрирование по середине).

---

## 3. COMPONENT LIBRARY (SPECIFICATIONS)

### 3.1. The "Card" Component
*Это основной строительный блок.*
*   **Visual:** Белый фон (`#FFFFFF`), граница `1px solid #E5E7EB`, скругление `12px`, легкая тень.
*   **Header:** Заголовок слева, кнопка действия (иконка) справа. Разделитель `1px solid #E5E7EB` под хедером.
*   **Body:** Padding `24px`.

### 3.2. Inputs & Forms
*   **Style:** "Clean Input". Без границ по умолчанию, только легкий серый фон (`#F3F4F6`) и нижняя граница.
*   **Focus State:** Фон становится белым, нижняя граница окрашивается в `#2563EB` (Royal Blue). Появляется легкое свечение (ring).
*   **Labels:** Маленький серый текст (`text-xs`, `text-gray-500`) над полем ввода.

### 3.3. Buttons
*   **Primary:** Фон `#2563EB`, текст белый. Скругление `6px`. Padding: `8px 16px`. Hover: затемнение на 10%.
*   **Secondary:** Фон прозрачный, граница `1px solid #D1D5DB`, текст серый. Hover: фон `#F3F4F6`.
*   **Ghost:** Текст серый. Hover: фон `#F3F4F4`.

### 3.4. Data Tables
*   **Header:** Фон `#F9FAFB`, текст `text-xs`, `font-semibold`, `text-gray-500`, uppercase.
*   **Rows:** Белый фон. Граница между строками `1px solid #F3F4F6`.
*   **Hover:** Эффект "подсветки строки" (`bg-gray-50`), чтобы следить за глазами.

---

## 4. STATISTICS & VISUALIZATION LAYER
*Специфика для Stat Tech.*

1.  **Charts (Graphs):**
    *   Стиль: Минимализм.
    *   Сетка осей: Пунктирные линии, очень светлый серый (`#E5E7EB`).
    *   Линии графиков: Толщина `2px` или `3px`. Цвета: Использовать палитру Tailwind (Blue, Emerald, Violet, Amber).
    *   Тултипы (Hover): Белый квадрат с черной текстом и тенью (`shadow-lg`). Закругление `4px`.

2.  **Math Formulas:**
    *   Рендеринг через MathJax/KaTeX.
    *   Шрифт формул: Serif (Times New Roman или Computer Modern).
    *   Размер: Немного крупнее основного текста для читаемости.

3.  **Results Display:**
    *   **Big Numbers:** Крупный размер шрифта (`text-3xl`), жирный (`font-bold`), цвет `#111827`. Использовать для ключевых метрик (p-value, R-squared).
