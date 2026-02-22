import pandas as pd
import numpy as np
from app.stats.engine import run_analysis

def test_welch_anova():
    print("--- Testing Welch's ANOVA (Unequal Variances) ---")
    
    # 1. Create Heteroscedastic Data
    # Group A: N=50, SD=1
    # Group B: N=50, SD=5 (Large variance)
    # Group C: N=50, SD=1
    np.random.seed(42)
    n = 50
    df = pd.DataFrame({
        "value": np.concatenate([
            np.random.normal(10, 1, n),
            np.random.normal(12, 5, n),
            np.random.normal(10, 1, n)
        ]),
        "group": ["A"]*n + ["B"]*n + ["C"]*n
    })
    
    # 2. Run Standard ANOVA (Assumes equal var)
    print("running anova...")
    res_anova = run_analysis(df, "anova", "value", "group")
    print(f"Standard ANOVA p-value: {res_anova['p_value']:.4f}")
    
    # 3. Run Welch's ANOVA
    print("running anova_welch...")
    res_welch = run_analysis(df, "anova_welch", "value", "group")
    print(f"Welch's ANOVA p-value: {res_welch['p_value']:.4f}")
    
    # 4. Assertions
    assert res_welch['method'] == "anova_welch"
    assert 0 <= res_welch['p_value'] <= 1
    
    print("SUCCESS: Welch's ANOVA executed.")

if __name__ == "__main__":
    test_welch_anova()
