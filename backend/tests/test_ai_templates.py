"""
Verification tests for TASK-004 (AI Interpretation Templates).
"""
import pytest
from app.modules.text_generator import TextGenerator

def test_interpret_group_comparison_independent():
    """Test T-test independent interpretation."""
    results = {
        "method": {"id": "t_test_ind", "name": "Independent T-test"},
        "p_value": 0.001,
        "significant": True,
        "groups": ["Control", "Treatment"],
        "plot_stats": {
            "Control": {"mean": 10},
            "Treatment": {"mean": 15}
        },
        "effect_size": 0.8,
        "effect_size_name": "cohen-d"
    }
    variables = {"target": "Pain Score", "group": "Group"}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "Independent T-test" in text
    assert "statistically significant difference" in text
    assert "significantly lower" in text # Control (10) < Treatment (15) ?? Wait, logic says: "Control (M=10) was ... than Treatment (M=15)" -> lower
    assert "Cohen's d = 0.80" in text

def test_interpret_anova():
    """Test ANOVA interpretation."""
    results = {
        "method": {"id": "anova", "name": "One-way ANOVA"},
        "p_value": 0.04,
        "significant": True,
        "groups": ["A", "B", "C"],
        "effect_size": 0.15,
        "effect_size_name": "eta_squared",
        "effect_size_interpretation": {"label": "large"}
    }
    variables = {"target": "Score", "group": "Group"}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "One-way ANOVA" in text
    assert "statistically significant difference" in text
    assert "effect size = 0.150" in text
    assert "(large)" in text

def test_interpret_correlation():
    """Test Pearson correlation."""
    results = {
        "method": "pearson",
        "p_value": 0.001,
        "stat_value": 0.75, # Strong positive
        "significant": True
    }
    variables = {"target": "Height", "predictor": "Weight"}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "statistically significant, very strong positive correlation" in text
    assert "r = 0.75" in text
    assert "as Weight increases, Height tends to increase" in text

def test_interpret_chi_square():
    """Test Chi-Square."""
    results = {
        "method": "chi_square",
        "p_value": 0.02,
        "significant": True,
        "effect_size": 0.35,
        "effect_size_name": "cramers_v",
        "effect_size_interpretation": {"label": "medium"}  # Mocked
    }
    variables = {"target": "Gender", "group": "Outcome"}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "Chi-Square test" in text
    assert "relation between these variables was significant" in text
    assert "dependent on Outcome" in text

def test_interpret_regression_linear():
    """Test Linear Regression interpretation."""
    results = {
        "method": "linear_regression",
        "p_value": 0.001,
        "significant": True,
        "regression": {"r_squared": 0.45}
    }
    variables = {"target": "Salary", "predictors": ["Education", "Experience"]}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "linear regression analysis" in text
    assert "Education, Experience" in text
    assert "R² of 0.45" in text
    assert "45.0% of the variance" in text

def test_interpret_regression_logistic():
    """Test Logistic Regression interpretation."""
    results = {
        "method": "logistic_regression",
        "p_value": 0.03,
        "significant": True,
        "regression": {"r_squared": 0.20} # Pseudo R2
    }
    variables = {"target": "Disease", "predictors": ["Age", "BMI"]}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "logistic regression" in text
    assert "likelihood that Disease occurs" in text
    assert "Pseudo R²" in text

def test_interpret_survival():
    """Test Survival Analysis interpretation."""
    results = {
        "method": "survival_km",
        "p_value": 0.01,
        "significant": True,
        "groups": ["A", "B"]
    }
    variables = {"time": "Days", "event": "Status", "group": "Treatment"}
    
    text = TextGenerator.interpret_result(results, variables)
    assert "Kaplan-Meier survival analysis" in text
    assert "significantly different" in text
    assert "survival times between the groups" in text
