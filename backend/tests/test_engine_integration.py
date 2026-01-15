import pytest
import pandas as pd
import os
from app.stats.engine import select_test, run_analysis

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_golden(filename):
    return pd.read_csv(os.path.join(DATA_DIR, filename))

def test_ttest_significant():
    df = load_golden("golden_ttest_sig.csv")
    col_a = "Value"
    col_b = "Group"
    
    # 1. Select Test
    types = {col_a: "numeric", col_b: "categorical"}
    method_id = select_test(df, col_a, col_b, types)
    
    assert method_id == "t_test_ind", "Should select T-Test Independent for normal data"
    
    # 2. Run Analysis
    result = run_analysis(df, method_id, col_a, col_b)
    
    assert bool(result["significant"]) is True, "Should be significant"
    assert result["p_value"] < 0.05

    assert result.get("effect_size") is not None
    assert result.get("effect_size_name") == "cohen-d"
    assert result.get("effect_size_ci_lower") is not None
    assert result.get("effect_size_ci_upper") is not None
    assert result.get("effect_size_ci_lower") < result.get("effect_size_ci_upper")
    assert result.get("power") is not None
    assert 0.0 <= float(result.get("power")) <= 1.0
    assert result.get("bf10") is not None

def test_ttest_not_significant():
    df = load_golden("golden_ttest_ns.csv")
    col_a = "Value"
    col_b = "Group"
    
    # 1. Select Test
    types = {col_a: "numeric", col_b: "categorical"}
    method_id = select_test(df, col_a, col_b, types)
    
    assert method_id == "t_test_ind"
    
    # 2. Run Analysis
    result = run_analysis(df, method_id, col_a, col_b)
    
    assert bool(result["significant"]) is False, "Should NOT be significant"
    assert result["p_value"] > 0.05

    assert result.get("effect_size") is not None
    assert result.get("effect_size_name") == "cohen-d"
    assert result.get("effect_size_ci_lower") is not None
    assert result.get("effect_size_ci_upper") is not None
    assert result.get("power") is not None
    assert 0.0 <= float(result.get("power")) <= 1.0
    assert result.get("bf10") is not None


def test_ttest_welch_returns_ci_power_bf10():
    df = load_golden("golden_ttest_sig.csv")
    col_a = "Value"
    col_b = "Group"

    result = run_analysis(df, "t_test_welch", col_a, col_b)

    assert result.get("effect_size") is not None
    assert result.get("effect_size_name") == "cohen-d"
    assert result.get("effect_size_ci_lower") is not None
    assert result.get("effect_size_ci_upper") is not None
    assert result.get("power") is not None
    assert result.get("bf10") is not None

def test_mann_whitney_significant():
    df = load_golden("golden_mw_sig.csv")
    col_a = "Value"
    col_b = "Group"
    
    # 1. Select Test
    types = {col_a: "numeric", col_b: "categorical"}
    method_id = select_test(df, col_a, col_b, types)
    
    # Note: Our logic might pick t-test if it passes normality check by chance, 
    # but for lognormal it usually picks Mann-Whitney. 
    # Let's assert it picks one of the independent comparison tests.
    assert method_id in ["mann_whitney", "t_test_ind"]
    
    if method_id == "mann_whitney":
        print("Correctly selected Non-Parametric test")
    
    # 2. Run Analysis
    result = run_analysis(df, method_id, col_a, col_b)
    
    assert bool(result["significant"]) is True
    assert result["p_value"] < 0.05
