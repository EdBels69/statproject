# Clinimetria — Product Vision

> **Миссия:** Сделать статистический анализ понятным для врачей и медицинских аналитиков.

---

## 🎯 Target User

**Персона:** Мария, 32 года, врач-исследователь

- **Образование:** Мед. институт, ноль курсов статистики
- **Контекст:** Пишет статью, собрала данные 50 пациентов
- **Страхи:** "Сделаю ошибку и статью отклонят"
- **Желание:** "Хочу чтобы программа сама подсказала что делать"

### Ключевые характеристики

| Аспект | Описание |
|--------|----------|
| **Мат. подготовка** | 0 — не знает что такое σ, η², df |
| **Цель** | Получить результаты для статьи |
| **Данные** | Excel таблица, 20-200 строк |
| **Время** | 30 минут на анализ |
| **Язык** | Русский |

---

## 💡 Value Proposition

### Для кого

Врачи и медицинские аналитики, которым нужно анализировать данные для научных статей.

### Проблема

- SPSS дорогой и сложный
- GraphPad не объясняет "почему этот тест"
- Jamovi не веб-приложение и не на русском
- Все инструменты предполагают что юзер знает статистику

### Решение Clinimetria

**"Умный ассистент для статистики"** — не просто калькулятор, а наставник который:

1. Сам выбирает правильный тест
2. Объясняет ПОЧЕМУ этот тест
3. Показывает ЧТО означают результаты
4. Генерирует текст для статьи

### Уникальное преимущество

```
GraphPad (не заблудишься) + Jamovi (гибко) + Образование (понимаешь)
```

---

## 🔑 Core Jobs-to-be-Done

### Job #1: Загрузить и подготовить данные
>
> "Хочу быстро загрузить Excel и увидеть что с данными"

**Что нужно:**

- Drag-and-drop загрузка
- Автоопределение типов (numeric/categorical)
- Анализ пропусков с рекомендациями
- Чистка данных (выбросы, дубликаты)
- Заполнение пропусков (mean/median/MICE)

**Success metric:** Загрузка → готово к анализу < 2 минут

### Job #2: Выбрать тест и переменные
>
> "Хочу гибко выбирать колонки как в Jamovi — перетащил, убрал, добавил"

**Что нужно:**

- Drag-and-drop переменных в роли (Target, Group)
- Мгновенный preview при изменении
- Smart recommendations ("Для ваших данных подходит...")
- Возможность сравнить несколько тестов

**Success metric:** Настройка анализа < 1 минута

### Job #3: Понять результаты
>
> "Хочу понимать что означают эти цифры, а не просто копировать их"

**Что нужно:**

- Explanation на hover (что такое p, d, η²)
- Visual scales (маленький/средний/большой эффект)
- "Для вашей статьи: ..." готовый текст
- Warnings ("Маленькая выборка", "Нарушена нормальность")

**Success metric:** Юзер может объяснить результат коллеге

### Job #4: Экспортировать для статьи
>
> "Хочу таблицу и текст готовые для вставки в Word"

**Что нужно:**

- APA/ГОСТ форматирование
- Выбор секций для отчёта
- Word/PDF экспорт
- Готовые фразы для методов

**Success metric:** Copy-paste в статью < 1 минута

---

## 📚 Education Philosophy

### Принцип: "Обучение через практику"

Не отдельные курсы, а **контекстная подсказка в момент когда нужно**.

### Три уровня глубины

| Уровень | Когда показывать | Пример для p-value |
|---------|-----------------|-------------------|
| **Junior** | По умолчанию | "p < 0.05 → результат значимый" |
| **Mid** | По клику | "p = вероятность получить такой результат если нет эффекта" |
| **Senior** | По запросу | "Не путать с P(H0&#124;data). При большом n trivial эффекты дают p < 0.05" |

### Ключевые концепции для объяснения

**Буквы:**

- t, z, F, U, H, χ² → что за статистика и зачем
- p → вероятность ошибки, НЕ вероятность гипотезы
- α, β → ошибки I и II рода
- η², d, r → размер эффекта
- μ, σ, M, SD → среднее и разброс
- df → степени свободы (сколько "свободных" наблюдений)

**Визуализации:**

- Q-Q plot → проверка нормальности
- Box plot → распределение и выбросы
- Residuals → остатки регрессии
- Forest plot → мета-анализ

**Философские вопросы:**

- Зачем effect size если есть p-value?
- Что такое "мощность" и почему 0.8?
- Почему Welch лучше Student?

---

## 🏗️ Product Principles

### 1. "Не дай заблудиться"

Система всегда показывает:

- Где ты сейчас (pipeline nav)
- Что делать дальше (recommendations)
- Что может пойти не так (warnings)

### 2. "Гибкость без хаоса"

- Drag-and-drop но с ограничениями (нельзя сравнить 2 текстовых)
- Auto-select но с возможностью override
- Defaults + Advanced options

### 3. "Объясни, не просто покажи"

Каждое число сопровождается:

- Что это (term definition)
- Хорошо/плохо (interpretation)
- Что делать (recommendation)

### 4. "Один клик до результата"

Для 80% случаев: Загрузил → Выбрал колонки → Получил отчёт

---

## 🗺️ Feature Roadmap

### MVP (сейчас) ✅

- [x] T-tests, ANOVA, Chi-square, Correlation
- [x] Effect sizes (d, η², r)
- [x] Basic visualizations
- [x] PDF/DOCX export
- [x] Education tooltips

### v1.1 (Phase 8) ⏳

- [ ] Drag-and-drop variables
- [ ] Step preview panel
- [x] Report customization ✅
- [ ] WhyThisTest integration
- [ ] FlowingData plot style

### v1.2 — Data Preparation & Smart Sorcerer 🔮

**Smart Variable Sorcerer:**

- [ ] Авто-сортировка: categorical ← | → numeric
- [ ] Группировка похожих колонок ("все про анемию")
- [ ] Детект repeated measures pattern (V1, V2, V3...)
- [ ] Wide→Long конвертер для tidy data

**Tidyverse-style Tools (Python):**

- [ ] `select()`, `filter()`, `mutate()` аналоги
- [ ] Pipe-style data transformations UI
- [ ] Унификация да/нет/ДА/НЕТ → 0/1
- [ ] Парсинг смешанных колонок

**Missing Data:**

- [ ] Pattern visualization (MCAR/MAR/MNAR)
- [ ] Little's MCAR test
- [ ] Multiple imputation (MICE)
- [ ] KNN imputation
- [ ] Sensitivity analysis (worst-case)

**Outlier & Cleaning:**

- [ ] Z-score / IQR detection
- [ ] Visual flagging
- [ ] Duplicate detection

### v1.3 — Advanced Analysis 🔮

**Regression:**

- [ ] Linear Regression (простая + множественная)
- [ ] Logistic Regression (бинарный исход)
- [ ] Ordinal Regression (шкалы)
- [ ] Residual diagnostics с объяснениями

**Agreement Studies:**

- [ ] Bland-Altman plot + analysis
- [ ] ICC (Intraclass Correlation)
- [ ] Kappa (Cohen's, Fleiss')

**Small Sample Solutions:**

- [ ] Bootstrap confidence intervals
- [ ] Permutation tests
- [ ] Exact tests (Fisher's exact)
- [ ] Warnings: "n < p — многие тесты не работают"
- [ ] Dimension reduction recommendations (PCA)

**Repeated Measures:**

- [ ] Repeated Measures ANOVA
- [ ] Mixed Models (LMM)
- [ ] GEE for longitudinal data

**Survival & Other:**

- [ ] Kaplan-Meier curves
- [ ] Log-rank test
- [ ] Sample Size Calculator

### v2.0 — Publication Ready 🔮

- [ ] Citation generator
- [ ] Journal-ready figure export
- [ ] Reproducibility report
- [ ] Collaboration (share analysis)
- [ ] Templates for common study designs

---

## 🔬 Real Data Insights (from sample files)

На основе анализа реальных датасетов (COVID 424×159, Work 44×119, IE 29×70):

| Проблема | Как часто | Решение |
|----------|-----------|---------|
| Wide format (>50 cols) | Очень часто | Smart grouping + Wide→Long |
| да/нет chaos | 100% файлов | Auto-унификация |
| n < p | Частно (Work) | Bootstrap + PCA recommendation |
| Mixed text+numbers | COVID | Парсер смешанных типов |
| Repeated measures | Work, IE | Auto-detect V1/V2/V3 pattern |

---

## 📏 Success Metrics

| Metric | Target |
|--------|--------|
| Time to first result | < 5 минут |
| Analysis completion rate | > 80% |
| User понимает p-value | > 70% (post-test) |
| Return users | > 40% в месяц |

---

## 🎨 Design Principles

| Принцип | Реализация |
|---------|-----------|
| **Минимализм** | Белый фон, один акцентный цвет |
| **Прогрессивное раскрытие** | Basic → Advanced по клику |
| **Мгновенный feedback** | Preview обновляется при каждом действии |
| **Русский язык** | Все термины на русском с английским в скобках |

---

## Как использовать этот документ

### Для разработки

1. Каждая фича проверяется против Jobs-to-be-Done
2. UI решения проверяются против Product Principles
3. Приоритеты определяются по Roadmap

### Для AI агентов (TRAE)

1. Читать User Persona перед написанием UI текстов
2. Следовать Education Philosophy в подсказках
3. Проверять что фича помогает конкретному Job

### Для принятия решений

- "Добавлять ли фичу X?" → Помогает ли она Target User с её Jobs?
- "Как реализовать Y?" → Соответствует ли Product Principles?
- "Что делать в первую очередь?" → Смотри Success Metrics

---

*Документ создан: 16 января 2026*
*Версия: 1.0*
