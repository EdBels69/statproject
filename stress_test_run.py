import sys
import os
import pandas as pd
import time
import numpy as np

# Correct path: point to 'backend' so 'app' is a module
backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

try:
    from app.stats.engine import validate_group_column, run_batch_analysis, run_analysis
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Path is: {sys.path}")
    sys.exit(1)

def test_messy_group():
    print("\n--- Test 1: Messy Group Validation ---")
    df = pd.read_csv("workspace/datasets/stress_test.csv")
    res = validate_group_column(df, "group_messy")
    print(f"Valid: {res['valid']}")
    if res.get('warnings'):
        print(f"Warnings: {res['warnings']}")
    
    if any("repeated values" in w for w in res.get('warnings', [])):
        print("✅ Correctly detected messy group")
    else:
        print("❌ Failed to detect messy group")

def test_too_many_groups():
    print("\n--- Test 2: Too Many Groups ---")
    df = pd.read_csv("workspace/datasets/stress_test.csv")
    res = validate_group_column(df, "group_many")
    print(f"Valid: {res['valid']}")
    if res.get('warnings'):
        print(f"Warnings: {res['warnings']}")
        
    if any("Too many groups" in w for w in res.get('warnings', [])):
        print("✅ Correctly detected too many groups")
    else:
        print("❌ Failed to detect too many groups count")

def test_performance():
    print("\n--- Test 3: Batch Analysis Performance (50 vars) ---")
    df = pd.read_csv("workspace/datasets/stress_test.csv", encoding='utf-8')
    targets = [f"feature_{i}" for i in range(50)]
    
    start_time = time.time()
    
    # Run batch analysis
    # Need to verify signature of run_batch_analysis
    # def run_batch_analysis(df: pd.DataFrame, targets: List[str], group_col: str, method_id: str = "t_test_ind")
    
    try:
        results = run_batch_analysis(df, targets, "group_clean", method_id="t_test_ind")
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"Processed {len(targets)} variables in {duration:.4f} seconds")
        
        if duration < 5.0:
            print("✅ Performance is acceptable (< 5s)")
        else:
            print(f"⚠️ Performance took {duration:.2f}s")
            
        print(f"Results keys count: {len(results)}")
        
    except Exception as e:
        print(f"Batch Analysis Crash: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_messy_group()
    test_too_many_groups()
    test_performance()
