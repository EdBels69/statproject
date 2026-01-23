import pandas as pd
import numpy as np
from app.stats.engine import run_analysis

def test_anova_tukey():
    print("--- Testing ANOVA with Tukey HSD ---")

    np.random.seed(42)
    
    # 1. Create Data with clear differences
    # Group A: Mean 10
    # Group B: Mean 12
    # Group C: Mean 20 (Clearly different)
    df = pd.DataFrame({
        "value": np.concatenate([
            np.random.normal(10, 1, 20),
            np.random.normal(12, 1, 20),
            np.random.normal(20, 1, 20)
        ]),
        "group": np.concatenate([
            ["A"] * 20,
            ["B"] * 20,
            ["C"] * 20
        ])
    })
    
    # 2. Run ANOVA
    results = run_analysis(df, "anova", "value", "group")
    
    print(f"ANOVA P-Value: {results['p_value']}")
    print(f"Significant: {results['p_value'] < 0.05}")
    
    # 3. Verify Tukey HSD
    post_hoc = results.get("post_hoc")
    print(f"Post-hoc Results Present: {post_hoc is not None}")
    
    if post_hoc:
        print(f"Number of Pairwise Comparisons: {len(post_hoc)}")
        for comp in post_hoc:
            print(f"  {comp['group1']} vs {comp['group2']}: diff={comp['diff']:.2f}, p={comp['p_value']:.4f}, sig={comp['significant']}")
            
    # Assertions
    assert results['p_value'] < 0.05, "ANOVA should be significant"
    assert post_hoc is not None, "Post-hoc results missing for significant ANOVA"
    assert len(post_hoc) == 3, "Should have 3 comparisons (A-B, A-C, B-C)"
    
    # Check specific known difference (A vs C should be significant)
    a_c = next((x for x in post_hoc if (x['group1']=='A' and x['group2']=='C') or (x['group1']=='C' and x['group2']=='A')), None)
    assert a_c is not None
    assert a_c['significant'] == True, "A vs C should be significant"

    # 4. Run ANOVA with BKY correction request (post-hoc should include adjusted p-values)
    results_bky = run_analysis(df, "anova", "value", "group", post_hoc="tukey", post_hoc_correction="bky")
    post_hoc_bky = results_bky.get("post_hoc")
    assert post_hoc_bky is not None
    any_adj = any((c.get("p_value_adj") is not None) for c in post_hoc_bky)
    assert any_adj, "Expected adjusted p-values in post-hoc results"

if __name__ == "__main__":
    test_anova_tukey()
