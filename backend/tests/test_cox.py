import pytest
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.stats.engine import run_analysis

def test_cox_regression():
    # 1. Create Data
    # N=100
    np.random.seed(42)
    N = 100
    df = pd.DataFrame({
        "Duration": np.random.exponential(10, N),
        "Event": np.random.binomial(1, 0.7, N),
        "Age": np.random.normal(60, 10, N),
        "Sex": np.random.choice(["Male", "Female"], N),
    })
    
    # 2. Add weak effect: Older people die faster (lower duration?)
    # Just checking mechanics, not effect size accuracy strictly
    
    # 3. Run Analysis
    res = run_analysis(
        df, 
        method_id="cox_regression", 
        col_a="Duration", 
        col_b="Event", 
        predictors=["Age", "Sex"]
    )
    
    if "error" in res:
        pytest.fail(f"Cox failed: {res['error']}")
        
    print(f"Cox C-Index: {res.get('concordance_index')}")
    print(f"Coefs: {res.get('coefficients')}")
    
    # 4. Assertions
    assert "concordance_index" in res
    assert "coefficients" in res
    assert len(res["coefficients"]) >= 2 # Age + Sex_Male
    
    coef_dict = {c["variable"]: c for c in res["coefficients"]}
    
    # Check Sex_Male exists (One hot encoded)
    assert "Sex_Male" in coef_dict or "Sex_Female" in coef_dict
    assert "Age" in coef_dict
    assert res["plot_config"]["type"] == "forest"
    
    # 5. Narrative Check
    assert "narrative" in res
    print("\n[Generated Narrative]")
    print(res["narrative"])
    assert "Cox Proportional Hazards" in res["narrative"]

if __name__ == "__main__":
    test_cox_regression()
