import pandas as pd
import numpy as np
from app.stats.engine import run_batch_analysis

def test_batch_fdr():
    print("--- Testing Batch Analysis with FDR Correction ---")
    
    np.random.seed(42)
    n = 20
    
    data = {
        "group": ["A"]*n + ["B"]*n
    }
    
    # 1. Create Features
    # Feature 1-2: Strong Signal (Should be sig)
    data["gene_1"] = np.concatenate([np.random.normal(10, 1, n), np.random.normal(15, 1, n)])
    data["gene_2"] = np.concatenate([np.random.normal(10, 1, n), np.random.normal(14, 1, n)])
    
    # Feature 3-10: Noise (Should not be sig)
    for i in range(3, 11):
        data[f"gene_{i}"] = np.concatenate([np.random.normal(10, 2, n), np.random.normal(10, 2, n)])
        
    df = pd.DataFrame(data)
    targets = [f"gene_{i}" for i in range(1, 11)]
    
    # 2. Run Batch Analysis
    print(f"Running batch analysis for {len(targets)} targets...")
    results = run_batch_analysis(df, targets, "group", method_id="t_test_ind")
    
    # 3. Validation
    assert len(results) == 10
    
    print("\nResults:")
    for res in results:
        t = res["target"]
        p = res["p_value"]
        p_adj = res["p_value_adj"]
        sig = res["significant"]
        sig_adj = res["significant_adj"]
        print(f"{t}: P={p:.4f} -> P_Adj={p_adj:.4f} [{'Sig' if sig_adj else 'Ns'}]")
        
        # In FDR, P_Adj should be >= P
        assert p_adj >= p, f"Adjusted P ({p_adj}) < Raw P ({p}) for {t}"
        
    # Check that gene_1 is significant
    g1 = next(r for r in results if r["target"] == "gene_1")
    assert g1["significant_adj"] == True
    
    # Check that noise is not significant (likely)
    g3 = next(r for r in results if r["target"] == "gene_3")
    assert g3["significant_adj"] == False
    
    print("SUCCESS: FDR correction verified.")

if __name__ == "__main__":
    test_batch_fdr()
