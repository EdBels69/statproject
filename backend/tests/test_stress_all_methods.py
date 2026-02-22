import sys
import os
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.api.datasets import DATA_DIR
from app.stats.registry import get_method
import shutil

client = TestClient(app)
TEST_ID = "test_stress_all_methods"
TEST_DIR = os.path.join(DATA_DIR, TEST_ID)

# Test data generation for different method types
def generate_test_data(method_id: str, n: int = 100) -> tuple:
    """Returns (dataset, target, group, kwargs) for a given method."""
    np.random.seed(42)
    
    if method_id == "t_test_one":
        df = pd.DataFrame({
            "Value": np.random.normal(10, 2, n)
        })
        return df, "Value", None, {"test_value": 10}
    
    elif method_id in ["t_test_ind", "t_test_welch", "mann_whitney"]:
        df = pd.DataFrame({
            "Group": ["A"]*n + ["B"]*n,
            "Value": np.concatenate([np.random.normal(10, 2, n), np.random.normal(12, 2, n)])
        })
        return df, "Value", "Group", {}
    
    elif method_id in ["t_test_rel", "wilcoxon"]:
        df = pd.DataFrame({
            "Subject": range(n),
            "Before": np.random.normal(10, 2, n),
            "After": np.random.normal(11, 2, n)
        })
        return df, "Before", "After", {}
    
    elif method_id in ["chi_square", "fisher"]:
        df = pd.DataFrame({
            "Treatment": ["A"]*50 + ["B"]*50,
            "Outcome": ["Success"]*35 + ["Failure"]*15 + ["Success"]*25 + ["Failure"]*25
        })
        return df, "Treatment", "Outcome", {}
    
    elif method_id in ["pearson", "spearman"]:
        df = pd.DataFrame({
            "X": np.random.normal(0, 1, n),
            "Y": np.random.normal(0, 1, n)
        })
        return df, "X", "Y", {}
    
    elif method_id in ["anova", "anova_welch", "kruskal"]:
        df = pd.DataFrame({
            "Group": ["A"]*n + ["B"]*n + ["C"]*n,
            "Value": np.concatenate([
                np.random.normal(10, 2, n),
                np.random.normal(12, 2, n),
                np.random.normal(14, 2, n)
            ])
        })
        return df, "Value", "Group", {}
    
    elif method_id == "rm_anova":
        subjects = range(20)
        df = pd.DataFrame({
            "Subject": np.repeat(subjects, 3),
            "Time": ["Pre", "Post1", "Post2"] * 20,
            "Value": np.random.normal(10, 2, 60) + np.tile([0, 2, 4], 20)
        })
        return df, "Value", "Time", {"subject": "Subject"}
    
    elif method_id == "friedman":
        subjects = range(15)
        df = pd.DataFrame({
            "Subject": np.repeat(subjects, 3),
            "Condition": ["A", "B", "C"] * 15,
            "Value": np.random.normal(10, 2, 45) + np.tile([0, 1, 2], 15)
        })
        return df, "Value", "Condition", {"subject": "Subject"}
    
    elif method_id == "mixed_model":
        subjects = np.repeat(range(10), 10)
        df = pd.DataFrame({
            "Subject": subjects,
            "Time": np.tile(range(10), 10),
            "Group": ["Control"]*50 + ["Treatment"]*50,
            "Value": np.random.normal(10, 2, 100) + np.where(np.array([subjects[i] < 5 for i in range(100)]), 0, 2)
        })
        return df, "Value", "Time", {"predictors": ["Time", "Group"], "random": ["Subject"]}
    
    elif method_id == "survival_km":
        df = pd.DataFrame({
            "Group": ["Control"]*50 + ["Treatment"]*50,
            "Time": np.concatenate([
                np.random.exponential(30, 50),
                np.random.exponential(45, 50)
            ]),
            "Event": np.random.binomial(1, 0.8, 100)
        })
        return df, "Time", "Event", {"group_col": "Group"}
    
    elif method_id == "linear_regression":
        df = pd.DataFrame({
            "Y": np.random.normal(10, 2, n),
            "X1": np.random.normal(0, 1, n),
            "X2": np.random.normal(0, 1, n)
        })
        return df, "Y", "X1", {"predictors": ["X1", "X2"]}
    
    elif method_id == "logistic_regression":
        df = pd.DataFrame({
            "Y": np.random.binomial(1, 0.5, n),
            "X1": np.random.normal(0, 1, n),
            "X2": np.random.normal(0, 1, n)
        })
        return df, "Y", "X1", {"predictors": ["X1", "X2"]}
    
    elif method_id == "roc_analysis":
        df = pd.DataFrame({
            "Outcome": ["Positive"]*50 + ["Negative"]*50,
            "Predictor": np.concatenate([
                np.random.normal(1, 1, 50),
                np.random.normal(0, 1, 50)
            ])
        })
        return df, "Outcome", "Predictor", {}
    
    else:
        raise ValueError(f"Unknown method: {method_id}")


def setup_test_dataset(df, dataset_id: str):
    """Create test dataset directory and save data."""
    test_dir = os.path.join(DATA_DIR, dataset_id)
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(os.path.join(test_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(test_dir, "processed"), exist_ok=True)
    
    # Save processed data
    df.to_parquet(os.path.join(test_dir, "processed", f"{dataset_id}.parquet"))
    
    # Create mock scan report
    columns_info = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            columns_info[col] = {"type": "numeric"}
        else:
            columns_info[col] = {"type": "categorical"}
    
    import json
    with open(os.path.join(test_dir, "processed", "scan_report.json"), "w") as f:
        json.dump({"columns": columns_info}, f)


def test_all_methods():
    """Stress test: Run all 20 statistical methods."""
    print("=" * 60)
    print("STRESS TEST: Testing all 20 statistical methods")
    print("=" * 60)
    
    results = {
        "passed": [],
        "failed": [],
        "errors": []
    }
    
    all_methods = list(get_method("").__class__.__bases__[0].__dict__.keys()) if hasattr(get_method(""), "__class__") else []
    
    for method_id in [
        "t_test_one", "t_test_ind", "t_test_welch", "mann_whitney",
        "t_test_rel", "wilcoxon", "chi_square", "fisher",
        "pearson", "spearman", "anova", "anova_welch", "kruskal",
        "rm_anova", "friedman", "mixed_model", "survival_km",
        "linear_regression", "logistic_regression", "roc_analysis"
    ]:
        print(f"\n[{method_id}] Testing...")
        
        try:
            method = get_method(method_id)
            if not method:
                results["errors"].append((method_id, "Method not found in registry"))
                print(f"  ✗ FAILED: Method not found in registry")
                continue
            
            # Generate test data
            df, target, group, kwargs = generate_test_data(method_id)
            
            # Setup dataset
            dataset_id = f"test_stress_{method_id}"
            setup_test_dataset(df, dataset_id)
            
            # Create protocol step
            step = {
                "id": f"step_{method_id}",
                "type": "hypothesis_test" if group else "correlation",
                "method": method_id,
                "target": target,
                **({"group": group} if group else {}),
                **kwargs
            }
            
            # Execute analysis
            protocol = {
                "name": f"Stress test {method_id}",
                "steps": [step]
            }
            
            payload = {
                "dataset_id": dataset_id,
                "protocol": protocol
            }
            
            run_resp = client.post("/api/v1/analysis/protocol/run", json=payload)
            
            if run_resp.status_code != 200:
                results["errors"].append((method_id, f"HTTP {run_resp.status_code}: {run_resp.text}"))
                print(f"  ✗ FAILED: HTTP {run_resp.status_code}")
                continue
            
            run_id = run_resp.json()["run_id"]
            
            # Fetch results
            res_resp = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
            
            if res_resp.status_code != 200:
                results["errors"].append((method_id, f"Failed to fetch results"))
                print(f"  ✗ FAILED: Could not fetch results")
                continue
            
            result_data = res_resp.json()
            step_result = result_data["results"].get(f"step_{method_id}")
            
            if not step_result:
                results["errors"].append((method_id, "No result returned"))
                print(f"  ✗ FAILED: No result returned")
                continue
            
            # Validate result structure
            required_fields = ["method", "conclusion"]
            missing_fields = [f for f in required_fields if f not in step_result]
            
            if missing_fields:
                results["failed"].append((method_id, f"Missing fields: {missing_fields}"))
                print(f"  ✗ FAILED: Missing fields: {missing_fields}")
                continue
            
            results["passed"].append(method_id)
            print(f"  ✓ PASSED")
            
            # Cleanup
            test_dir = os.path.join(DATA_DIR, dataset_id)
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
            
        except Exception as e:
            results["errors"].append((method_id, str(e)))
            print(f"  ✗ ERROR: {str(e)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)
    print(f"Total Methods: 20")
    print(f"Passed: {len(results['passed'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Errors: {len(results['errors'])}")
    
    if results["passed"]:
        print(f"\n✓ PASSED ({len(results['passed'])}):")
        for m in results["passed"]:
            print(f"  - {m}")
    
    if results["failed"]:
        print(f"\n✗ FAILED ({len(results['failed'])}):")
        for m, reason in results["failed"]:
            print(f"  - {m}: {reason}")
    
    if results["errors"]:
        print(f"\n⚠ ERRORS ({len(results['errors'])}):")
        for m, reason in results["errors"]:
            print(f"  - {m}: {reason}")
    
    print("=" * 60)
    
    # Cleanup test datasets
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    
    return len(results["passed"]) == 20


if __name__ == "__main__":
    success = test_all_methods()
    sys.exit(0 if success else 1)
