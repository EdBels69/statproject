from typing import Dict, Any, Optional

class TextGenerator:
    """
    Rule-based expert system to generate dissertation-style interpretation of statistical results.
    Mimics a human statistician's writing style.
    """
    
    @staticmethod
    def format_p_value(p: float) -> str:
        if p < 0.001:
            return "p < 0.001"
        return f"p = {p:.3f}"

    @staticmethod
    def interpret_effect_size(effect_size: float, effect_size_name: str = "cohen-d") -> str:
        if effect_size is None:
            return ""

        name = str(effect_size_name or "").lower().replace("-", "_").replace(" ", "_")
        abs_es = abs(float(effect_size))

        # Cohen's d / Hedges' g
        if name in ["cohen_d", "cohens_d", "hedges_g", "glass_delta", "d"]:
            if abs_es < 0.2: return "trivial effect"
            if abs_es < 0.5: return "small effect"
            if abs_es < 0.8: return "medium effect"
            return "large effect"

        # Eta-squared / Epsilon-squared
        if name in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2", "eps_sq", "epsilon_squared"]:
            if abs_es < 0.01: return "trivial effect"
            if abs_es < 0.06: return "small effect"
            if abs_es < 0.14: return "medium effect"
            return "large effect"

        # Correlation / RBC / Cramér's V
        if name in ["r", "pearson", "spearman", "kendall", "rbc", "rank_biserial", "cramers_v", "cramer_v", "phi", "point_biserial"]:
            if abs_es < 0.1: return "trivial effect"
            if abs_es < 0.3: return "small effect"
            if abs_es < 0.5: return "medium effect"
            return "large effect"

        # Odds Ratio
        if name in ["odds_ratio", "or"]:
            if abs_es < 1.5: return "trivial effect"
            if abs_es < 2.5: return "small effect"
            if abs_es < 4.3: return "medium effect"
            return "large effect"

        # Fallback (assume Cohen's d scale)
        if abs_es < 0.2: return "trivial effect"
        if abs_es < 0.5: return "small effect"
        if abs_es < 0.8: return "medium effect"
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
    def _method_id(results: Dict[str, Any]) -> str:
        method_obj = results.get("method")
        if hasattr(method_obj, "id"):
            return str(getattr(method_obj, "id") or "").strip().lower()
        if isinstance(method_obj, dict):
            return str(method_obj.get("id") or method_obj.get("name") or "").strip().lower()
        method_id = results.get("method_id")
        if isinstance(method_id, str) and method_id.strip():
            return method_id.strip().lower()
        return str(method_obj or "").strip().lower()

    @staticmethod
    def _method_name(results: Dict[str, Any]) -> str:
        method_obj = results.get("method")
        if hasattr(method_obj, "name"):
            return str(getattr(method_obj, "name") or getattr(method_obj, "id") or "test")
        if isinstance(method_obj, dict):
            return str(method_obj.get("name") or method_obj.get("id") or "test")
        return str(method_obj or results.get("method_id") or "test")

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _is_ru(style: str) -> bool:
        return str(style or "").strip().lower() in {"ru", "gost"}

    @staticmethod
    def interpret_result(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        return TextGenerator.generate_conclusion(results, variables, style)

    @staticmethod
    def generate_conclusion(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        method_id = TextGenerator._method_id(results)
        is_ru = TextGenerator._is_ru(style)

        # 1. Group Comparisons (Independent/Paired)
        # 1. Group Comparisons (Independent/Paired/ANOVA)
        if method_id in ["t_test_ind", "t_test_welch", "t_test_rel", "mann_whitney", "wilcoxon", "anova", "anova_welch", "kruskal"]:
            return TextGenerator._interpret_group_comparison(results, variables, style)
            
        # 1.5 One-Sample
        elif method_id == "t_test_one":
            return TextGenerator._interpret_one_sample(results, variables, style)
            
        # 2. Correlations
        elif method_id in ["pearson", "spearman", "kendall"]:
            return TextGenerator._interpret_correlation(results, variables, style)

        # 3. Categorical (Chi-Square)
        elif method_id == "chi_square":
             return TextGenerator._interpret_chi_square(results, variables, style)

        elif method_id in ["fisher", "fisher_exact"]:
            return TextGenerator._interpret_fisher(results, variables, style)
             
        # 4. Regression
        elif method_id in ["linear_regression", "logistic_regression"]:
            return TextGenerator._interpret_regression(results, variables, style)

        # 5. Survival
        elif method_id == "survival_km":
            return TextGenerator._interpret_survival(results, variables, style)
        elif method_id in {
            "bayes_t_test_ind",
            "bayes_t_test_one",
            "bayes_correlation",
            "bayes_anova",
            "bayes_chi_square",
            "bayes_linear_regression",
        }:
            return TextGenerator._interpret_bayesian(results, variables, style)
        elif method_id == "ancova":
            return TextGenerator._interpret_ancova(results, variables, style)
        elif method_id == "roc_analysis":
            return TextGenerator._interpret_roc(results, variables, style)
        elif method_id in {"shapiro_wilk", "dagostino_pearson", "anderson_darling", "kolmogorov_smirnov", "levene", "bartlett", "fligner"}:
            return TextGenerator._interpret_assumption(results, variables, style)
        elif method_id in {"pca", "efa", "kmeans", "hierarchical_clustering", "partial_correlation"}:
            return TextGenerator._interpret_multivariate(results, variables, style)

        return TextGenerator._generic_fallback(results, variables, style)

    @staticmethod
    def _interpret_regression(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        method_id = TextGenerator._method_id(results)
        p_value = TextGenerator._safe_float(results.get("p_value"))
        p_text = TextGenerator.format_p_value(p_value if p_value is not None else 1.0)
        r2 = results.get('regression', {}).get('r_squared', results.get("r_squared", results.get("pseudo_r2", 0)))
        is_ru = TextGenerator._is_ru(style)
        
        target = variables.get('target', variables.get("outcome", "Target"))
        predictors = variables.get('predictors', [])
        if isinstance(predictors, str):
            predictors = [predictors]
        if not predictors:
            candidates = variables.get("covariates")
            if isinstance(candidates, list):
                predictors = [str(x) for x in candidates if str(x).strip()]
        pred_str = ", ".join(predictors) if predictors else "predictors"

        # Linear Regression
        if method_id == "linear_regression":
            if is_ru:
                text = f"Построена линейная регрессия для прогноза {target} по предикторам: {pred_str}. "
                if results.get("significant") is True:
                    text += f"Модель статистически значима ({p_text}), R²={float(r2 or 0):.2f}."
                else:
                    text += f"Статистическая значимость модели не подтверждена ({p_text})."
                return text
            text = f"A linear regression analysis was conducted to predict {target} based on {pred_str}. "
            if results['significant']:
                text += f"A significant regression equation was found ({p_text}), with an R² of {r2:.2f}. "
                text += f"This indicates that {r2*100:.1f}% of the variance in {target} can be explained by the model."
            else:
                text += f"The regression model was not statistically significant ({p_text}). The predictors do not reliably predict {target}."
            return text

        # Logistic Regression
        if method_id == "logistic_regression":
            if is_ru:
                text = f"Проведена логистическая регрессия для оценки вероятности исхода {target} по предикторам: {pred_str}. "
                if results.get("significant") is True:
                    text += f"Модель статистически значима ({p_text}), Pseudo R²={float(r2 or 0):.2f}."
                else:
                    text += f"Статистическая значимость модели не подтверждена ({p_text})."
                return text
            text = f"A logistic regression was performed to ascertain the effects of {pred_str} on the likelihood that {target} occurs. "
            if results['significant']:
                text += f"The logistic regression model was statistically significant ({p_text}). The model explained {r2*100:.1f}% (Pseudo R²) of the variance in {target}."
            else:
                 text += f"The logistic regression model was not statistically significant ({p_text})."
            return text
        
        if is_ru:
            return f"Регрессионный анализ выполнен ({p_text})."
        return "Regression analysis completed."

    @staticmethod
    def _interpret_survival(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results.get('p_value', 1.0))
        time_col = variables.get('time', 'Time')
        event_col = variables.get('event', 'Event')
        group_col = variables.get('group', None)
        groups = results.get('groups', [])
        is_ru = TextGenerator._is_ru(style)

        if not group_col or len(groups) < 2:
            if is_ru:
                return f"Проведен анализ выживаемости Каплана-Мейера для {event_col} во времени ({time_col})."
            return f"Kaplan-Meier survival analysis was conducted for {time_col} predicting {event_col}. Survival probabilities were estimated over time."

        if is_ru:
            text = f"Проведен анализ выживаемости Каплана-Мейера (log-rank) для сравнения кривых выживаемости между группами {group_col}. "
            if results.get("significant") is True:
                text += f"Обнаружены статистически значимые различия между кривыми ({p_text})."
            else:
                text += f"Статистически значимых различий между кривыми не выявлено ({p_text})."
            return text

        text = f"A Kaplan-Meier survival analysis (Log-rank test) was conducted to compare survival distributions on {time_col} between groups defined by {group_col}. "
        
        if results['significant']:
            text += f"The survival distributions for the different interventions were significantly different ({p_text}). "
            # Try to report median survival if available (requires more data from engine, for now generic)
            text += "There is a statistically significant difference in survival times between the groups."
        else:
             text += f"The survival distributions for the different interventions were not significantly different ({p_text})."
        
        return text

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
            # Force numeric output for standard scientific reporting
            if eff_size is not None:
                if (eff_name or "").lower().replace(" ", "").replace("_", "") in ["eta2", "np2", "epssq", "etasquared", "partialeta2"]:
                     eff_text = f", effect size = {float(eff_size):.3f} ({desc})"
                elif (eff_name or "").lower().replace(" ", "") in ["rbc", "r"]:
                     eff_text = f", effect size = {float(eff_size):.2f} ({desc})"
                else:
                     eff_text = f", Cohen's d = {float(eff_size):.2f} ({desc})"
            else:
                if desc:
                    eff_text = f", {desc}"
        elif eff_size is not None:
            eff_desc = TextGenerator.interpret_effect_size(eff_size, eff_name or "cohen-d")
            if (eff_name or "").lower().replace(" ", "").replace("_", "") in ["eta2", "np2", "epssq", "etasquared", "partialeta2"]:
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
    def _interpret_one_sample(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        target = variables.get('target', 'the variable')
        test_val = results.get('extra', {}).get('test_value', 0)
        is_ru = TextGenerator._is_ru(style)
        
        plot_stats = results.get('plot_stats', {})
        stats = plot_stats.get("group", {})
        mean = stats.get("mean", 0)
        if is_ru:
            text = f"Проведен одновыборочный t-тест: проверка, отличается ли среднее {target} от {test_val}. "
            if not results.get('significant'):
                text += f"Статистически значимых отличий не выявлено (M = {mean:.2f}, {p_text})."
            else:
                direction = "выше" if mean > test_val else "ниже"
                text += f"Среднее значение {target} (M = {mean:.2f}) статистически значимо {direction}, чем {test_val} ({p_text})."
            return text

        text = f"A one-sample t-test was conducted to determine if the mean of {target} differs significantly from {test_val}. "
        
        if not results['significant']:
            text += f"No statistically significant difference was found (M = {mean:.2f}, {p_text}). The mean is statistically indistinguishable from {test_val}."
        else:
            direction = "significantly higher" if mean > test_val else "significantly lower"
            text += f"The mean of {target} (M = {mean:.2f}) was {direction} than the test value of {test_val} ({p_text})."
            
        return text

    @staticmethod
    def _interpret_correlation(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        var1 = variables.get('target', 'Variable 1')
        var2 = variables.get('predictor', variables.get("group", 'Variable 2'))
        r_val = 0
        is_ru = TextGenerator._is_ru(style)
        
        # Extract R from regression block if Pearson, or root of stat_value for others (approx)
        # Actually engine.py returns 'stat_value' as the correlation coefficient for pearson/spearman
        r_val = results.get('stat_value', 0)
        
        strength = TextGenerator.interpret_correlation_strength(r_val)
        direction = "positive" if r_val > 0 else "negative"
        method_name = TextGenerator._method_name(results).replace("_", " ")

        if is_ru:
            strength_ru = {
                "negligible": "пренебрежимо слабая",
                "weak": "слабая",
                "moderate": "умеренная",
                "strong": "сильная",
                "very strong": "очень сильная",
            }.get(strength, "неопределенная")
            direction_ru = "положительная" if r_val > 0 else "отрицательная"
            text = f"Проведен корреляционный анализ ({method_name}) между {var1} и {var2}. "
            if not results.get('significant'):
                text += f"Статистически значимой связи не выявлено ({p_text})."
                return text
            text += f"Выявлена статистически значимая {strength_ru} {direction_ru} связь (r = {r_val:.2f}, {p_text}). "
            if r_val > 0:
                text += f"При увеличении {var2} значение {var1} имеет тенденцию увеличиваться."
            else:
                text += f"При увеличении {var2} значение {var1} имеет тенденцию уменьшаться."
            return text
        
        text = f"A {method_name} analysis was performed to assess the relationship between {var1} and {var2}. "
        
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
    def _interpret_bayesian(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        method_id = TextGenerator._method_id(results)
        bf10 = TextGenerator._safe_float(results.get("bf10"))
        p_value = TextGenerator._safe_float(results.get("p_value"))
        effect = TextGenerator._safe_float(results.get("effect_size"))
        effect_name = str(results.get("effect_size_name") or "effect")
        target = variables.get("target", variables.get("outcome", "показателя" if is_ru else "outcome"))
        group = variables.get("group", variables.get("predictor", "группы" if is_ru else "group"))

        if is_ru:
            title_map = {
                "bayes_t_test_ind": "Байесовский t-тест",
                "bayes_t_test_one": "Байесовский одновыборочный t-тест",
                "bayes_correlation": "Байесовский корреляционный анализ",
                "bayes_anova": "Байесовская ANOVA",
                "bayes_chi_square": "Байесовский χ²-тест",
                "bayes_linear_regression": "Байесовская линейная регрессия",
            }
            head = title_map.get(method_id, "Байесовский анализ")
            parts = [f"{head}: {target} по фактору {group}."]
            if bf10 is not None:
                if bf10 >= 10:
                    evid = "сильное свидетельство в пользу H1"
                elif bf10 >= 3:
                    evid = "умеренное свидетельство в пользу H1"
                elif bf10 >= 1:
                    evid = "слабое свидетельство в пользу H1"
                elif bf10 >= 1 / 3:
                    evid = "слабое свидетельство в пользу H0"
                elif bf10 >= 0.1:
                    evid = "умеренное свидетельство в пользу H0"
                else:
                    evid = "сильное свидетельство в пользу H0"
                parts.append(f"BF10={bf10:.3g} ({evid}).")
            if p_value is not None:
                parts.append(f"Частотная оценка: {TextGenerator.format_p_value(p_value)}.")
            if effect is not None:
                parts.append(f"Размер эффекта: {effect_name}={effect:.3f}.")
            return " ".join(parts)

        title = method_id.replace("_", " ")
        msg = [f"Bayesian analysis ({title}) completed for {target} by {group}."]
        if bf10 is not None:
            msg.append(f"BF10={bf10:.3g}.")
        if p_value is not None:
            msg.append(f"Frequentist reference: {TextGenerator.format_p_value(p_value)}.")
        if effect is not None:
            msg.append(f"Effect size: {effect_name}={effect:.3f}.")
        return " ".join(msg)

    @staticmethod
    def _interpret_ancova(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        p_value = TextGenerator._safe_float(results.get("p_value"))
        stat = TextGenerator._safe_float(results.get("stat_value"))
        covariates = results.get("covariates")
        if isinstance(covariates, list):
            cov_s = ", ".join([str(x) for x in covariates if str(x).strip()])
        else:
            cov_s = ""
        outcome = variables.get("target", variables.get("outcome", results.get("outcome", "показателя" if is_ru else "outcome")))
        group = variables.get("group", results.get("group", "группы" if is_ru else "group"))

        p_txt = TextGenerator.format_p_value(p_value if p_value is not None else 1.0)
        stat_txt = f"F={stat:.3f}" if stat is not None else ""
        cov_txt = f" с ковариатами: {cov_s}" if cov_s else ""

        if is_ru:
            text = f"Проведен ANCOVA-анализ для {outcome} по фактору {group}{cov_txt}. "
            if results.get("significant") is True:
                text += f"После поправки на ковариаты эффект группы статистически значим ({p_txt}{', ' + stat_txt if stat_txt else ''})."
            else:
                text += f"После поправки на ковариаты статистически значимого эффекта группы не выявлено ({p_txt}{', ' + stat_txt if stat_txt else ''})."
            return text

        text = f"ANCOVA was conducted for {outcome} by {group}{cov_txt}. "
        if results.get("significant") is True:
            text += f"Group effect remained significant after covariate adjustment ({p_txt}{', ' + stat_txt if stat_txt else ''})."
        else:
            text += f"No significant adjusted group effect was detected ({p_txt}{', ' + stat_txt if stat_txt else ''})."
        return text

    @staticmethod
    def _interpret_roc(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        auc = TextGenerator._safe_float(results.get("auc"))
        sens = TextGenerator._safe_float(results.get("sensitivity"))
        spec = TextGenerator._safe_float(results.get("specificity"))
        thr = TextGenerator._safe_float(results.get("best_threshold"))
        predictor = variables.get("target", variables.get("outcome", "предиктора" if is_ru else "predictor"))
        outcome = variables.get("group", "исхода" if is_ru else "outcome")

        if is_ru:
            if auc is None:
                return f"ROC-анализ для {predictor} относительно {outcome} выполнен, но AUC недоступен."
            quality = "низкая"
            if auc >= 0.9:
                quality = "отличная"
            elif auc >= 0.8:
                quality = "очень хорошая"
            elif auc >= 0.7:
                quality = "приемлемая"
            elif auc >= 0.6:
                quality = "слабая"
            text = f"ROC-анализ: AUC={auc:.3f} ({quality} дискриминация) для {predictor} при прогнозе {outcome}."
            if thr is not None:
                text += f" Оптимальный порог={thr:.3f}"
            if sens is not None and spec is not None:
                text += f", чувствительность={sens:.3f}, специфичность={spec:.3f}."
            else:
                text += "."
            return text

        if auc is None:
            return f"ROC analysis for {predictor} vs {outcome} completed, but AUC is unavailable."
        text = f"ROC analysis: AUC={auc:.3f} for {predictor} predicting {outcome}."
        if thr is not None:
            text += f" Best threshold={thr:.3f}."
        if sens is not None and spec is not None:
            text += f" Sensitivity={sens:.3f}, specificity={spec:.3f}."
        return text

    @staticmethod
    def _interpret_assumption(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        method_id = TextGenerator._method_id(results)
        p_value = TextGenerator._safe_float(results.get("p_value"))
        stat = TextGenerator._safe_float(results.get("stat_value"))
        passed = results.get("passed")
        target = variables.get("target", variables.get("outcome", "показателя" if is_ru else "variable"))
        p_txt = TextGenerator.format_p_value(p_value if p_value is not None else 1.0)
        stat_txt = f"W={stat:.3f}" if stat is not None else ""

        if method_id in {"shapiro_wilk", "dagostino_pearson", "anderson_darling", "kolmogorov_smirnov"}:
            if is_ru:
                status = "нормальность не нарушена" if passed is True else ("нормальность нарушена" if passed is False else "статус не определен")
                return f"Проверка нормальности ({method_id}) для {target}: {status} ({p_txt}{', ' + stat_txt if stat_txt else ''})."
            status = "normality accepted" if passed is True else ("normality violated" if passed is False else "status unavailable")
            return f"Normality check ({method_id}) for {target}: {status} ({p_txt}{', ' + stat_txt if stat_txt else ''})."

        if is_ru:
            status = "однородность дисперсий подтверждена" if passed is True else ("однородность дисперсий нарушена" if passed is False else "статус не определен")
            return f"Проверка однородности дисперсий ({method_id}) для {target}: {status} ({p_txt})."
        status = "homogeneity accepted" if passed is True else ("homogeneity violated" if passed is False else "status unavailable")
        return f"Variance homogeneity check ({method_id}) for {target}: {status} ({p_txt})."

    @staticmethod
    def _interpret_multivariate(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        method_id = TextGenerator._method_id(results)
        n_obs = results.get("n_observations")
        n_vars = results.get("n_variables")

        if method_id == "partial_correlation":
            return TextGenerator._interpret_correlation(results, variables, style)

        if method_id == "pca":
            n_comp = results.get("n_components")
            var_total = TextGenerator._safe_float(results.get("explained_variance_total"))
            if is_ru:
                text = f"PCA выполнен на {n_vars or '-'} переменных (N={n_obs or '-'})"
                if n_comp is not None:
                    text += f", выделено компонент: {n_comp}"
                if var_total is not None:
                    text += f", суммарно объяснено {var_total * 100.0:.1f}% дисперсии."
                else:
                    text += "."
                return text
            text = f"PCA completed on {n_vars or '-'} variables (N={n_obs or '-'})"
            if n_comp is not None:
                text += f", components retained: {n_comp}"
            if var_total is not None:
                text += f", total explained variance: {var_total * 100.0:.1f}%."
            else:
                text += "."
            return text

        if method_id == "efa":
            n_fact = results.get("n_factors")
            if is_ru:
                return f"EFA выполнен на {n_vars or '-'} переменных (N={n_obs or '-'}), выделено факторов: {n_fact or '-'}."
            return f"EFA completed on {n_vars or '-'} variables (N={n_obs or '-'}), factors retained: {n_fact or '-'}."

        if method_id in {"kmeans", "hierarchical_clustering"}:
            n_clusters = results.get("n_clusters")
            sil = TextGenerator._safe_float(results.get("silhouette"))
            label = "k-means" if method_id == "kmeans" else "hierarchical clustering"
            if is_ru:
                text = f"Кластеризация ({label}) выполнена: N={n_obs or '-'}, переменных={n_vars or '-'}, кластеров={n_clusters or '-'}."
                if sil is not None:
                    text += f" Индекс silhouette={sil:.3f}."
                return text
            text = f"Clustering ({label}) completed: N={n_obs or '-'}, variables={n_vars or '-'}, clusters={n_clusters or '-'}."
            if sil is not None:
                text += f" Silhouette={sil:.3f}."
            return text

        return TextGenerator._generic_fallback(results, variables, style)

    @staticmethod
    def _generic_fallback(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        is_ru = TextGenerator._is_ru(style)
        method_name = TextGenerator._method_name(results).replace("_", " ")
        p_value = TextGenerator._safe_float(results.get("p_value"))
        effect = TextGenerator._safe_float(results.get("effect_size"))
        effect_name = str(results.get("effect_size_name") or "effect")
        target = variables.get("target", variables.get("outcome", results.get("target", "показатель" if is_ru else "outcome")))
        group = variables.get("group", variables.get("predictor", results.get("group", "фактор" if is_ru else "group")))
        alpha = TextGenerator._safe_float(results.get("alpha"))
        significant = results.get("significant")
        if not isinstance(significant, bool) and p_value is not None and alpha is not None:
            significant = bool(p_value < alpha)

        if is_ru:
            pieces = [f"Выполнен анализ ({method_name}) для {target} по фактору {group}."]
            if p_value is not None:
                pieces.append(f"{TextGenerator.format_p_value(p_value)}.")
            if alpha is not None and isinstance(significant, bool):
                pieces.append(
                    "H0 отклоняется." if significant else "Оснований для отклонения H0 недостаточно."
                )
            if effect is not None:
                pieces.append(f"Размер эффекта: {effect_name}={effect:.3f}.")
            return " ".join(pieces)

        pieces = [f"Analysis ({method_name}) was completed for {target} by {group}."]
        if p_value is not None:
            pieces.append(f"{TextGenerator.format_p_value(p_value)}.")
        if alpha is not None and isinstance(significant, bool):
            pieces.append("H0 rejected." if significant else "Failed to reject H0.")
        if effect is not None:
            pieces.append(f"Effect size: {effect_name}={effect:.3f}.")
        return " ".join(pieces)

    @staticmethod
    def _interpret_chi_square(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        var1 = variables.get('target', 'Variable 1')
        var2 = variables.get('group', 'Variable 2')

        eff_size = results.get('effect_size')
        eff_interp = results.get('effect_size_interpretation') if isinstance(results, dict) else None
        expected_min = results.get('expected_min')

        eff_text_ru = ""
        if isinstance(eff_interp, dict):
            desc = eff_interp.get("description_ru") or eff_interp.get("label_ru")
            if desc:
                eff_text_ru = f"; эффект: {desc}"
        elif eff_size is not None:
            try:
                eff_text_ru = f"; V = {float(eff_size):.2f}"
            except Exception:
                eff_text_ru = ""

        caution_ru = ""
        try:
            if expected_min is not None and float(expected_min) < 5:
                caution_ru = " Ожидаемые частоты в некоторых ячейках < 5; интерпретация требует осторожности."
        except Exception:
            caution_ru = ""

        if style == "ru":
            text = f"Проведен тест хи-квадрат для проверки связи между {var1} и {var2}. "
            if results['significant']:
                text += f"Связь статистически значима ({p_text}{eff_text_ru}). Это указывает на зависимость {var1} от {var2}."
            else:
                text += f"Статистически значимой связи не выявлено ({p_text}{eff_text_ru}). {var1} не демонстрирует зависимости от {var2}."
            if caution_ru:
                text += caution_ru
            return text

        eff_text = ""
        if isinstance(eff_interp, dict):
            desc = eff_interp.get("description") or eff_interp.get("label")
            if desc:
                eff_text = f", {desc}"
        elif eff_size is not None:
            try:
                eff_text = f", Cramér's V = {float(eff_size):.2f}"
            except Exception:
                eff_text = ""

        text = f"A Chi-Square test of independence was performed to examine the relation between {var1} and {var2}. "
        if results['significant']:
            text += f"The relation between these variables was significant ({p_text}{eff_text}). This suggests that {var1} is dependent on {var2}."
        else:
            text += f"The relation between these variables was not significant ({p_text}{eff_text}). {var1} appears to be independent of {var2}."
        return text

    @staticmethod
    def _interpret_fisher(results: Dict[str, Any], variables: Dict[str, str], style: str = "pro") -> str:
        p_text = TextGenerator.format_p_value(results['p_value'])
        var1 = variables.get('target', 'Variable 1')
        var2 = variables.get('group', 'Variable 2')

        odds_ratio = results.get('odds_ratio')
        eff_interp = results.get('effect_size_interpretation') if isinstance(results, dict) else None

        eff_text_ru = ""
        if isinstance(eff_interp, dict):
            desc = eff_interp.get("description_ru") or eff_interp.get("label_ru")
            if desc:
                eff_text_ru = f"; эффект: {desc}"
        elif odds_ratio is not None:
            try:
                eff_text_ru = f"; OR = {float(odds_ratio):.2f}"
            except Exception:
                eff_text_ru = ""

        if style == "ru":
            text = f"Проведен точный тест Фишера для проверки связи между {var1} и {var2}. "
            if results['significant']:
                text += f"Связь статистически значима ({p_text}{eff_text_ru})."
            else:
                text += f"Статистически значимой связи не выявлено ({p_text}{eff_text_ru})."
            return text

        eff_text = ""
        if isinstance(eff_interp, dict):
            desc = eff_interp.get("description") or eff_interp.get("label")
            if desc:
                eff_text = f", {desc}"
        elif odds_ratio is not None:
            try:
                eff_text = f", OR = {float(odds_ratio):.2f}"
            except Exception:
                eff_text = ""

        text = f"A Fisher's exact test was performed to examine the relation between {var1} and {var2}. "
        if results['significant']:
            text += f"The relation between these variables was significant ({p_text}{eff_text})."
        else:
            text += f"The relation between these variables was not significant ({p_text}{eff_text})."
        return text
