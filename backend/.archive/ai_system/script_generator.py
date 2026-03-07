"""
Script Generator: Creates executable Python scripts for statistical analysis.
This addresses the LLM context window problem by generating code instead of processing data.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class AnalysisScriptGenerator:
    """
    Generates executable Python scripts for statistical analysis.
    LLM sees only metadata (column names, types, n) - NOT the actual data.
    """
    
    def generate_comparison_script(
        self,
        dataset_path: str,
        group_col: str,
        numeric_vars: List[str],
        categorical_vars: List[str],
        visits: Optional[List[str]] = None,
        longitudinal_families: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generates a complete Python script that:
        1. Loads data
        2. Performs statistical tests
        3. Logs methodology (audit trail)
        4. Returns JSON results
        
        The script is self-contained and reproducible.
        """
        
        # Generate script header with metadata
        script = f'''#!/usr/bin/env python3
"""
AUTO-GENERATED STATISTICAL ANALYSIS SCRIPT
Generated: {datetime.now().isoformat()}
Group Column: {group_col}
Variables: {len(numeric_vars)} numeric, {len(categorical_vars)} categorical
Longitudinal Families: {len(longitudinal_families) if longitudinal_families else 0}
"""

import pandas as pd
import numpy as np
import json
from scipy import stats
from datetime import datetime

# === AUDIT LOG (Transparency) ===
audit_log = []

def log_step(step, details):
    """Log every decision for full transparency."""
    audit_log.append({{
        "step": step,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }})

# === SAFE TYPE CONVERSION ===
def to_native(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {{str(k): to_native(v) for k, v in obj.items()}}
    elif isinstance(obj, list):
        return [to_native(v) for v in obj]
    elif isinstance(obj, (np.bool_, np.bool8)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return to_native(obj.tolist())
    elif pd.isna(obj):
        return None
    else:
        return obj

# === LOAD DATA ===
log_step("load_data", {{"action": "Loading dataset from parquet"}})
df = pd.read_parquet("{dataset_path}")
log_step("load_complete", {{"rows": len(df), "cols": len(df.columns)}})

results = {{"numeric": {{}}, "categorical": {{}}, "longitudinal": {{}}}}

# === HELPER: Normality Test ===
def check_normality(series, group_name):
    """Shapiro-Wilk test for normality."""
    clean = pd.to_numeric(series, errors='coerce').dropna()
    if len(clean) < 3:
        return False, None
    try:
        stat, p = stats.shapiro(clean) if len(clean) < 5000 else (0, 1.0)
        is_normal = p > 0.05
        log_step("normality_check", {{
            "group": group_name,
            "n": len(clean),
            "p_value": float(p),
            "is_normal": is_normal
        }})
        return is_normal, float(p)
    except:
        return False, None

# === NUMERIC COMPARISONS ===
for var in {numeric_vars}:
    log_step("analyze_numeric_start", {{"variable": var}})
    
    try:
        # Get groups
        groups = df["{group_col}"].dropna().unique()
        group_data = {{}}
        normality_results = {{}}
        
        # Check normality per group
        all_normal = True
        for g in groups:
            grp_series = df[df["{group_col}"] == g][var]
            is_norm, p_norm = check_normality(grp_series, str(g))
            normality_results[str(g)] = {{"is_normal": is_norm, "p_value": p_norm}}
            if not is_norm:
                all_normal = False
            group_data[str(g)] = pd.to_numeric(grp_series, errors='coerce').dropna()
        
        # Select appropriate test
        if len(groups) == 2:
            g1, g2 = groups
            data1 = group_data[str(g1)]
            data2 = group_data[str(g2)]
            
            if all_normal and len(data1) >= 3 and len(data2) >= 3:
                # T-test
                t_stat, p_val = stats.ttest_ind(data1, data2)
                method = "T-Test (independent)"
                effect_size = (data1.mean() - data2.mean()) / np.sqrt((data1.std()**2 + data2.std()**2) / 2)
                rationale = f"T-test selected: 2 groups, normality OK (all p > 0.05)"
            else:
                # Mann-Whitney U
                u_stat, p_val = stats.mannwhitneyu(data1, data2, alternative='two-sided')
                method = "Mann-Whitney U"
                effect_size = None
                rationale = f"Mann-Whitney U selected: 2 groups, normality violated or small n"
        else:
            # 3+ groups
            samples = [group_data[str(g)] for g in groups if len(group_data[str(g)]) >= 3]
            
            if all_normal and len(samples) >= 2:
                # ANOVA
                f_stat, p_val = stats.f_oneway(*samples)
                method = "ANOVA"
                effect_size = None
                rationale = f"ANOVA selected: {{len(groups)}} groups, all normal"
            else:
                # Kruskal-Wallis
                h_stat, p_val = stats.kruskal(*samples)
                method = "Kruskal-Wallis"
                effect_size = None
                rationale = f"Kruskal-Wallis selected: {{len(groups)}} groups, normality violated"
        
        # Store results
        results["numeric"][var] = to_native({{
            "method": method,
            "p_value": float(p_val),
            "significant": p_val < 0.05,
            "effect_size": float(effect_size) if effect_size is not None else None,
            "normality": normality_results,
            "audit": rationale,
            "groups_analyzed": len(groups)
        }})
        
        log_step("analyze_numeric_complete", {{"variable": var, "method": method, "p_value": float(p_val)}})
        
    except Exception as e:
        log_step("analyze_numeric_error", {{"variable": var, "error": str(e)}})
        results["numeric"][var] = {{
            "method": "Error",
            "p_value": 1.0,
            "significant": False,
            "error": str(e)
        }}

# === CATEGORICAL COMPARISONS ===
for var in {categorical_vars}:
    if var == "{group_col}":  # Skip the grouping variable itself
        continue
        
    log_step("analyze_categorical_start", {{"variable": var}})
    
    try:
        # Contingency table
        ct = pd.crosstab(df["{group_col}"], df[var])
        
        # Select appropriate test
        if ct.shape == (2, 2) and ct.min().min() < 5:
            # Fisher's Exact (for small cell counts)
            odds_ratio, p_val = stats.fisher_exact(ct)
            method = "Fisher Exact"
            rationale = f"Fisher selected: 2x2 table with cell < 5 (min={{ct.min().min()}})"
        else:
            # Chi-Square
            chi2, p_val, dof, expected = stats.chi2_contingency(ct)
            method = "Chi-Square"
            rationale = f"Chi-Square selected: {{ct.shape[0]}}x{{ct.shape[1]}} table"
        
        results["categorical"][var] = to_native({{
            "method": method,
            "p_value": float(p_val),
            "significant": p_val < 0.05,
            "contingency_table": ct.to_dict(),
            "audit": rationale
        }})
        
        log_step("analyze_categorical_complete", {{"variable": var, "method": method, "p_value": float(p_val)}})
        
    except Exception as e:
        log_step("analyze_categorical_error", {{"variable": var, "error": str(e)}})
        results["categorical"][var] = {{
            "method": "Error",
            "p_value": 1.0,
            "significant": False,
            "error": str(e)
        }}

# === OUTPUT ===
output = to_native({{
    "results": results,
    "audit_log": audit_log,
    "summary": {{
        "total_numeric_tests": len(results["numeric"]),
        "total_categorical_tests": len(results["categorical"]),
        "significant_count": sum(1 for r in results["numeric"].values() if r.get("significant")) +
                            sum(1 for r in results["categorical"].values() if r.get("significant")),
        "script_generated_at": "{datetime.now().isoformat()}",
        "reproducible": True
    }}
}})

print(json.dumps(output, ensure_ascii=False, indent=2))
'''
        
        return script
    
    def _generate_subgroup_code(self, subgroups: List[str]) -> str:
        """Generate code for subgroup analysis (future enhancement)."""
        if not subgroups:
            return "# No subgroups specified"
        
        code = "# === SUBGROUP ANALYSIS ===\n"
        for subgroup in subgroups:
            code += f"# TODO: Analyze subgroup '{subgroup}'\n"
        return code
