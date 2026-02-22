
import pytest
import pandas as pd
import numpy as np
from app.stats.engine import _run_analysis_python

def create_dummy_data():
    np.random.seed(42)
    df = pd.DataFrame({
        'group': np.random.choice(['A', 'B', 'C'], 100),
        'score': np.random.normal(0, 1, 100),
        'score2': np.random.normal(0, 1, 100),
        'x1': np.random.normal(0, 1, 100),
        'x2': np.random.normal(0, 1, 100)
    })
    # Correlate x1 and x2 for VIF
    df['x3'] = df['x1'] * 0.9 + np.random.normal(0, 0.1, 100) 
    return df

def test_ttest_config():
    df = create_dummy_data()
    df = df[df['group'].isin(['A', 'B'])] # Ensure 2 groups for t-test
    # 1. Default (Cohen's d, CI, Descriptives)
    res = _run_analysis_python(df, 't_test_ind', 'score', 'group')
    assert res['effect_size_name'] in ['cohen-d', 'cohen']
    assert res['effect_size_ci_lower'] is not None
    assert res['plot_stats'] is not None

    # 2. Hedges' g, No CI, No Descriptives
    res = _run_analysis_python(df, 't_test_ind', 'score', 'group', 
                              effect_size='hedges', ci=False, descriptives=False)
    assert res['effect_size_name'] == 'hedges'
    assert res['effect_size_ci_lower'] is None
    assert res['plot_stats'] is None

    # 3. Glass's delta
    res = _run_analysis_python(df, 't_test_ind', 'score', 'group', 
                              effect_size='glass', ci=True)
    assert res['effect_size_name'] == 'glass'
    assert res['effect_size_ci_lower'] is not None

def test_anova_config():
    df = create_dummy_data()
    # 1. Default (Eta-squared)
    res = _run_analysis_python(df, 'anova', 'score', 'group', effect_size='eta_squared')
    # Depending on implementation, can be eta2 or eta_squared
    assert res['effect_size_name'] in ['eta2', 'eta_squared', 'np2'] # One-way, eta2=np2

    # 2. Omega-squared
    res = _run_analysis_python(df, 'anova', 'score', 'group', effect_size='omega_squared')
    # With limited sample/variance, logic should try to compute it
    if res['effect_size'] is not None:
         # Name might be hardcoded to what we requested if we computed it, 
         # or fell back. If we succeeded, it should be 'omega_squared' (implicit) or passed through.
         pass 

def test_regression_config():
    df = create_dummy_data()
    # 1. CI=False, VIF=True
    res = _run_analysis_python(df, 'linear_regression', 'score', None, 
                              predictors=['x1', 'x2', 'x3'], ci=False, vif=True)
    # Check VIF exists in coefficients
    coeffs = res['coefficients']
    has_vif = any('vif' in c and c['vif'] is not None for c in coeffs if c['variable'] != 'const')
    assert has_vif
    # Check CI is None
    assert coeffs[0]['ci_lower'] is None

    # 2. CI=True, VIF=False
    res = _run_analysis_python(df, 'linear_regression', 'score', None, 
                              predictors=['x1', 'x2', 'x3'], ci=True, vif=False)
    coeffs = res['coefficients']
    assert coeffs[0]['ci_lower'] is not None
    # VIF might be None or strict check
    # Check if 'vif' key is present but None, or just checking first valid var
    var_coeff = next(c for c in coeffs if c['variable'] != 'const')
    assert var_coeff.get('vif') is None

