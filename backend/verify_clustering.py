import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from app.stats.engine import _handle_correlation_matrix

# Ensuring Agg backend
import matplotlib
matplotlib.use('Agg')

def verify_clustering():
    print("--- Verifying Correlation Clustering ---")
    
    # Create sample data with structure
    # Group A: x1, x2 highly correlated
    # Group B: x3, x4 highly correlated
    # A and B weakly correlated
    np.random.seed(42)
    n = 100
    x1 = np.random.randn(n)
    x2 = x1 + np.random.normal(0, 0.2, n)  # High corr with x1
    x3 = np.random.randn(n)
    x4 = x3 + np.random.normal(0, 0.2, n)  # High corr with x3
    
    # Add some noise to x1/x2 vs x3/x4
    df = pd.DataFrame({
        'var_A1': x1,
        'var_A2': x2,
        'var_B1': x3,
        'var_B2': x4,
        'var_Noise': np.random.randn(n)
    })
    
    print("Data created. Running clustered correlation...")
    
    try:
        results = _handle_correlation_matrix(
            df, 
            ['var_A1', 'var_A2', 'var_B1', 'var_B2', 'var_Noise'], 
            method='pearson', 
            cluster_variables=True
        )
        
        # Checks
        print(f"Clustered Flag: {results['clustered']}")
        print(f"Variables Order: {results['variables']}")
        
        if not results['plot_image']:
            print("❌ Error: No plot image returned!")
        else:
            print("✅ Plot image returned (Base64 string present)")
            
        if not results['clustered']:
            print("❌ Error: Clustering flag is False but requested True")
            
        # Check reordering logic
        # Ideally, var_A1 and var_A2 should be adjacent, var_B1 and var_B2 adjacent
        vars_reordered = results['variables']
        # We can't strictly predict order but we can check if matrix keys match
        
        matrix_keys = list(results['corr_matrix'].keys())
        if matrix_keys != vars_reordered:
            print(f"❌ Error: Matrix keys {matrix_keys} do not match variable list {vars_reordered}")
        else:
            print("✅ Matrix keys match reordered variable list")
            
        # Check if row keys inside matrix also match
        first_col = results['corr_matrix'][vars_reordered[0]]
        row_keys = list(first_col.keys())
        if row_keys != vars_reordered:
             print(f"❌ Error: Inner row keys {row_keys} do not match variable list {vars_reordered}")
        else:
             print("✅ Inner row keys match reordered variable list")
             
        # Check integrity
        # var_A1 vs var_A2 should be high
        corr_a1_a2 = results['corr_matrix']['var_A1']['var_A2']
        print(f"Correlation A1-A2: {corr_a1_a2:.3f} (Expected > 0.8)")
        if corr_a1_a2 < 0.8:
            print("⚠️ Warning: Correlation unexpectedly low?")

        print("\n--- Testing Edge Case: Small N (2 vars) ---")
        results_small = _handle_correlation_matrix(
            df,
            ['var_A1', 'var_A2'],
            method='pearson',
            cluster_variables=True
        )
        print(f"Clustered (2 vars): {results_small['clustered']}")
        if results_small['clustered']:
             print("✅ Clustering applied even for 2 variables.")
        else:
            print("⚠️ Clustering skipped for 2 variables (acceptable).")
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_clustering()
