from typing import Dict, Any

class NarrativeGenerator:
    """
    Generates human-readable interpretation of statistical results.
    Mimics 'scientific writing' style.
    """
    
    def generate_narrative(self, result: Dict[str, Any]) -> str:
        method_id = result.get("method", {}).get("id") if isinstance(result.get("method"), dict) else result.get("method")
        
        # Handle simple string method ID or object
        if not method_id and "method" in result and isinstance(result["method"], str):
             method_id = result["method"]
             
        if not method_id:
            return "Analysis complete."
            
        if method_id in ["t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon"]:
            return self._describe_two_group(result)
        elif method_id in ["anova", "anova_welch", "kruskal"]:
            return self._describe_anova(result)
        elif method_id in ["pearson", "spearman"]:
            return self._describe_correlation(result)
        elif method_id in ["chi_square", "fisher"]:
            return self._describe_chi_square(result)
        elif method_id == "cox_regression":
            return self._describe_cox(result)
        elif method_id == "roc_analysis":
            return self._describe_roc(result)
            
        return "Statistical analysis completed."

    def _format_p(self, p: float) -> str:
        if p < 0.001: return "p < 0.001"
        return f"p = {p:.3f}"

    def _describe_two_group(self, res: Dict) -> str:
        significant = res.get("significant", False)
        p_val = res.get("p_value", 1.0)
        stat_name = "Statistic"
        if "t_test" in str(res.get("method")): stat_name = "t"
        elif "mann" in str(res.get("method")): stat_name = "U"
        elif "wilcoxon" in str(res.get("method")): stat_name = "W"
        
        stat_val = res.get("stat_value", 0)
        
        # Build Group Stats Text
        group_text = ""
        groups = res.get("groups", [])
        if len(groups) == 2:
            g1 = groups[0]
            g2 = groups[1]
            group_text = (
                f" Сравнивались группа '{g1['name']}' (M={g1['mean']:.2f}, SD={g1['std']:.2f}) "
                f"и группа '{g2['name']}' (M={g2['mean']:.2f}, SD={g2['std']:.2f})."
            )
        
        sig_text = "статистически значимые различия" if significant else "различий не выявлено"
        direction = ""
        
        if significant and len(groups) == 2:
            if groups[0]['mean'] > groups[1]['mean']:
                direction = f" Среднее значение в группе '{groups[0]['name']}' было значимо выше."
            else:
                direction = f" Среднее значение в группе '{groups[1]['name']}' было значимо выше."
        
        method_name = str(res.get('method', 'comparison'))
        return (
            f"Был проведен анализ методом '{method_name}'. "
            f"Результат: {sig_text} ({stat_name}={stat_val:.2f}, {self._format_p(p_val)})."
            f"{group_text}{direction}"
        )

    def _describe_anova(self, res: Dict) -> str:
        significant = res.get("significant", False)
        p_val = res.get("p_value", 1.0)
        stat = res.get("stat_value", 0)
        
        sig_text = "выявил статистически значимые различия" if significant else "не показал значимых различий"
        
        text = f"Дисперсионный анализ (ANOVA) {sig_text} между группами (F={stat:.2f}, {self._format_p(p_val)})."
        
        if significant:
             text += " Рекомендуется провести апостериорные (post-hoc) сравнения."
             
        return text

    def _describe_correlation(self, res: Dict) -> str:
        r = res.get("stat_value", 0)
        p = res.get("p_value", 1.0)
        
        strength = "очень слабая"
        abs_r = abs(r)
        if abs_r > 0.9: strength = "очень сильная"
        elif abs_r > 0.7: strength = "сильная"
        elif abs_r > 0.5: strength = "заметная"
        elif abs_r > 0.3: strength = "умеренная"
        elif abs_r > 0.1: strength = "слабая"
        
        direction = "положительная" if r > 0 else "отрицательная"
        sig_text = "значима" if p < 0.05 else "не значима"
        
        return (
            f"Наблюдается {strength} {direction} корреляция (r={r:.2f}). "
            f"Связь статистически {sig_text} ({self._format_p(p)})."
        )

    def _describe_chi_square(self, res: Dict) -> str:
        p = res.get("p_value", 1.0)
        chi2 = res.get("stat_value", 0)
        significant = res.get("significant", False)
        
        relation = "статистически значимая связь" if significant else "связь отсутствует"
        
        return (
            f"Анализ таблицы сопряженности (Хи-квадрат) показал, что {relation} "
            f"(Chi2={chi2:.2f}, {self._format_p(p)})."
        )

    def _describe_cox(self, res: Dict) -> str:
        p = res.get("p_value", 1.0)
        c_index = res.get("concordance_index", 0.5)
        coefs = res.get("coefficients", [])
        
        sig_preds = [c for c in coefs if c.get("significant")]
        
        text = (
            f"Построена модель пропорциональных рисков Кокса. "
            f"Индекс конкордации (C-index) модели составил {c_index:.2f}. "
            f"Общий P-value модели: {self._format_p(p)}."
        )
        
        if sig_preds:
            names = ", ".join([c["variable"] for c in sig_preds])
            text += f" Выявлены значимые предикторы: {names}."
            
            # Detail for first significant predictor
            best = sig_preds[0]
            hr = best.get("hazard_ratio")
            impact = "повышает" if hr > 1 else "снижает"
            text += f" В частности, {best['variable']} {impact} риск наступления события (HR={hr:.2f})."
        else:
            text += " Значимых предикторов (p<0.05) не выявлено."
            
        return text

    def _describe_roc(self, res: Dict) -> str:
        auc = res.get("auc", 0.5)
        ci_lower = res.get("auc_ci_lower", 0.0)
        ci_upper = res.get("auc_ci_upper", 1.0)
        p = res.get("p_value", 1.0)
        
        cut_off = res.get("best_threshold")
        sens = res.get("sensitivity", 0)
        spec = res.get("specificity", 0)
        
        quality = "неудовлетворительное"
        if auc > 0.9: quality = "отличное"
        elif auc > 0.8: quality = "очень хорошее"
        elif auc > 0.7: quality = "хорошее"
        elif auc > 0.6: quality = "среднее"
        
        text = (
            f"Выполнен ROC-анализ. Площадь под ROC-кривой (AUC) составила {auc:.3f} "
            f"(95% ДИ: {ci_lower:.3f}-{ci_upper:.3f}), что классифицируется как {quality} качество модели. "
            f"Различие с AUC=0.5 статистически { 'значимо' if p < 0.05 else 'не значимо' } ({self._format_p(p)})."
        )
        
        if cut_off is not None:
            text += (
                f" Оптимальный порог отсечения (Youden's index method) составил {cut_off:.2f}. "
                f"При данном пороге: Чувствительность = {sens:.1%}, Специфичность = {spec:.1%}."
            )
            
        return text
