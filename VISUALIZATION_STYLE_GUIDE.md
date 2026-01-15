# 📊 VISUALIZATION_STYLE_GUIDE.md — Руководство по визуализации данных

> **Основано на:** Nathan Yau "Visualize This" (FlowingData)  
> **Дополнительно:** Edward Tufte, Cole Nussbaumer Knaflic, Stephen Few  
> **Применение:** StatWizard графики и отчёты

---

## 📚 Рекомендуемая литература

### В проекте (docs/)

| Книга | Файл | Ключевые главы |
|-------|------|----------------|
| **Nathan Yau — Visualize This** | `docs/nathan-yau-visualize-this...pdf` | Ch.4-8: Patterns, Proportions, Relationships, Distributions |

### Дополнительно (рекомендуется)

| Книга | Автор | Фокус |
|-------|-------|-------|
| **The Visual Display of Quantitative Information** | Edward Tufte | Data-ink ratio, chartjunk |
| **Storytelling with Data** | Cole Nussbaumer Knaflic | Narrative structure |
| **Information Dashboard Design** | Stephen Few | Dashboard UX |
| **Refactoring UI** | Adam Wathan | Practical design tips |

---

## 🎯 Принципы FlowingData (Nathan Yau)

### 1. Data-Ink Ratio

> "Every drop of ink should represent data"

**Убираем:**

- ❌ Лишние gridlines
- ❌ 3D эффекты
- ❌ Decorative borders
- ❌ Тени на графиках
- ❌ Background patterns

**Оставляем:**

- ✅ Данные
- ✅ Оси (минимальные)
- ✅ Legends (когда необходимо)
- ✅ Annotations (ключевые точки)

```python
# FlowingData style
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_linewidth(0.5)
ax.spines['bottom'].set_linewidth(0.5)
ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.3)
```

---

### 2. Выбор типа графика

**По Nathan Yau (глава 3):**

| Цель | Тип графика | Когда использовать |
|------|-------------|-------------------|
| **Сравнение групп** | Bar chart, Box plot | Categorical × Numeric |
| **Тренды во времени** | Line chart | Time series |
| **Распределение** | Histogram, Density | One numeric variable |
| **Соотношения** | Scatter plot | Two numeric variables |
| **Части целого** | Stacked bar (НЕ pie!) | Proportions |
| **Выживаемость** | Step function (Kaplan-Meier) | Survival analysis |

**⚠️ Избегай:**

- Pie charts (сложно сравнивать)
- 3D bar charts (искажают данные)
- Dual-axis charts (запутывают)

---

### 3. Цветовая палитра

**FlowingData approach:**

```python
# Основная палитра (нейтральная)
COLORS = {
    'primary': '#0f172a',     # Темный (основные данные)
    'secondary': '#64748b',   # Серый (вторичные)
    'accent': '#8b5cf6',      # Фиолетовый (выделение)
    'positive': '#10b981',    # Зелёный (significant)
    'negative': '#ef4444',    # Красный (errors)
    'neutral': '#f1f5f9',     # Светлый фон
}

# Для групп (colorblind-safe)
GROUP_COLORS = [
    '#4269d0',  # Blue
    '#ef9154',  # Orange  
    '#4ca858',  # Green
    '#db4949',  # Red
    '#8b5cf6',  # Purple
    '#14b8a6',  # Teal
]
```

**Правила:**

1. **Не более 6 цветов** на одном графике
2. **Colorblind-safe** — используй `sns.color_palette("colorblind")`
3. **Серый для контекста** — основной цвет для "фоновых" данных
4. **Акцентный цвет** — только для выделения ключевых точек

---

### 4. Typography

**Nathan Yau рекомендует:**

```python
FONT_CONFIG = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica Neue', 'Arial', 'DejaVu Sans'],
    'font.size': 10,          # Base size
    'axes.titlesize': 12,     # Title
    'axes.labelsize': 10,     # Axis labels
    'xtick.labelsize': 9,     # Tick labels
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 14,   # Suptitle
}
```

**Правила:**

1. **Один шрифт** на весь график
2. **Иерархия размеров:** Title > Labels > Ticks
3. **Никакого bold** для tick labels
4. **Italic** только для переменных (e.g., *p* = 0.001)

---

### 5. Annotations вместо легенды

**FlowingData principle:**

> "Label directly on the chart when possible"

```python
# ❌ Плохо — легенда далеко от данных
plt.legend(['Group A', 'Group B'])

# ✅ Хорошо — прямая подпись
ax.annotate('Treatment', xy=(x_treatment, y_treatment), 
            fontsize=9, color='#0f172a')
ax.annotate('Control', xy=(x_control, y_control), 
            fontsize=9, color='#64748b')
```

**Когда использовать легенду:**

- Больше 3 групп
- Линии пересекаются
- Labels не помещаются

---

## 🛠️ Практическое применение

### Box Plot + Strip Plot (для сравнения групп)

```python
import seaborn as sns
import matplotlib.pyplot as plt

def create_comparison_plot(df, x_col, y_col, title=""):
    """FlowingData-style comparison plot."""
    
    fig, ax = plt.subplots(figsize=(7, 5))
    
    # Box plot (белый, только контур)
    sns.boxplot(
        data=df, x=x_col, y=y_col,
        showfliers=False,
        boxprops={'facecolor': 'none', 'edgecolor': '#64748b'},
        whiskerprops={'color': '#64748b'},
        capprops={'color': '#64748b'},
        medianprops={'color': '#0f172a'},
        width=0.5,
        ax=ax
    )
    
    # Strip plot (точки данных)
    sns.stripplot(
        data=df, x=x_col, y=y_col,
        color='#0f172a', alpha=0.6, size=5,
        jitter=0.2, ax=ax
    )
    
    # Минималистичные оси
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)
    
    # Лёгкая сетка
    ax.yaxis.grid(True, alpha=0.2, linestyle='-', linewidth=0.3)
    ax.set_axisbelow(True)
    
    # Заголовок
    if title:
        ax.set_title(title, fontsize=12, fontweight='normal', pad=15)
    
    plt.tight_layout()
    return fig, ax
```

### Scatter Plot с регрессией (для корреляции)

```python
def create_correlation_plot(df, x_col, y_col, title=""):
    """FlowingData-style scatter with regression."""
    
    fig, ax = plt.subplots(figsize=(7, 5))
    
    # Scatter
    ax.scatter(
        df[x_col], df[y_col],
        color='#0f172a', alpha=0.5, s=40, edgecolors='none'
    )
    
    # Regression line
    from scipy.stats import linregress
    slope, intercept, r, p, se = linregress(df[x_col], df[y_col])
    x_line = np.linspace(df[x_col].min(), df[x_col].max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color='#8b5cf6', linewidth=2)
    
    # Annotation
    ax.annotate(
        f'r = {r:.2f}, p < {p:.3f}' if p < 0.05 else f'r = {r:.2f}, n.s.',
        xy=(0.05, 0.95), xycoords='axes fraction',
        fontsize=10, color='#0f172a'
    )
    
    # Минималистичные оси
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    return fig, ax
```

### Histogram (для распределения)

```python
def create_distribution_plot(data, title="", bins=30):
    """FlowingData-style histogram with density."""
    
    fig, ax = plt.subplots(figsize=(7, 4))
    
    # Histogram
    ax.hist(
        data, bins=bins, 
        color='#e2e8f0', edgecolor='#94a3b8', linewidth=0.5
    )
    
    # Density curve (KDE)
    from scipy.stats import gaussian_kde
    kde = gaussian_kde(data)
    x_range = np.linspace(data.min(), data.max(), 200)
    ax2 = ax.twinx()
    ax2.plot(x_range, kde(x_range), color='#0f172a', linewidth=1.5)
    ax2.set_yticks([])
    ax2.spines['right'].set_visible(False)
    
    # Минималистичные оси
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    return fig, ax
```

---

## 📐 Размеры и DPI

### Для экрана (web)

```python
SCREEN_CONFIG = {
    'figure.figsize': (8, 5),    # 16:10 ratio
    'figure.dpi': 100,           # Screen DPI
    'savefig.dpi': 150,          # Retina-ish
}
```

### Для публикации (PDF/Print)

```python
PUBLICATION_CONFIG = {
    'figure.figsize': (7, 5),    # Journal standard
    'figure.dpi': 300,           # Print quality
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
}
```

### Стандартные размеры (Nathan Yau рекомендует)

| Тип | Ширина | Высота | Ratio |
|-----|--------|--------|-------|
| Single column | 3.5" | 2.5" | 7:5 |
| Double column | 7" | 5" | 7:5 |
| Full page | 7" | 9" | 7:9 |
| Square | 5" | 5" | 1:1 |

---

## ✅ Чеклист перед экспортом

### Обязательно

- [ ] Убраны верхняя и правая оси
- [ ] Gridlines с alpha < 0.3
- [ ] Colorblind-safe палитра
- [ ] DPI >= 300 для публикации
- [ ] Шрифты readable (>= 9pt)
- [ ] Заголовок понятный без контекста
- [ ] Оси подписаны с единицами измерения

### Хорошо бы

- [ ] Прямые annotations вместо легенды
- [ ] Ключевые точки выделены
- [ ] Статистика на графике (p, r, CI)
- [ ] Significance brackets для групп

### Избегать

- [ ] Pie charts
- [ ] 3D эффекты
- [ ] Dual Y-axes
- [ ] Больше 6 цветов
- [ ] Decorative elements

---

## 🔗 Интеграция с plot_config.py

**Файл:** `backend/app/modules/plot_config.py`

Все настройки из этого guide уже применены в `plot_config.py`. Функция `apply_publication_config()` автоматически применяет FlowingData стиль.

```python
from app.modules.plot_config import apply_publication_config

# В начале любой функции построения графика
apply_publication_config()
fig, ax = plt.subplots()
# ... ваш код
```

---

## 📖 Дополнительные ресурсы

### Онлайн

- [FlowingData Blog](https://flowingdata.com/) — Nathan Yau's blog
- [Storytelling with Data Blog](https://www.storytellingwithdata.com/blog)
- [Datawrapper Academy](https://academy.datawrapper.de/) — Chart types guide

### Инструменты

- [ColorBrewer](https://colorbrewer2.org/) — Colorblind-safe palettes
- [Viz Palette](https://projects.susielu.com/viz-palette) — Test color accessibility
- [Chart Chooser](https://depictdatastudio.com/charts/) — Interactive guide

---

*Обновлено: 15 января 2026*  
*Основано на: Nathan Yau "Visualize This" (FlowingData)*  
*Применение: StatWizard v1.0*
