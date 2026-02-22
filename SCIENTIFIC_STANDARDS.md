# 🔬 SCIENTIFIC_STANDARDS.md —# Scientific Standards for Clinimetria

> Стандарты научного кода для AI-агентов и разработчиков.  
> Основано на: Python Data Science Handbook, Nathan Yau "Visualize This", de Smith "Statistical Analysis Handbook"

## 📚 Основные источники

1. **Python Data Science Handbook** (Jake VanderPlas) — NumPy, Pandas, Matplotlib best practices
2. **Visualize This** (Nathan Yau) — FlowingData принципы визуализации
3. **Statistical Analysis Handbook** (Dr. Michael J. de Smith) — методологическая строгость
   - Online: <https://www.statsref.com/>
4. **Cohen (1988)** — Effect size conventions (d = 0.2, 0.5, 0.8)
5. **APA Publication Manual (7th ed.)** — стандарты отчётности
6. **ASA Statement on p-Values (2016)** — интерпретация p-value
7. Pandas Best Practices 2024
8. SciPy / Statsmodels documentation
9. Matplotlib / Seaborn publication standards
10. **Nathan Yau "Visualize This" (FlowingData)** — см. `docs/nathan-yau-visualize-this...pdf`
11. **VISUALIZATION_STYLE_GUIDE.md** — практическое руководство по графикам

---

## 📚 Структура документа

1. [NumPy - Основа вычислений](#1-numpy)
2. [Pandas - Работа с данными](#2-pandas)
3. [Matplotlib + Seaborn - Визуализация](#3-visualization)
4. [SciPy + Statsmodels - Статистика](#4-statistics)
5. [Scikit-learn - ML и импутация](#5-machine-learning)
6. [Pingouin - Биомед статистика](#6-pingouin)

---

## 1. NumPy — Основа вычислений {#1-numpy}

### Принципы

| Принцип | Описание |
|---------|----------|
| **Vectorization** | Избегай циклов Python, используй NumPy операции |
| **Broadcasting** | Операции над массивами разных размеров |
| **Memory efficiency** | Используй правильные dtype (float32 вместо float64) |

### Код-паттерны

```python
import numpy as np

# ✅ ПРАВИЛЬНО — Vectorization
result = np.mean(data) * np.std(data)

# ❌ НЕПРАВИЛЬНО — Python цикл
total = 0
for x in data:
    total += x
mean = total / len(data)

# ✅ ПРАВИЛЬНО — Broadcasting
normalized = (data - data.mean()) / data.std()

# ✅ ПРАВИЛЬНО — Boolean indexing
valid_data = data[~np.isnan(data)]
outliers = data[np.abs(data - data.mean()) > 3 * data.std()]
```

---

## 2. Pandas — Работа с данными {#2-pandas}

### 2.1 Загрузка данных

```python
import pandas as pd

# ✅ ЛУЧШИЙ формат — Parquet (в 5-10x быстрее CSV)
df = pd.read_parquet("data.parquet", engine="pyarrow")
df.to_parquet("output.parquet", engine="pyarrow")

# CSV — если нужна совместимость
df = pd.read_csv("data.csv", 
    dtype={'group': 'category'},  # Указывай типы явно
    parse_dates=['date'],
    usecols=['id', 'value', 'group'],  # Только нужные колонки
    na_values=['NA', 'N/A', '-']  # Явные маркеры пропусков
)
```

### 2.2 Оптимизация памяти

```python
def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Оптимизация типов данных для экономии памяти.
    Экономия: 50-75% памяти.
    """
    for col in df.columns:
        col_type = df[col].dtype
        
        if col_type == 'int64':
            c_min, c_max = df[col].min(), df[col].max()
            if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                df[col] = df[col].astype(np.int8)
            elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                df[col] = df[col].astype(np.int16)
            elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                df[col] = df[col].astype(np.int32)
                
        elif col_type == 'float64':
            df[col] = df[col].astype(np.float32)
            
        elif col_type == 'object':
            if df[col].nunique() / len(df) < 0.5:  # <50% уникальных
                df[col] = df[col].astype('category')
    
    return df
```

### 2.3 Method Chaining

```python
# ✅ ПРАВИЛЬНО — Читаемый pipeline
result = (
    df
    .query("age >= 18")
    .assign(bmi=lambda x: x['weight'] / (x['height'] ** 2))
    .pipe(optimize_dataframe)
    .groupby('treatment')
    .agg({'outcome': ['mean', 'std', 'count']})
)

# ❌ НЕПРАВИЛЬНО — Куча промежуточных переменных
df1 = df[df['age'] >= 18]
df1['bmi'] = df1['weight'] / (df1['height'] ** 2)
df2 = optimize_dataframe(df1)
result = df2.groupby('treatment').agg(...)
```

### 2.4 Избегай итерации

```python
# ✅ ПРАВИЛЬНО — Vectorized
df['result'] = np.where(df['value'] > 0, 'positive', 'negative')

# ✅ ПРАВИЛЬНО — Apply только когда нужна сложная логика
df['complex_result'] = df['text'].str.extract(r'(\d+)')

# ❌ НЕПРАВИЛЬНО — iterrows (медленно!)
for idx, row in df.iterrows():
    df.at[idx, 'result'] = 'positive' if row['value'] > 0 else 'negative'
```

---

## 3. Matplotlib + Seaborn — Визуализация {#3-visualization}

### 3.1 Параметры для публикаций

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Стиль для научных публикаций
FIGURE_CONFIG = {
    # Размеры
    'figure.figsize': (7, 5),           # Дюймы
    'figure.dpi': 300,                   # Высокое разрешение
    
    # Шрифты
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    
    # Линии
    'axes.linewidth': 1.0,
    'lines.linewidth': 1.5,
    'lines.markersize': 6,
    
    # Сетка
    'axes.grid': True,
    'grid.alpha': 0.3,
    
    # Убрать лишнее
    'axes.spines.top': False,
    'axes.spines.right': False,
}

plt.rcParams.update(FIGURE_CONFIG)
sns.set_theme(style="whitegrid", palette="colorblind")
```

### 3.2 Стандартные размеры фигур

| Тип | Ширина | Высота | Использование |
|-----|--------|--------|---------------|
| Single column | 3.25" | 2.5" | Журнальная статья (1 колонка) |
| Double column | 7.0" | 5.0" | Журнальная статья (2 колонки) |
| Presentation | 10" | 6" | Слайды |
| Dashboard | Auto | Auto | Веб-интерфейс |

### 3.3 Цветовые палитры

```python
# ✅ Perceptually uniform для числовых данных
cmap_continuous = 'viridis'  # или 'plasma', 'magma'

# ✅ Diverging для данных с центром (z-scores)
cmap_diverging = 'RdBu_r'  # или 'coolwarm'

# ✅ Categorical для групп (colorblind-safe)
palette_categorical = 'colorblind'  # seaborn
# Или явно: ['#0173B2', '#DE8F05', '#029E73', '#D55E00', '#CC78BC']

# ❌ НЕ использовать
# 'jet', 'rainbow' — не perceptually uniform
# red/green вместе — проблемы для colorblind
```

### 3.4 Типы графиков по анализу

| Анализ | Основной график | Дополнительный |
|--------|-----------------|----------------|
| Сравнение групп (2) | Box + Strip plot | Violin plot |
| Сравнение групп (3+) | Box plot | Bar + Error bars |
| Корреляция | Scatter + регрессия | Heatmap матрица |
| Распределение | Histogram + KDE | QQ-plot |
| Время | Line plot + CI | Area plot |
| Выживаемость | Kaplan-Meier | Forest plot |
| ROC | ROC curve | Precision-Recall |

### 3.5 Шаблоны графиков

```python
def plot_group_comparison(df, x, y, ax=None):
    """
    Стандартный график сравнения групп.
    Box + Strip + аннотации.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(4, 4))
    
    # Box plot (без выбросов)
    sns.boxplot(data=df, x=x, y=y, ax=ax, 
                showfliers=False, width=0.5, 
                boxprops={'facecolor': 'lightblue', 'alpha': 0.7})
    
    # Точки
    sns.stripplot(data=df, x=x, y=y, ax=ax,
                  color='darkblue', alpha=0.6, size=4, jitter=True)
    
    # Убрать лишние оси
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    return ax

def plot_correlation_matrix(corr_matrix, ax=None):
    """
    Стандартная тепловая карта корреляций.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    
    # Маска для верхнего треугольника
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    
    sns.heatmap(corr_matrix, mask=mask, ax=ax,
                cmap='RdBu_r', center=0,
                vmin=-1, vmax=1,
                annot=True, fmt='.2f',
                square=True, linewidths=0.5)
    
    return ax

def plot_distribution(data, ax=None, title=None):
    """
    Распределение с гистограммой и KDE.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(5, 4))
    
    sns.histplot(data, kde=True, ax=ax, 
                 color='steelblue', edgecolor='white')
    
    # Добавить среднюю линию
    mean_val = np.nanmean(data)
    ax.axvline(mean_val, color='red', linestyle='--', 
               label=f'Mean: {mean_val:.2f}')
    
    ax.legend()
    if title:
        ax.set_title(title)
    
    return ax
```

### 3.6 Экспорт для публикаций

```python
def save_publication_figure(fig, filename, formats=['pdf', 'png', 'svg']):
    """
    Сохранить фигуру во всех нужных форматах.
    """
    for fmt in formats:
        fig.savefig(
            f"{filename}.{fmt}",
            dpi=300,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none'
        )
```

---

## 4. SciPy + Statsmodels — Статистика {#4-statistics}

### 4.1 Статистические тесты (scipy.stats)

```python
from scipy import stats

# T-тесты
t_stat, p_value = stats.ttest_ind(group1, group2)  # Independent
t_stat, p_value = stats.ttest_rel(group1, group2)  # Paired
t_stat, p_value = stats.ttest_1samp(data, popmean=0)  # One-sample

# Welch's t-test (не предполагает равные дисперсии)
t_stat, p_value = stats.ttest_ind(group1, group2, equal_var=False)

# Непараметрические
u_stat, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')
w_stat, p_value = stats.wilcoxon(group1, group2)  # Paired

# ANOVA
f_stat, p_value = stats.f_oneway(group1, group2, group3)

# Kruskal-Wallis
h_stat, p_value = stats.kruskal(group1, group2, group3)

# Корреляции
r, p_value = stats.pearsonr(x, y)
rho, p_value = stats.spearmanr(x, y)
tau, p_value = stats.kendalltau(x, y)

# Нормальность
w_stat, p_value = stats.shapiro(data)  # n < 5000
stat, p_value = stats.normaltest(data)  # D'Agostino-Pearson

# Однородность дисперсий
w_stat, p_value = stats.levene(group1, group2)
w_stat, p_value = stats.bartlett(group1, group2)  # Если нормальные

# Chi-square
chi2, p_value, dof, expected = stats.chi2_contingency(table)
```

### 4.2 Регрессии (statsmodels)

```python
import statsmodels.api as sm
import statsmodels.formula.api as smf

# Линейная регрессия с формулой
model = smf.ols('outcome ~ treatment + age + C(sex)', data=df).fit()
print(model.summary())

# Логистическая регрессия
model = smf.logit('event ~ treatment + age', data=df).fit()
odds_ratios = np.exp(model.params)

# Mixed Effects (LMM)
model = smf.mixedlm('outcome ~ time + treatment', 
                     data=df, 
                     groups=df['subject_id'],
                     re_formula='~time').fit()
```

### 4.3 Effect Sizes

| Тест | Effect Size | Интерпретация |
|------|-------------|---------------|
| t-test | Cohen's d | 0.2 малый, 0.5 средний, 0.8 большой |
| ANOVA | η² (eta-squared) | 0.01 малый, 0.06 средний, 0.14 большой |
| ANOVA | ω² (omega-squared) | Менее смещённый чем η² |
| Correlation | r | 0.1 слабый, 0.3 средний, 0.5 сильный |
| Chi-square | Cramér's V | Зависит от df |
| Odds | OR (Odds Ratio) | 1 = нет эффекта |

```python
def cohens_d(group1, group2):
    """Cohen's d с pooled SD."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    return (np.mean(group1) - np.mean(group2)) / pooled_std

def eta_squared(f_stat, df_between, df_within):
    """Eta-squared для ANOVA."""
    return (f_stat * df_between) / (f_stat * df_between + df_within)
```

---

## 5. Scikit-learn — ML и импутация {#5-machine-learning}

### 5.1 MICE Импутация

```python
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer, SimpleImputer

# MICE — множественная импутация
imputer = IterativeImputer(
    max_iter=10,
    random_state=42,
    sample_posterior=True  # Для неопределённости
)
df_imputed = pd.DataFrame(
    imputer.fit_transform(df[numeric_cols]),
    columns=numeric_cols
)

# Простая импутация
imputer = SimpleImputer(strategy='median')  # или 'mean', 'most_frequent'
```

### 5.2 Стандартизация

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

# Z-score (для нормально распределённых)
scaler = StandardScaler()

# Min-Max (для ограниченного диапазона)
scaler = MinMaxScaler()

# Robust (устойчивый к выбросам)
scaler = RobustScaler()

df[cols] = scaler.fit_transform(df[cols])
```

---

## 6. Pingouin — Биомед статистика {#6-pingouin}

**Pingouin** — библиотека для статистики с удобным API и готовыми effect sizes.

```python
import pingouin as pg

# T-test с effect size
result = pg.ttest(group1, group2, correction='auto')  # auto-Welch
# Возвращает: T, dof, p, d (Cohen's d), CI, power, BF10

# ANOVA с effect sizes
aov = pg.anova(data=df, dv='outcome', between='group')
# Возвращает: Source, SS, DF, MS, F, p-unc, np2 (partial eta²)

# Repeated measures ANOVA
rm_aov = pg.rm_anova(data=df, dv='outcome', within='time', subject='subject')

# Mixed ANOVA
mix_aov = pg.mixed_anova(data=df, dv='outcome', 
                          within='time', between='group', subject='subject')

# Корреляция с CI
result = pg.corr(x, y, method='pearson')
# Возвращает: n, r, CI95%, p, BF10, power

# Post-hoc тесты
posthoc = pg.pairwise_tukey(data=df, dv='outcome', between='group')
posthoc = pg.pairwise_tests(data=df, dv='outcome', between='group', 
                             padjust='bonf')  # bonferroni correction

# Power analysis
power = pg.power_ttest(d=0.5, n=None, power=0.8, alpha=0.05)
# Возвращает необходимый n
```

---

## 📋 Чеклист для AI-агентов

### При работе с данными

- [ ] Использовать Parquet вместо CSV
- [ ] Оптимизировать dtypes (int64→int32, category)
- [ ] Использовать method chaining
- [ ] Избегать циклов — только vectorization

### При статистике

- [ ] Всегда считать effect size
- [ ] Всегда давать 95% CI
- [ ] Проверять предположения тестов (нормальность, гомогенность)
- [ ] Использовать pingouin для удобного вывода

### При визуализации

- [ ] 300 DPI минимум
- [ ] Colorblind-safe палитры
- [ ] PDF/SVG для публикаций
- [ ] Убирать верхнюю и правую оси

### При выводе результатов

- [ ] APA-форматирование
- [ ] Интерпретация effect size
- [ ] AI-заключение простыми словами

---

*Версия: 1.0*  
*Источники: Python Data Science Handbook, SciPy docs, APA 7th*
