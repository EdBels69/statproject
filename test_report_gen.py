import sys
import pandas as pd
import numpy as np
import os

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.modules.word_report import generate_word_report
from app.api.analysis import AnalysisResult # Schema

def run_test():
    # Mock Data Structure resembling ProtocolEngine output
    results = {
        # 1. Group Comparison (T-test)
        "test_age": {
            "type": "hypothesis_test",
            "target": "Age",
            "method": "t_test_ind",
            "p_value": 0.045,
            "stat_value": 2.1,
            "significant": True,
            "effect_size": 0.5,
            # Plot Data
            "plot_data": [
                {"group": "A", "value": 25}, {"group": "A", "value": 26},
                {"group": "B", "value": 30}, {"group": "B", "value": 32}
            ]
        },
        # 2. Descriptive Paired
        "desc_bp": {
            "type": "descriptive_paired",
            "variables": ["BP_Pre", "BP_Post"],
            "mean_diff": -5.0,
            "std_diff": 2.0,
            "min_diff": -8, 
            "max_diff": -2,
            "n": 10
        },
        # 3. Paired Test
        "test_bp": {
            "type": "compare_paired",
            "method": "t_test_rel",
            "p_value": 0.001,
            "stat_value": -4.5,
            "significant": True,
            "plot_data": [
                {"diff": -5}, {"diff": -4}, {"diff": -6}
            ]
        },
        # 4. Subgroup Descriptive
        "desc_age_Male": {
            "type": "descriptive_compare",
            "target": "Age",
            "subgroup": "Male",
            "stats": {
                "A": {"count": 10, "mean": 30, "std": 5},
                "B": {"count": 10, "mean": 35, "std": 5},
                "overall": {"count": 20, "mean": 32.5}
            }
        }
    }
    
    run_data = {
        "results": results
    }
    
    # Generate
    try:
        doc_bytes = generate_word_report(run_data, "MockDataset.csv")
        print(f"Generated Doc: {len(doc_bytes)} bytes")
        
        with open("test_report_full.docx", "wb") as f:
            f.write(doc_bytes)
        print("✅ Saved to test_report_full.docx")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
