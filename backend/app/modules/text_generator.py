from typing import Dict, Any

class TextGenerator:
    """
    Rule-based expert system to generate dissertation-style interpretation of statistical results.
    Mimics a human statistician's writing style.
    """

    INTERPRETATION_TEMPLATES = {
        "t_test_one": {
            "significant": "Обнаружено статистически значимое отличие {target} от заданного значения ({method_name}, {p_display}). Среднее значение {target} = {mean1:.2f}.",
            "not_significant": "Статистически значимых отличий {target} от заданного значения не выявлено ({method_name}, {p_display})."
        },
        "t_test_ind": {
            "significant": "Выявлены статистически значимые различия между группами {group1} и {group2} ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.2f} ({effect_interpretation}). {group_higher} показала {higher_lower} значения (M = {mean1:.2f} vs M = {mean2:.2f}).",
            "not_significant": "Статистически значимых различий между группами {group1} и {group2} не выявлено ({method_name}, {p_display})."
        },
        "t_test_welch": {
            "significant": "Обнаружены статистически значимые различия между группами {group1} и {group2} ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.2f} ({effect_interpretation}).",
            "not_significant": "Статистически значимых различий между группами {group1} и {group2} не выявлено ({method_name}, {p_display})."
        },
        "t_test_rel": {
            "significant": "Выявлены статистически значимые различия между связанными условиями {group1} и {group2} ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.2f} ({effect_interpretation}).",
            "not_significant": "Статистически значимых различий между условиями {group1} и {group2} не выявлено ({method_name}, {p_display})."
        },
        "mann_whitney": {
            "significant": "Непараметрический анализ выявил значимые различия между группами {group1} и {group2} ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.2f} ({effect_interpretation}).",
            "not_significant": "Непараметрический анализ не выявил значимых различий между группами {group1} и {group2} ({method_name}, {p_display})."
        },
        "wilcoxon": {
            "significant": "Тест выявил значимые различия между условиями {group1} и {group2} ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.2f} ({effect_interpretation}).",
            "not_significant": "Тест не выявил значимых различий между условиями {group1} и {group2} ({method_name}, {p_display})."
        },
        "anova": {
            "significant": "Обнаружены статистически значимые различия по {target} между группами ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.3f} ({effect_interpretation}).",
            "not_significant": "Статистически значимых различий по {target} между группами не выявлено ({method_name}, {p_display})."
        },
        "anova_welch": {
            "significant": "Robust-анализ выявил статистически значимые различия по {target} между группами ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.3f} ({effect_interpretation}).",
            "not_significant": "Robust-анализ не выявил значимых различий по {target} между группами ({method_name}, {p_display})."
        },
        "kruskal": {
            "significant": "Непараметрический анализ выявил значимые различия по {target} между группами ({method_name}, {p_display}). Размер эффекта {effect_name} = {effect_value:.3f} ({effect_interpretation}).",
            "not_significant": "Непараметрический анализ не выявил значимых различий по {target} между группами ({method_name}, {p_display})."
        },
        "rm_anova": {
            "significant": "Выявлены статистически значимые различия во времени для {target} ({method_name}, {p_display}).",
            "not_significant": "Статистически значимых различий во времени для {target} не выявлено ({method_name}, {p_display})."
        },
        "friedman": {
            "significant": "Непараметрический анализ выявил значимые различия между условиями по {target} ({method_name}, {p_display}).",
            "not_significant": "Непараметрический анализ не выявил значимых различий между условиями по {target} ({method_name}, {p_display})."
        },
        "chi_square": {
            "significant": "Выявлена статистически значимая связь между {target} и {group} ({method_name}, {p_display}).",
            "not_significant": "Статистически значимой связи между {target} и {group} не выявлено ({method_name}, {p_display})."
        },
        "fisher": {
            "significant": "Точный тест выявил значимую связь между {target} и {group} ({method_name}, {p_display}).",
            "not_significant": "Точный тест не выявил значимой связи между {target} и {group} ({method_name}, {p_display})."
        },
        "pearson": {
            "significant": "Обнаружена статистически значимая связь между {target} и {group} (r = {r_value:.2f}, {p_display}).",
            "not_significant": "Статистически значимой связи между {target} и {group} не выявлено ({p_display})."
        },
        "spearman": {
            "significant": "Обнаружена статистически значимая связь между {target} и {group} (ρ = {r_value:.2f}, {p_display}).",
            "not_significant": "Статистически значимой связи между {target} и {group} не выявлено ({p_display})."
        },
        "clustered_correlation": {
            "significant": "Кластерный анализ выявил статистически значимую связь между переменными ({p_display}).",
            "not_significant": "Кластерный анализ не выявил статистически значимой связи между переменными ({p_display})."
        },
        "mixed_model": {
            "significant": "Смешанная модель выявила статистически значимые эффекты по {target} ({p_display}).",
            "not_significant": "Смешанная модель не выявила статистически значимых эффектов по {target} ({p_display})."
        },
        "mixed_effects": {
            "significant": "Смешанная модель выявила статистически значимые эффекты по {target} ({p_display}).",
            "not_significant": "Смешанная модель не выявила статистически значимых эффектов по {target} ({p_display})."
        },
        "survival_km": {
            "significant": "Кривые выживаемости различаются статистически значимо ({p_display}).",
            "not_significant": "Статистически значимых различий в кривых выживаемости не выявлено ({p_display})."
        },
        "linear_regression": {
            "significant": "Регрессионная модель выявила статистически значимую связь между переменными ({p_display}).",
            "not_significant": "Регрессионная модель не выявила статистически значимой связи между переменными ({p_display})."
        },
        "logistic_regression": {
            "significant": "Логистическая регрессия выявила статистически значимые предикторы ({p_display}).",
            "not_significant": "Логистическая регрессия не выявила статистически значимых предикторов ({p_display})."
        },
        "roc_analysis": {
            "significant": "ROC-анализ показал статистически значимую диагностическую точность ({p_display}).",
            "not_significant": "ROC-анализ не выявил статистически значимой диагностической точности ({p_display})."
        },
        "shapiro_wilk": {
            "significant": "Тест нормальности выявил отклонения от нормального распределения ({p_display}).",
            "not_significant": "Тест нормальности не выявил значимых отклонений от нормального распределения ({p_display})."
        },
        "levene": {
            "significant": "Тест Левена показал неоднородность дисперсий между группами ({p_display}).",
            "not_significant": "Тест Левена не выявил неоднородности дисперсий ({p_display})."
        },
        "bland_altman": {
            "significant": "Анализ Бланда–Олтмана выявил систематические различия между методами ({p_display}).",
            "not_significant": "Анализ Бланда–Олтмана не выявил статистически значимых различий между методами ({p_display})."
        },
        "icc": {
            "significant": "ICC показывает статистически значимую согласованность измерений ({p_display}).",
            "not_significant": "ICC не выявил статистически значимой согласованности измерений ({p_display})."
        },
        "cohens_kappa": {
            "significant": "Каппа Коэна показывает статистически значимое согласие между оценками ({p_display}).",
            "not_significant": "Каппа Коэна не выявила статистически значимого согласия между оценками ({p_display})."
        },
        "mcnemar": {
            "significant": "Тест Мак-Немара выявил статистически значимые изменения долей ({p_display}).",
            "not_significant": "Тест Мак-Немара не выявил статистически значимых изменений долей ({p_display})."
        },
        "cochran_q": {
            "significant": "Тест Кохрана Q выявил статистически значимые различия долей ({p_display}).",
            "not_significant": "Тест Кохрана Q не выявил статистически значимых различий долей ({p_display})."
        },
        "anova_twoway": {
            "significant": "Двухфакторный анализ выявил статистически значимые эффекты факторов по {target} ({p_display}).",
            "not_significant": "Двухфакторный анализ не выявил статистически значимых эффектов факторов по {target} ({p_display})."
        },
        "ancova": {
            "significant": "ANCOVA выявила статистически значимые различия по {target} с учетом ковариат ({p_display}).",
            "not_significant": "ANCOVA не выявила статистически значимых различий по {target} с учетом ковариат ({p_display})."
        },
        "pca": {
            "significant": "PCA выполнен для выявления латентной структуры данных.",
            "not_significant": "PCA выполнен для выявления латентной структуры данных."
        },
        "efa": {
            "significant": "EFA выполнен для выявления латентных факторов в данных.",
            "not_significant": "EFA выполнен для выявления латентных факторов в данных."
        },
        "cronbach_alpha": {
            "significant": "Расчет альфы Кронбаха показывает надежность шкалы.",
            "not_significant": "Расчет альфы Кронбаха показывает надежность шкалы."
        },
        "kmeans": {
            "significant": "Кластеризация выполнена, получены группы наблюдений.",
            "not_significant": "Кластеризация выполнена, получены группы наблюдений."
        }
    }
    
    @staticmethod
    def format_p_value(p: float) -> str:
        if p < 0.001:
            return "p < 0.001"
        if p < 0.01:
            return "p < 0.01"
        if p < 0.05:
            return "p < 0.05"
        return f"p = {p:.3f}"

    @staticmethod
    def _resolve_method_name(method_obj: Any) -> str:
        if hasattr(method_obj, "name"):
            return method_obj.name
        if isinstance(method_obj, dict):
            return method_obj.get("name") or method_obj.get("id") or "test"
        return str(method_obj).replace("_", " ")

    @staticmethod
    def _effect_label(effect_name: str) -> str:
        name = str(effect_name or "").lower().replace("-", "_").replace(" ", "_")
        if name in ["cohen_d", "cohens_d", "d"]:
            return "d"
        if name in ["hedges_g", "g"]:
            return "g"
        if name in ["glass_delta", "delta"]:
            return "Δ"
        if name in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2"]:
            return "η²"
        if name in ["eps_sq", "epsilon_squared"]:
            return "ε²"
        if name in ["r", "pearson", "spearman", "rbc"]:
            return "r"
        if name in ["cramers_v", "cramer_v"]:
            return "V"
        return name or "эффект"

    @staticmethod
    def _build_template_context(results: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
        method_name = TextGenerator._resolve_method_name(results.get("method"))
        target = variables.get("target", "переменной")
        group = variables.get("group", "группой")
        groups = results.get("groups") or []
        group1 = str(groups[0]) if len(groups) > 0 else "Группа 1"
        group2 = str(groups[1]) if len(groups) > 1 else "Группа 2"
        plot_stats = results.get("plot_stats") or {}
        m1 = float(plot_stats.get(group1, {}).get("mean", 0) or 0)
        m2 = float(plot_stats.get(group2, {}).get("mean", 0) or 0)
        if m1 >= m2:
            group_higher = group1
            higher_lower = "более высокие"
        else:
            group_higher = group2
            higher_lower = "более низкие"

        p_value = results.get("p_value")
        try:
            p_value_f = float(p_value)
            p_display = TextGenerator.format_p_value(p_value_f) if p_value_f == p_value_f else "p = н/д"
        except Exception:
            p_value_f = 1.0
            p_display = "p = н/д"

        stat_value = results.get("stat_value")
        try:
            stat_value_f = float(stat_value)
        except Exception:
            stat_value_f = 0.0

        effect_size = results.get("effect_size")
        effect_name = TextGenerator._effect_label(results.get("effect_size_name"))
        try:
            effect_value = float(effect_size)
        except Exception:
            effect_value = 0.0

        effect_interpretation = ""
        eff_interp = results.get("effect_size_interpretation")
        if isinstance(eff_interp, dict):
            effect_interpretation = eff_interp.get("description_ru") or eff_interp.get("label_ru") or ""
        if not effect_interpretation and effect_size is not None:
            effect_interpretation = TextGenerator.interpret_effect_size(effect_size, results.get("effect_size_name"))

        r_value = stat_value_f
        return {
            "method_name": method_name,
            "target": target,
            "group": group,
            "group1": group1,
            "group2": group2,
            "p_display": p_display,
            "p_value": p_value_f,
            "stat_value": stat_value_f,
            "effect_name": effect_name,
            "effect_value": effect_value,
            "effect_interpretation": effect_interpretation,
            "mean1": m1,
            "mean2": m2,
            "group_higher": group_higher,
            "higher_lower": higher_lower,
            "r_value": r_value
        }

    @staticmethod
    def _render_template(method_id: str, results: Dict[str, Any], variables: Dict[str, str]) -> str:
        templates = TextGenerator.INTERPRETATION_TEMPLATES.get(method_id)
        if not templates:
            return ""
        is_significant = bool(results.get("significant"))
        key = "significant" if is_significant else "not_significant"
        template = templates.get(key) or templates.get("default")
        if not template:
            return ""
        ctx = TextGenerator._build_template_context(results, variables)
        try:
            return template.format(**ctx)
        except Exception:
            return ""

    @staticmethod
    def interpret_effect_size(effect_size: float, effect_size_name: str = "cohen-d") -> str:
        if effect_size is None:
            return ""

        name = str(effect_size_name or "").lower().replace("-", "_").replace(" ", "_")
        abs_es = abs(float(effect_size))

        if name in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2", "eps_sq", "epsilon_squared"]:
            if abs_es < 0.01:
                return "negligible effect"
            if abs_es < 0.06:
                return "small effect"
            if abs_es < 0.14:
                return "medium effect"
            return "large effect"

        if name in ["r", "pearson", "spearman", "rbc", "rank_biserial", "rank_biserial_correlation", "cramers_v", "cramer_v"]:
            if abs_es < 0.1:
                return "negligible effect"
            if abs_es < 0.3:
                return "small effect"
            if abs_es < 0.5:
                return "medium effect"
            return "large effect"

        if abs_es < 0.2:
            return "negligible effect"
        if abs_es < 0.5:
            return "small effect"
        if abs_es < 0.8:
            return "medium effect"
        return "large effect"

    @staticmethod
    def interpret_correlation_strength(r: float) -> str:
        try:
            v = abs(float(r))
        except Exception:
            v = 0.0
        if v < 0.1:
            return "negligible"
        if v < 0.3:
            return "weak"
        if v < 0.5:
            return "moderate"
        if v < 0.7:
            return "strong"
        return "very strong"

    @staticmethod
    def interpret_result(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        return TextGenerator.generate_conclusion(results, variables, style)

    @staticmethod
    def generate_conclusion(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        method_obj = results.get("method")
        # Extract ID if method is object/dict
        if hasattr(method_obj, "id"):
            method_id = method_obj.id
        elif isinstance(method_obj, dict):
            method_id = method_obj.get("id")
        else:
            method_id = str(method_obj)

        if style == "ru":
            rendered = TextGenerator._render_template(method_id, results, variables)
            if rendered:
                return rendered
            
        # 1. Group Comparisons (Independent/Paired)
        if method_id in ["t_test_ind", "t_test_welch", "t_test_rel", "mann_whitney", "wilcoxon"]:
            return TextGenerator._interpret_group_comparison(results, variables, style)
            
        # 1.5 One-Sample
        elif method_id == "t_test_one":
            return TextGenerator._interpret_one_sample(results, variables) # Add style support later if needed
            
        # 2. Correlations
        elif method_id in ["pearson", "spearman"]:
            return TextGenerator._interpret_correlation(results, variables)

        # 3. Categorical (Chi-Square)
        elif method_id == "chi_square":
             return TextGenerator._interpret_chi_square(results, variables)
             
        return "Analysis completed."

    @staticmethod
    def _interpret_group_comparison(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        target = variables.get('target', 'the variable')
        group_col = variables.get('group', 'group')
        groups = results.get('groups', [])
        plot_stats = results.get('plot_stats', {})
        eff_size = results.get('effect_size')
        eff_interp = results.get('effect_size_interpretation') if isinstance(results, dict) else None
        eff_name = results.get('effect_size_name')
        
        # Method Name Resolution
        method_obj = results.get("method")
        if hasattr(method_obj, "name"):
            method_name = method_obj.name
        elif isinstance(method_obj, dict):
            method_name = method_obj.get("name", "test")
        else:
            method_name = str(method_obj).replace("_", " ")
        
        # Simple Style
        if style == "simple":
            if not results['significant']:
                return "No clear difference was found between the groups. They appear to be similar."
            
            # Determine winner
            if len(groups) == 2:
                 g1, g2 = groups[0], groups[1]
                 m1 = plot_stats.get(g1, {}).get('mean', 0)
                 m2 = plot_stats.get(g2, {}).get('mean', 0)
                 winner, loser = (g1, g2) if m1 > m2 else (g2, g1)
                 return f"A significant difference was found. {winner} showed higher values than {loser}."
            return "A significant difference was found between the groups."

        if style == "ru":
            eff_text = ""
            if isinstance(eff_interp, dict):
                desc = eff_interp.get("description_ru") or eff_interp.get("label_ru")
                if desc:
                    eff_text = f"; эффект: {desc}"
            elif eff_size is not None:
                try:
                    eff_text = f"; эффект: {float(eff_size):.2f}"
                except Exception:
                    eff_text = ""

            text = f"Проведен {method_name} для оценки различий {target} между группами ({group_col}). "

            if not results['significant']:
                text += f"Статистически значимых различий не выявлено ({p_text}{eff_text})."
                return text

            text += f"Обнаружены статистически значимые различия ({p_text}{eff_text}). "

            if len(groups) == 2:
                g1, g2 = groups[0], groups[1]
                m1 = plot_stats.get(g1, {}).get('mean', 0)
                m2 = plot_stats.get(g2, {}).get('mean', 0)
                direction = "выше" if m1 > m2 else "ниже"
                text += f"В частности, в группе {g1} среднее значение {target} (M = {m1:.2f}) было {direction}, чем в группе {g2} (M = {m2:.2f})."
            return text

        # Pro Style
        eff_text = ""
        if isinstance(eff_interp, dict):
            desc = eff_interp.get("description") or eff_interp.get("label")
            if desc:
                eff_text = f", {desc}"
        elif eff_size is not None:
            eff_desc = TextGenerator.interpret_effect_size(eff_size, eff_name or "cohen-d")
            if (eff_name or "").lower().replace(" ", "") in ["eta2", "np2", "eps-sq", "eps_sq", "eta_squared", "partial_eta2"]:
                eff_text = f", effect size = {float(eff_size):.3f} ({eff_desc})"
            elif (eff_name or "").lower().replace(" ", "") in ["rbc", "r"]:
                eff_text = f", effect size = {float(eff_size):.2f} ({eff_desc})"
            else:
                eff_text = f", Cohen's d = {float(eff_size):.2f} ({eff_desc})"
            
        text = f"An independent {method_name} was conducted to determine if there were differences in {target} between groups defined by {group_col}. "
        
        if not results['significant']:
            text += f"The analysis revealed no statistically significant difference between the groups ({p_text}{eff_text}). "
            return text
            
        # Significant
        text += f"There was a statistically significant difference between the groups ({p_text}{eff_text}). "
        
        if len(groups) == 2:
             g1, g2 = groups[0], groups[1]
             m1 = plot_stats.get(g1, {}).get('mean', 0)
             m2 = plot_stats.get(g2, {}).get('mean', 0)
             direction = "higher" if m1 > m2 else "lower"
             text += f"Specifically, the {target} in the {g1} group (M = {m1:.2f}) was significantly {direction} than in the {g2} group (M = {m2:.2f}). "
             
        return text

    @staticmethod
    def _interpret_one_sample(results: Dict[str, Any], variables: Dict[str, str]) -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        target = variables.get('target', 'the variable')
        test_val = results.get('extra', {}).get('test_value', 0)
        
        plot_stats = results.get('plot_stats', {})
        stats = plot_stats.get("group", {})
        mean = stats.get("mean", 0)
        
        text = f"A one-sample t-test was conducted to determine if the mean of {target} differs significantly from {test_val}. "
        
        if not results['significant']:
            text += f"No statistically significant difference was found (M = {mean:.2f}, {p_text}). The mean is statistically indistinguishable from {test_val}."
        else:
            direction = "significantly higher" if mean > test_val else "significantly lower"
            text += f"The mean of {target} (M = {mean:.2f}) was {direction} than the test value of {test_val} ({p_text})."
            
        return text

    @staticmethod
    def interpret_correlation_strength(r: float) -> str:
        """Interpret correlation coefficient magnitude (Cohen 1988)."""
        ar = abs(r) if r is not None else 0
        if ar < 0.10:
            return "negligible"
        elif ar < 0.30:
            return "weak"
        elif ar < 0.50:
            return "moderate"
        elif ar < 0.70:
            return "strong"
        else:
            return "very strong"

    @staticmethod
    def _interpret_correlation(results: Dict[str, Any], variables: Dict[str, str]) -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        var1 = variables.get('target', 'Variable 1')
        var2 = variables.get('predictor', 'Variable 2')
        r_val = 0
        
        # Extract R from regression block if Pearson, or root of stat_value for others (approx)
        # Actually engine.py returns 'stat_value' as the correlation coefficient for pearson/spearman
        r_val = results.get('stat_value', 0)
        
        strength = TextGenerator.interpret_correlation_strength(r_val)
        direction = "positive" if r_val > 0 else "negative"
        
        text = f"A {results.get('method')} analysis was performed to assess the relationship between {var1} and {var2}. "
        
        if not results['significant']:
             text += f"The relationship was not statistically significant ({p_text}). There is insufficient evidence to conclude that these variables are associated."
             return text
             
        text += f"There was a statistically significant, {strength} {direction} correlation between {var1} and {var2} (r = {r_val:.2f}, {p_text}). "
        
        if direction == "positive":
            text += f"This indicates that as {var2} increases, {var1} tends to increase."
        else:
            text += f"This indicates that as {var2} increases, {var1} tends to decrease."
            
        return text

    @staticmethod
    def _interpret_chi_square(results: Dict[str, Any], variables: Dict[str, str]) -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        var1 = variables.get('target', 'Variable 1')
        var2 = variables.get('group', 'Variable 2')
        
        text = f"A Chi-Square test of independence was performed to examine the relation between {var1} and {var2}. "
        
        if results['significant']:
            text += f"The relation between these variables was significant ({p_text}). This suggests that {var1} is dependent on {var2}."
        else:
            text += f"The relation between these variables was not significant ({p_text}). {var1} appears to be independent of {var2}."
            
        return text
