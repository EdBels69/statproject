import sys
import pandas as pd
import numpy as np

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.stats.engine import _handle_correlation_matrix

def run_test():
    # Create Data (3 Variables)
    n = 50
    # X1 and X2 correlated, X3 random
    x1 = np.random.normal(0, 1, n)
    x2 = x1 * 0.8 + np.random.normal(0, 0.5, n)
    x3 = np.random.normal(5, 2, n)
    
    df = pd.DataFrame({
        "Var1": x1,
        "Var2": x2,
        "Var3": x3,
        "Group": ["A"] * n # noise
    })
    
    # Run Correlation
    try:
        res = _handle_correlation_matrix(df, ["Var1", "Var2", "Var3"], method="pearson")
        
        # Verify
        if "error" in res:
            print(f"❌ Error: {res['error']}")
            return

        print(f"✅ Method: {res['method']}")
        
        # Check Image
        if res.get("plot_image") and len(res["plot_image"]) > 100:
            print(f"✅ Plot Image Generated ({len(res['plot_image'])} bytes)")
        else:
             print("❌ Plot Image Missing or too small")
             
        # Check Matrix (3x3)
        corr = res.get("corr_matrix")
        if len(corr) == 3:
             print(f"✅ Correlation Matrix 3x3 verified")
        else:
             print(f"❌ Correlation Matrix Size: {len(corr)}")

        # Check values
        print(f"  Corr(Var1, Var2) ~0.8: {corr['Var1']['Var2']:.2f}")

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
