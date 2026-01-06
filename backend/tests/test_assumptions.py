import pandas as pd
import numpy as np
from app.stats.engine import run_analysis

def test_assumptions_logic():
    print("--- 1. Testing Perfect Data (Parametric) ---")
    np.random.seed(42)
    df_good = pd.DataFrame({
        "value": np.concatenate([np.random.normal(10, 1, 50), np.random.normal(12, 1, 50)]),
        "group": ["A"]*50 + ["B"]*50
    })
    res_good = run_analysis(df_good, "t_test_ind", "value", "group")
    print(f"Warnings: {res_good.get('warnings')}")
    assert len(res_good['warnings']) == 0, "Should have no warnings for perfect data"

    print("\n--- 2. Testing Non-Normal Data ---")
    df_bad_norm = pd.DataFrame({
        "value": np.concatenate([np.random.exponential(1, 50), np.random.exponential(1, 50)]),
        "group": ["A"]*50 + ["B"]*50
    })
    res_bad_norm = run_analysis(df_bad_norm, "t_test_ind", "value", "group")
    print(f"Warnings: {res_bad_norm.get('warnings')}")
    assert any("Normality" in w for w in res_bad_norm['warnings']), "Should warn about Normality"

    print("\n--- 3. Testing Heterogeneous Variances ---")
    df_bad_var = pd.DataFrame({
        "value": np.concatenate([np.random.normal(10, 1, 50), np.random.normal(10, 5, 50)]),
        "group": ["A"]*50 + ["B"]*50
    })
    res_bad_var = run_analysis(df_bad_var, "t_test_ind", "value", "group")
    print(f"Warnings: {res_bad_var.get('warnings')}")
    assert any("Homogeneity" in w for w in res_bad_var['warnings']), "Should warn about Homogeneity"
    
    # Check Welch recommendation in ANY warning
    assert any("Welch" in w for w in res_bad_var['warnings']), "Should recommend Welch"
    
    print("\n--- 4. Testing Welch (Should ignore Homogeneity warning) ---")
    res_welch = run_analysis(df_bad_var, "t_test_welch", "value", "group")
    # Should NOT satisfy strict_homogeneity check for 't_test_ind'/'anova' list
    # The list was ["t_test_ind", "anova"]. So 't_test_welch' should skip homogeneity warning.
    print(f"Warnings: {res_welch.get('warnings')}")
    # It might still warn about Normality (since data is Normal, it shouldn't, but let's see)
    # Normality is normal in this case.
    # Homogeneity check is only for standard tests.
    has_homo_warn = any("Homogeneity" in w for w in res_welch.get('warnings', []))
    assert not has_homo_warn, "Welch test should not warn about homogeneity"

if __name__ == "__main__":
    test_assumptions_logic()
