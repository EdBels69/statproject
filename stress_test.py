import pandas as pd
import numpy as np
import sys
import os

# Mock the environment to load backend modules
sys.path.append(os.path.abspath('backend'))

from app.stats.engine import run_analysis
from app.stats.registry import METHODS

def generate_test_data(n=100):
    np.random.seed(42)
    data = {
        'age': np.random.normal(50, 10, n),
        'bmi': np.random.normal(25, 5, n),
        'gender': np.random.choice(['Male', 'Female'], n),
        'treatment': np.random.choice(['A', 'B', 'C'], n),
        'outcome_binary': np.random.choice([0, 1], n),
        'bp_systolic': np.random.normal(120, 15, n),
        'survival_time': np.random.exponential(50, n),
        'event': np.random.binomial(1, 0.7, n)
    }
    # Add correlation
    data['bp_systolic'] += 0.5 * data['age']
    return pd.DataFrame(data)

def run_stress_test():
    df = generate_test_data(200)
    print(f"--- Technical Stress Test (N={len(df)}) ---")
    
    tests_to_run = [
        ("t_test_ind", "bp_systolic", "gender", {}),
        ("anova", "bp_systolic", "treatment", {}),
        ("pearson", "age", "bp_systolic", {}),
        ("chi_square", "gender", "treatment", {}),
        ("survival_km", "survival_time", "event", {"group_col": "treatment"}),
        ("linear_regression", "bp_systolic", None, {"predictors": ["age", "bmi"]}),
        ("logistic_regression", "outcome_binary", None, {"predictors": ["age", "treatment"]})
    ]
    
    results_log = []
    for method, col_a, col_b, kwargs in tests_to_run:
        try:
            print(f"Testing {method}...", end=" ")
            res = run_analysis(df, method, col_a, col_b, **kwargs)
            results_log.append({"method": method, "status": "PASS", "p_val": res.get('p_value')})
            print("DONE.")
        except Exception as e:
            results_log.append({"method": method, "status": "FAIL", "error": str(e)})
            print(f"FAILED: {e}")

    print("\n--- Final Test Report ---")
    for r in results_log:
        p_str = f" (p={r['p_val']:.4f})" if 'p_val' in r else ""
        print(f"[{r['status']}] {r['method']}{p_str}")

if __name__ == "__main__":
    run_stress_test()
