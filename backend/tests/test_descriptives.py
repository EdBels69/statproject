
import pandas as pd
import numpy as np
import warnings
from app.stats.engine import compute_descriptive_compare

def test_descriptives_cv_geometric_mean():
    # Create synthetic data
    # Group A: Normal distribution, Mean=10, SD=2 -> CV=20%
    np.random.seed(42)
    group_a = np.random.normal(10, 2, 100)
    
    # Group B: Log-normal (for geometric mean)
    group_b = np.random.lognormal(mean=2, sigma=0.5, size=100)
    
    df = pd.DataFrame({
        "value": np.concatenate([group_a, group_b]),
        "group": ["A"] * 100 + ["B"] * 100
    })
    
    results = compute_descriptive_compare(df, "value", "group")
    
    res_a = results["A"]
    res_b = results["B"]
    
    # Check A
    assert res_a["count"] == 100
    assert res_a["mean"] is not None
    assert res_a["cv"] is not None
    # Expected CV is around 20 (SD=2 / Mean=10 * 100)
    assert 15 < res_a["cv"] < 25 
    
    # Check B
    assert res_b["geometric_mean"] is not None
    # Log-normal mean=2 -> exp(2) approx 7.38
    assert 6 < res_b["geometric_mean"] < 9
    
    # Check other metrics
    assert res_a["skewness"] is not None
    assert res_a["kurtosis"] is not None
    assert res_a["shapiro_p"] is not None

def test_descriptives_missing_values():
    df = pd.DataFrame({
        "value": [1, 2, np.nan, 4, 5],
        "group": ["A", "A", "A", "A", "A"]
    })
    results = compute_descriptive_compare(df, "value", "group")
    res_a = results["A"]
    
    assert res_a["count"] == 4
    assert res_a["missing"] == 1
    assert res_a["mean"] == 3.0


def test_descriptives_constant_series_no_runtime_warning():
    df = pd.DataFrame(
        {
            "value": [5.0] * 20,
            "group": ["A"] * 20,
        }
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        results = compute_descriptive_compare(df, "value", "group")

    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warnings
    res_a = results["A"]
    assert res_a["shapiro_w"] is None
    assert res_a["shapiro_p"] is None
