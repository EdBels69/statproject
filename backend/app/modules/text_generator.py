from typing import Dict, Any

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
