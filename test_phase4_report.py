import sys
import pandas as pd
import numpy as np
import io
import base64

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.modules.word_report import generate_word_report

def run_test():
    print("--- Phase 4 Report Test ---")
    
    # 1. Mock Regression Result
    # Minimal Base64 transparent pixel
    dummy_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    
    reg_res = {
        "type": "regression",
        "method": "ols",
        "target": "Y",
        "n_obs": 100,
        "fit_stats": {"n_obs": 100, "r_squared": 0.85, "aic": 120.5},
        "plot_image": dummy_img,
        "coef_table": [
             {"variable": "const", "coef": 5.1, "std_err": 0.1, "p_value": 0.0000, "ci_lower": 4.9, "ci_upper": 5.3},
             {"variable": "X1", "coef": 2.2, "std_err": 0.05, "p_value": 0.001, "ci_lower": 2.1, "ci_upper": 2.3}
        ]
    }
    
    # 2. Mock Survival Result
    surv_res = {
        "type": "survival",
        "method": "kaplan_meier",
        "p_value": 0.035,
        "median_survival": {"A": 12.5, "B": 24.0},
        "plot_image": dummy_img
    }
    
    # 3. Step Map
    run_data = {
         "results": {
             "step_reg": reg_res,
             "step_surv": surv_res
         }
    }
    
    try:
        doc_bytes = generate_word_report(run_data, "TestPhase4.csv")
        print(f"✅ Report Generated ({len(doc_bytes)} bytes)")
        
        # Optional: Save to check manually
        with open("test_phase4.docx", "wb") as f:
             f.write(doc_bytes)
             
    except Exception as e:
         print(f"❌ Report Generation Failed: {e}")
         import traceback
         traceback.print_exc()

if __name__ == "__main__":
    run_test()
