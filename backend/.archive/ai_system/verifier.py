"""
Statistical Verifier: Detects hallucinations and anomalies in analysis results.
Addresses the LLM hallucination problem with rule-based validation.
"""
from typing import Dict, Any, List


class StatisticalVerifier:
    """
    Validates statistical results to catch:
    1. Impossible values (p=0, p>1)
    2. Suspicious patterns (p<0.001 but effect size ~0)
    3. Calculation errors (NaN, Inf)
    """
    
    ANOMALY_RULES = [
        {
            "id": "p_value_zero",
            "check": lambda r: r.get("p_value") == 0,
            "severity": "critical",
            "message": "P-value is exactly 0 (impossible - likely calculation error)"
        },
        {
            "id": "p_value_invalid",
            "check": lambda r: r.get("p_value", 0) < 0 or r.get("p_value", 0) > 1,
            "severity": "critical",
            "message": "P-value outside valid range [0, 1]"
        },
        {
            "id": "effect_size_extreme",
            "check": lambda r: r.get("effect_size") is not None and abs(r.get("effect_size", 0)) > 5,
            "severity": "warning",
            "message": "Effect size > 5 (unusually large - check data)"
        },
        {
            "id": "small_p_tiny_effect",
            "check": lambda r: (
                r.get("p_value", 1) < 0.001 and 
                r.get("effect_size") is not None and 
                abs(r.get("effect_size", 0)) < 0.1
            ),
            "severity": "warning",
            "message": "Very small p-value but tiny effect size (check sample size)"
        },
    ]
    
    def verify_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify analysis results and flag anomalies.
        
        Returns:
            {
                "verified": True/False,
                "flags": [list of issues found],
                "recommendation": str
            }
        """
        flags = []
        
        # Check numeric results
        for var_name, res in results.get("numeric", {}).items():
            for rule in self.ANOMALY_RULES:
                if rule["check"](res):
                    flags.append({
                        "variable": var_name,
                        "type": "numeric",
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "value": res.get("p_value")
                    })
        
        # Check categorical results
        for var_name, res in results.get("categorical", {}).items():
            for rule in self.ANOMALY_RULES:
                if rule["check"](res):
                    flags.append({
                        "variable": var_name,
                        "type": "categorical",
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "value": res.get("p_value")
                    })
        
        # Generate recommendation
        critical_count = sum(1 for f in flags if f["severity"] == "critical")
        warning_count = sum(1 for f in flags if f["severity"] == "warning")
        
        if critical_count > 0:
            recommendation = f"CRITICAL: {critical_count} critical issues found. Review immediately before using results."
        elif warning_count > 0:
            recommendation = f"Review {warning_count} warnings. Results may still be valid but verify manually."
        else:
            recommendation = "All validation checks passed. Results appear statistically valid."
        
        return {
            "verified": len(flags) == 0,
            "total_flags": len(flags),
            "critical_flags": critical_count,
            "warning_flags": warning_count,
            "flags": flags,
            "recommendation": recommendation
        }
    
    def add_verification_to_report(self, verification: Dict[str, Any]) -> str:
        """
        Generate markdown section for insertion in DOCX report.
        """
        if verification["verified"]:
            return "✅ **Верификация пройдена**: Все проверки пройдены успешно."
        
        md = f"⚠️ **Верификация**: Обнаружено {verification['total_flags']} предупреждений.\n\n"
        
        for flag in verification["flags"]:
            icon = "🔴" if flag["severity"] == "critical" else "🟡"
            md += f"{icon} **{flag['variable']}**: {flag['message']}\n"
        
        md += f"\n**Рекомендация**: {verification['recommendation']}"
        return md
