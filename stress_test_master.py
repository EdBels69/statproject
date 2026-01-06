import sys
import pandas as pd
import numpy as np
import warnings

# Suppress warnings for cleaner log
warnings.filterwarnings("ignore")

# Setup Backend Path
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.stats.engine import _handle_regression, _handle_survival, _handle_correlation_matrix, run_analysis

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_regression_edge_cases():
    log("Testing Regression Edge Cases...")
    n = 100
    
    # 1. Singular Matrix (Perfect Multicollinearity)
    # X2 is exactly 2*X1
    df_singular = pd.DataFrame({
        "Y": np.random.normal(0,1,n),
        "X1": np.random.normal(0,1,n),
        "X2": np.random.normal(0,1,n)
    })
    df_singular["X3"] = df_singular["X1"] * 2 # Perfect correlation
    
    res = _handle_regression(df_singular, "Y", ["X1", "X3"], "ols")
    if "error" in res:
        log(f"Singular Matrix Handling: OK (Caught: {res['error']})", "PASS")
    else:
        # Statsmodels might handle it by dropping col or returning NaNs. 
        # If it returns result, check if Coefs are NaNs or huge?
        log(f"Singular Matrix Handling: WARNING (Result returned: {res.keys()})", "WARN")

    # 2. Zero Variance Predictor (Constant)
    df_const = pd.DataFrame({
        "Y": np.random.normal(0,1,n),
        "X1": np.random.normal(0,1,n),
        "Const": [5]*n
    })
    res = _handle_regression(df_const, "Y", ["X1", "Const"], "ols")
    # Should likely drop Const or handle it
    vals = [r['coef'] for r in res.get('coef_table', []) if r['variable'] == 'Const']
    if "error" in res or (vals and np.isnan(vals[0])):
         log(f"Constant Predictor Handling: OK", "PASS")
    else:
         log(f"Constant Predictor Handling: Unknown (Result: {vals})", "INFO")

def test_anova_high_cardinality():
    log("Testing ANOVA High Cardinality...")
    # 500 groups, 2 obs each
    n_groups = 200 # Post-hoc Tukey is O(N^2) or similar
    df = pd.DataFrame({
        "Val": np.random.normal(0,1, n_groups*3),
        "Group": np.repeat([f"G{i}" for i in range(n_groups)], 3)
    })
    
    try:
        import time
        start = time.time()
        res = run_analysis(df, "anova", "Val", "Group")
        dur = time.time() - start
        
        if "error" in res:
             log(f"High Cardinality ANOVA Failed: {res['error']}", "FAIL")
        else:
             n_posthoc = len(res.get("post_hoc", []))
             log(f"High Cardinality ANOVA: OK ({dur:.2f}s). Generated {n_posthoc} post-hoc comparisons.", "PASS")
             
    except Exception as e:
        log(f"High Cardinality Crash: {e}", "FAIL")

def test_survival_edge_cases():
    log("Testing Survival Edge Cases...")
    n = 50
    
    # 1. No Events (All censored)
    df_censored = pd.DataFrame({
        "Time": np.random.exponential(10, n),
        "Event": [0]*n # No events
    })
    res = _handle_survival(df_censored, "Time", "Event")
    if "error" in res:
         log(f"All Censored Failed: {res['error']}", "FAIL")
    else:
         med = res.get("median_survival", {}).get("Overall")
         if med == "Not Reached" or np.isinf(med):
              log("All Censored: OK (Median Not Reached)", "PASS")
         else:
              log(f"All Censored: Unexpected Median {med}", "WARN")

    # 2. Constant Time (t=0 for all)
    df_zero = pd.DataFrame({
        "Time": [0]*n,
        "Event": np.random.binomial(1, 0.5, n)
    })
    res = _handle_survival(df_zero, "Time", "Event")
    if "error" in res:
        log(f"Zero Time Handling: FAIL ({res['error']})", "FAIL")
    else:
        log("Zero Time Handling: OK (Handled)", "PASS")

def test_correlation_edge_cases():
    log("Testing Correlation Edge Cases...")
    n = 50
    # 1. Constant Column (Std=0 -> Correlation undefined)
    df = pd.DataFrame({
        "A": np.random.normal(0,1,n),
        "B": [10]*n
    })
    res = _handle_correlation_matrix(df, ["A", "B"], "pearson")
    
    # Pearsonr usually throws specific warning or returns NaN
    cm = res.get("corr_matrix")
    if cm:
        val = cm["A"].get("B")
        if np.isnan(val):
             log("Zero Variance Correlation: OK (NaN)", "PASS")
        else:
             log(f"Zero Variance Correlation: FAIL (Got {val})", "FAIL")

if __name__ == "__main__":
    print("=== START STRESS TEST ===")
    test_regression_edge_cases()
    test_anova_high_cardinality()
    test_survival_edge_cases()
    test_correlation_edge_cases()
    print("=== END STRESS TEST ===")
