import json
import base64
import sys
import os

# Fix path to allow importing app modules
sys.path.append("/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend")

BASE_URL = "http://localhost:8000/api/v1/analysis"
DATASET_ID = "test_dataset"
RUN_ID = "test_run"

# Mock data setup not feasible easily without running full analysis first.
# Instead, we will assume a run exists or mocking the internal call if possible?
# Actually, the user likely won't run this. I should perform a 'dry run' test 
# by mocking the pipeline manager or just checking the function directly.

from app.stats.plotter import render_custom_plot

def test_plotter():
    print("Testing Plotter...")
    
    # 1. Scatter Data
    scatter_data = {
        "type": "scatter",
        "x": [1, 2, 3, 4, 5],
        "y": [2.1, 4.2, 6.1, 8.0, 10.5]
    }
    
    params = {
        "title": "Custom Scatter",
        "xlabel": "Time",
        "ylabel": "Value",
        "theme": "seaborn",
        "color": "#FF0000"
    }
    
    img = render_custom_plot(scatter_data, params)
    if len(img) > 100:
        print("Scatter Plot Generated: OK")
    else:
        print("Scatter Plot Failed")

    # 2. Survival Data
    survival_data = [
        {"group": "A", "time": [0, 5, 10], "prob": [1.0, 0.8, 0.5]},
        {"group": "B", "time": [0, 6, 12], "prob": [1.0, 0.9, 0.7]}
    ]
    
    params["title"] = "Custom Kaplan-Meier"
    img2 = render_custom_plot(survival_data, params)
    if len(img2) > 100:
        print("Survival Plot Generated: OK")
    else:
        print("Survival Plot Failed")

if __name__ == "__main__":
    test_plotter()
