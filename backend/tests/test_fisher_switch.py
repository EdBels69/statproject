import pandas as pd
import numpy as np
from app.stats.engine import run_analysis

def test_fisher_switch():
    print("--- Testing Fisher's Exact Auto-Switch ---")
    
    # 1. Create Small Sample Data (2x2)
    # Group A: 1 Yes, 9 No
    # Group B: 11 Yes, 3 No
    # Total = 24.
    # Expected for cell (0,0) approx (10*12)/24 = 5? No, let's make it smaller.
    # A: 2 Yes, 3 No. Total 5.
    # B: 1 Yes, 4 No. Total 5.
    # Total = 10.
    # Expected A-Yes = (3*5)/10 = 1.5 < 5. Should trigger Fisher.
    
    data = {
        "group": ["A"]*5 + ["B"]*5,
        "outcome": ["Yes","Yes","No","No","No"] + ["Yes","No","No","No","No"]
    }
    df = pd.DataFrame(data)
    
    # 2. Run Chi-Square (request specific method, but expect internal switch)
    print("Running chi_square with small sample...")
    res = run_analysis(df, "chi_square", "group", "outcome")
    
    print(f"Result Method ID: {res.get('method')}")
    print(f"P-Value: {res.get('p_value'):.4f}")
    print(f"Warning: {res.get('warning')}")
    
    # 3. Assertions
    # It might keep method_id as "chi_square" but warning present, OR switch method_id.
    # My implementation changes method_id to "fisher_exact".
    assert res['method'] == "fisher_exact"
    assert "Auto-switched" in res['warning']
    assert 0 <= res['p_value'] <= 1
    
    print("SUCCESS: Auto-switch to Fisher's Exact Test verified.")

if __name__ == "__main__":
    test_fisher_switch()
