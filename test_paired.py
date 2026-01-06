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
        self.captured_output = None
    def load_dataset(self, id):
        pass 
    def create_analysis_run(self, id, proto):
        return "/tmp/run_paired" 
    def save_run_results(self, run_id, res):
        self.captured_output = res
        return run_id

def run_test():
    n = 20
    # Create Paired Data (Pre < Post)
    pre = np.random.normal(120, 10, n)
    post = pre - 10 + np.random.normal(0, 5, n) # Decrease by 10
    
    df = pd.DataFrame({
        "BP_Pre": pre,
        "BP_Post": post
    })
    
    protocol = {
        "steps": [
            {
                "id": "desc_paired",
                "type": "descriptive_paired",
                "target_a": "BP_Pre",
                "target_b": "BP_Post"
            },
            {
                "id": "test_paired",
                "type": "compare_paired",
                "target_a": "BP_Pre",
                "target_b": "BP_Post",
                "method": "t_test_rel"
            }
        ]
    }
    
    pipeline = MockPipeline()
    engine = ProtocolEngine(pipeline)
    engine.execute_protocol("dummy", df, protocol)
    
    results = pipeline.captured_output["results"]
    
    print("Results Keys:", results.keys())
    
    desc = results.get("desc_paired")
    test = results.get("test_paired")
    
    if desc and test:
        print("✅ Desc:", desc)
        print("✅ Test:", test)
        
        # Check logic
        if desc.get("mean_diff") < -5:
            print("✅ Mean Diff is negative as expected")
        else:
            print("❌ Mean Diff unexpected")
            
        if test.get("p_value") < 0.05:
             print("✅ Significant difference found")
        else:
             print("❌ Not significant (unexpected for this data)")
    else:
        print("❌ Missing results")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"Crash: {e}")
        import traceback
        traceback.print_exc()
