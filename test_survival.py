import sys
import pandas as pd
import numpy as np

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.stats.engine import _handle_survival

def run_test():
    print("--- Survival Analysis Test ---")
    
    # Create Data (Censored)
    # Group A: Short survival (mean 10)
    # Group B: Long survival (mean 20)
    n = 30
    time_a = np.random.exponential(10, n)
    event_a = np.random.binomial(1, 0.8, n) # 80% events
    
    time_b = np.random.exponential(20, n)
    event_b = np.random.binomial(1, 0.8, n)
    
    df = pd.DataFrame({
        "Time": np.concatenate([time_a, time_b]),
        "Event": np.concatenate([event_a, event_b]),
        "Group": ["A"]*n + ["B"]*n
    })
    
    # 1. Overall Survival
    print("\n[1] Overall Survival")
    res_overall = _handle_survival(df, "Time", "Event")
    if "error" in res_overall:
        print(f"❌ Failed: {res_overall['error']}")
    else:
        print(f"✅ Method: {res_overall['method']}")
        print(f"✅ Median Survival (Overall): {res_overall['median_survival'].get('Overall')}")
        if res_overall.get("plot_image"):
             print(f"✅ Plot Generated ({len(res_overall['plot_image'])} bytes)")

    # 2. Grouped Survival (Log-Rank)
    print("\n[2] Grouped Survival (A vs B)")
    res_grouped = _handle_survival(df, "Time", "Event", "Group")
    if "error" in res_grouped:
         print(f"❌ Failed: {res_grouped['error']}")
    else:
         p = res_grouped.get("p_value")
         print(f"✅ Log-Rank P-Value: {p}")
         media = res_grouped.get("median_survival")
         print(f"✅ Medians: A={media.get('A'):.2f}, B={media.get('B'):.2f}")
         
         if p is not None and p < 0.1: # Should be significant
             print("✅ Significant difference detected")
         else:
             print(f"⚠️ P-value {p} seems high (check data)")

if __name__ == "__main__":
    run_test()
