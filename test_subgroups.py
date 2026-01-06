import sys
import pandas as pd
import numpy as np

# Setup
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.core.protocol_engine import ProtocolEngine

class MockPipeline:
    def __init__(self):
        pass
    def load_dataset(self, id):
        pass 
    def create_analysis_run(self, id, proto):
        return "/tmp/run" 
    def save_run_results(self, run_id, res):
        pass

class CapturingPipeline(MockPipeline):
    def __init__(self):
        self.captured_results = None
    def save_run_results(self, run_id, res):
        self.captured_results = res
        return run_id

def run_test():
    n = 100
    df = pd.DataFrame({
        "Age": np.random.normal(30, 5, n),
        "Score": np.random.normal(50, 10, n),
        "Treatment": ["A"] * 50 + ["B"] * 50,
        "Sex": ["Male", "Female"] * 50
    })
    protocol = {
        "steps": [
            {
                "id": "test_age",
                "type": "compare",
                "target": "Age",
                "group": "Treatment",
                "subgroup": "Sex"
            }
        ]
    }
    
    pipeline = CapturingPipeline()
    engine = ProtocolEngine(pipeline)
    engine.execute_protocol("dummy_id", df, protocol)
    
    res = pipeline.captured_results
    results = res.get("results", {})
    logs = res.get("log", [])
    
    print("LOGS:", logs)
    print("Keys found:", results.keys())
    
    expected = ["test_age_Male", "test_age_Female"]
    found = [k for k in results.keys() if k in expected]
    
    if len(found) == 2:
        print("✅ Correctly exploded into subgroups")
        if results["test_age_Male"].get("subgroup") == "Male":
            print("✅ Metadata injected correctly")
        else:
            print("❌ Metadata missing")
    else:
        print("❌ Failed to explode: " + str(list(results.keys())))

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"Crash: {e}")
        import traceback
        traceback.print_exc()
