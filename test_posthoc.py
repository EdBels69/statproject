import sys
import pandas as pd
import numpy as np

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.stats.engine import run_analysis

def run_test():
    # Create ANOVA data (3 Groups)
    # A: ~30, B: ~40, C: ~50 (Distinct)
    n = 20
    df = pd.DataFrame({
        "Score": np.concatenate([
            np.random.normal(30, 5, n),
            np.random.normal(40, 5, n),
            np.random.normal(50, 5, n)
        ]),
        "Group": ["A"] * n + ["B"] * n + ["C"] * n
    })
    
    # Run ANOVA
    try:
        res = run_analysis(df, "anova", "Score", "Group")
        print(f"ANOVA P-Value: {res['p_value']}")
        
        post_hoc = res.get("post_hoc")
        if post_hoc:
            print(f"✅ Post-hoc Results Detected ({len(post_hoc)} comparisons)")
            for row in post_hoc:
                print(f"  {row['group1']} vs {row['group2']}: Diff={row['diff']:.2f}, Sig={row['significant']}")
        else:
            print("❌ No Post-hoc results (Check alpha/significance)")

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
