import pandas as pd
import numpy as np
from app.stats.engine import run_analysis

def test_roc_analysis():
    print("--- Testing ROC Analysis ---")
    
    # 1. Create Separable Data
    # Healthy (0): Mean 10
    # Disease (1): Mean 18
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        "biomarker": np.concatenate([np.random.normal(10, 2, n), np.random.normal(18, 2, n)]),
        "diagnosis": [0]*n + [1]*n
    })
    
    # 2. Run ROC
    results = run_analysis(df, "roc_analysis", "biomarker", "diagnosis")
    
    print(f"AUC: {results['auc']:.4f}")
    print(f"Best Threshold (Youden): {results['best_threshold']:.4f}")
    print(f"Sensitivity at Cut-off: {results['sensitivity']:.4f}")
    print(f"Specificity at Cut-off: {results['specificity']:.4f}")
    
    # 3. Assertions
    assert results['auc'] > 0.9, "AUC should be very high for separable data"
    assert "plot_data" in results
    assert len(results["plot_data"]) > 0
    
    # Check structure
    point = results["plot_data"][0]
    assert "x" in point and "y" in point, "Plot data must have x (FPR) and y (TPR)"
    
    print("SUCCESS: ROC Analysis Verified.")

if __name__ == "__main__":
    test_roc_analysis()
