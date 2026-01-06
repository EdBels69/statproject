import sys
import os
import pandas as pd
import time

backend_path = "/Users/eduardbelskih/.gemini/antigravity/scratch/statproject/backend"
if backend_path not in sys.path:
    sys.path.append(backend_path)

try:
    from app.stats.engine import validate_group_column, run_batch_analysis
except ImportError:
    sys.exit(1)

with open("stress_test.log", "w") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    try:
        log("--- Test 1: Messy Group ---")
        df = pd.read_csv("backend/workspace/datasets/stress_test.csv")
        res = validate_group_column(df, "group_messy")
        log(f"Valid: {res['valid']}")
        warnings = res.get('warnings', [])
        log(f"Warnings: {warnings}")
        if any("repeated values" in w for w in warnings):
            log("✅ Detected messy group")
        else:
            log("❌ Failed detection")

        log("\n--- Test 2: Too Many Groups ---")
        res2 = validate_group_column(df, "group_many")
        log(f"Valid: {res2['valid']}")
        warnings2 = res2.get('warnings', [])
        log(f"Warnings: {warnings2}")
        if any("Too many groups" in w for w in warnings2):
            log("✅ Detected too many groups")
        else:
            log("❌ Failed detection")

        log("\n--- Test 3: Performance (50 vars) ---")
        targets = [f"feature_{i}" for i in range(50)]
        start = time.time()
        results = run_batch_analysis(df, targets, "group_clean", method_id="t_test_ind")
        dur = time.time() - start
        log(f"Time: {dur:.4f}s")
        if dur < 5.0:
            log("✅ Performance OK")
        else:
            log("⚠️ Slow")

    except Exception as e:
        log(f"❌ Crash: {e}")
