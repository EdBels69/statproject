import pytest
import pandas as pd
import numpy as np
from app.stats.engine import _handle_group_comparison, _handle_regression, _handle_anova_twoway

def test_anova_table_structure():
    # Create valid dummy data for ANOVA
    df = pd.DataFrame({
        "group": ["A"]*10 + ["B"]*10 + ["C"]*10,
        "value": np.concatenate([
            np.random.normal(10, 2, 10),
            np.random.normal(12, 2, 10),
            np.random.normal(15, 2, 10)
        ])
    })
    
    # Run ANOVA
    result = _handle_group_comparison(
        df, "anova", "value", "group", 
        kwargs={"effect_size": "eta_squared"}
    )
    
    assert "anova_table" in result
    table = result["anova_table"]
    assert isinstance(table, list)
    assert len(table) > 0
    # Check keys
    row = table[0]
    # Pingouin returns Source, SS, DF, MS, F, p-unc, np2/eta2
    assert "Source" in row
    assert "F" in row
    assert "p-unc" in row
    assert "SS" in row
    assert "DF" in row

def test_welch_anova_table():
    df = pd.DataFrame({
        "group": ["A"]*10 + ["B"]*10,
        "value": np.concatenate([np.random.normal(10, 2, 10), np.random.normal(12, 5, 10)])
    })
    result = _handle_group_comparison(
        df, "anova_welch", "value", "group", kwargs={}
    )
    assert "anova_table" in result
    assert len(result["anova_table"]) > 0
    assert "F" in result["anova_table"][0]

def test_kruskal_table():
    df = pd.DataFrame({
        "group": ["A"]*10 + ["B"]*10,
        "value": np.random.rand(20)
    })
    result = _handle_group_comparison(
        df, "kruskal", "value", "group", kwargs={}
    )
    assert "anova_table" in result
    assert "H" in result["anova_table"][0]

def test_regression_coefficients():
    df = pd.DataFrame({
        "x1": np.random.rand(50),
        "x2": np.random.rand(50),
        "y": np.random.rand(50)
    })
    
    # _handle_regression signature: df, method_id, target_col, kwargs
    # Note: kwargs must include "predictors"
    result = _handle_regression(
        df, "linear_regression", "y", None,
        kwargs={"predictors": ["x1", "x2"], "ci": True}
    )
    
    assert "coefficients" in result
    coefs = result["coefficients"]
    assert isinstance(coefs, list)
    # Intercept + x1 + x2 = 3
    # Statmodels adds intercept automatically? 
    # Usually yes for OLS if added constant. 
    # engine.py: X = sm.add_constant(X) so yes.
    assert len(coefs) >= 3 
    
    row = coefs[0]
    assert "variable" in row
    assert "coefficient" in row
    assert "std_err" in row
    assert "p_value" in row
    assert "ci_lower" in row
    assert "ci_upper" in row
    # VIF might not be in intercept or might be NaN, but key should be there if we iterate all
    # Let's check a non-intercept row if possible or just check structure
    assert "vif" in row 
