"""
Verification tests for TASK-001 (Effect Size) and TASK-002 (ANOVA Eta-squared).
"""
import pytest
import pandas as pd
import numpy as np
from app.stats.engine import _handle_group_comparison, interpret_effect_size
from app.modules.text_generator import TextGenerator

def test_interpret_effect_size_function():
    """Test the interpret_effect_size function in engine.py."""
    # Cohen's d
    res = interpret_effect_size(0.1, "cohen_d")
    assert res["label"] == "trivial"
    
    res = interpret_effect_size(0.3, "cohen_d")
    assert res["label"] == "small"
    
    res = interpret_effect_size(0.6, "cohen_d")
    assert res["label"] == "medium"
    
    res = interpret_effect_size(0.9, "cohen_d")
    assert res["label"] == "large"

    # Eta-squared
    res = interpret_effect_size(0.02, "eta_squared")
    assert res["label"] == "small"
    
    res = interpret_effect_size(0.07, "eta_squared")
    assert res["label"] == "medium"

def test_anova_eta_squared():
    """Test that ANOVA calculation returns eta_squared."""
    # Create dataset for ANOVA (3 groups)
    # Group A: Mean=10
    # Group B: Mean=12
    # Group C: Mean=15
    data = {
        "value": np.concatenate([
            np.random.normal(10, 1, 20),
            np.random.normal(12, 1, 20),
            np.random.normal(15, 1, 20)
        ]),
        "group": np.concatenate([
            ["A"] * 20,
            ["B"] * 20,
            ["C"] * 20
        ])
    }
    df = pd.DataFrame(data)
    
    # Run ANOVA
    res = _handle_group_comparison(df, "anova", "value", "group", {})
    
    assert res["method"] == "anova"
    assert res["p_value"] < 0.05
    assert "effect_size" in res
    assert res["effect_size"] > 0
    # Accept canonical and shorthand aliases.
    assert res["effect_size_name"] in ["eta_squared", "eta2", "np2"]
    assert res["effect_size_interpretation"] is not None
    assert "label" in res["effect_size_interpretation"]

def test_text_generator_uses_interpretation():
    """Test that TextGenerator uses the interpretation from engine."""
    results = {
        "method": {"id": "anova", "name": "ANOVA"},
        "p_value": 0.001,
        "significant": True,
        "groups": ["A", "B", "C"],
        "plot_stats": {
            "A": {"mean": 10},
            "B": {"mean": 12},
            "C": {"mean": 15}
        },
        "effect_size": 0.15,
        "effect_size_name": "eta_squared",
        "effect_size_interpretation": {
            "label": "large",
            "description": "Large effect size detected"
        }
    }
    
    text_pro = TextGenerator.interpret_result(results, {"target": "Value", "group": "Group"}, style="pro")
    
    # Text should contain the description from effect_size_interpretation
    assert "Large effect size detected" in text_pro or "large" in text_pro.lower()

    # Verify manual formatter in TextGenerator
    # It should match engine's logic roughly
    tg_interp = TextGenerator.interpret_effect_size(0.15, "eta_squared")
    assert "large" in tg_interp.lower()

if __name__ == "__main__":
    _test_interpret_effect_size_function()
    test_anova_eta_squared()
    test_text_generator_uses_interpretation()
