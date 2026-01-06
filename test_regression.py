import sys
import pandas as pd
import numpy as np

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.stats.engine import _handle_regression

def run_test():
    print("--- Regression Logic Test ---")
    
    # 1. Linear Regression (OLS)
    # y = 2x1 + 3x2 + 5 + noise
    n = 100
    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)
    y_linear = 2*x1 + 3*x2 + 5 + np.random.normal(0, 0.5, n)
    
    df_ols = pd.DataFrame({"Y": y_linear, "X1": x1, "X2": x2})
    
    print("\n[1] Linear Regression (OLS)")
    res_ols = _handle_regression(df_ols, "Y", ["X1", "X2"], "auto")
    
    if "error" in res_ols:
        print(f"❌ OLS Failed: {res_ols['error']}")
    else:
        print(f"✅ Method: {res_ols['method']} (Expected 'ols')")
        print(f"✅ R-Squared: {res_ols['fit_stats']['r_squared']:.4f}")
        
        # Check Coeffs
        coeffs = {r['variable']: r['coef'] for r in res_ols['coef_table']}
        print(f"  Intercept (Exp ~5): {coeffs.get('const'):.2f}")
        print(f"  X1 (Exp ~2): {coeffs.get('X1'):.2f}")
        print(f"  X2 (Exp ~3): {coeffs.get('X2'):.2f}")
        
        if abs(coeffs.get('X1') - 2) < 0.2:
            print("✅ Coefficients correct within tolerance")
        else:
            print("❌ Coefficients inaccurate")
            
        if res_ols.get("plot_image"):
             print(f"✅ Diagnostic Plot Generated ({len(res_ols['plot_image'])} bytes)")

    # 2. Logistic Regression (Logit)
    # y = 1 if (x1 + x2 > 0) else 0
    y_logit = (x1 + x2 + np.random.normal(0, 0.5, n) > 0).astype(int)
    df_logit = pd.DataFrame({"Y": y_logit, "X1": x1, "X2": x2})
    
    print("\n[2] Logistic Regression (Logit)")
    res_logit = _handle_regression(df_logit, "Y", ["X1", "X2"], "auto")
    
    if "error" in res_logit:
         print(f"❌ Logit Failed: {res_logit['error']}")
    else:
         print(f"✅ Method: {res_logit['method']} (Expected 'logit')")
         print(f"✅ Pseudo R-Squared: {res_logit['fit_stats']['r_squared']:.4f}")
         
         # Check Odds Ratios
         or_table = [r for r in res_logit['coef_table'] if r['variable'] == 'X1']
         if or_table:
             print(f"  X1 Odds Ratio: {or_table[0]['odds_ratio']:.2f}")
             
         if res_logit.get("plot_image"):
             print(f"✅ ROC Curve Generated ({len(res_logit['plot_image'])} bytes)")

if __name__ == "__main__":
    run_test()
