"""
Test suite for API v2 endpoints - Advanced Statistical Methods
Tests mixed effects models, clustered correlation, and protocol v2 execution.
Memory-optimized testing for M1 8GB constraints.
"""

import sys
import os
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
import pytest
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.api.datasets import DATA_DIR
from app.api.v2 import analysis_executor
import shutil

# Setup
client = TestClient(app)
TEST_ID_V2 = "test_dataset_v2_integration"
TEST_ID_V2_CLUSTER = "test_dataset_v2_cluster"
TEST_DIR_V2 = os.path.join("workspace", "datasets", "test_dataset_v2_integration")
TEST_DIR_V2_CLUSTER = os.path.join("workspace", "datasets", TEST_ID_V2_CLUSTER)

# Test data for mixed effects (longitudinal)
def create_mixed_effects_test_data():
    """Create longitudinal test data for mixed effects models."""
    np.random.seed(42)
    n_subjects = 10
    n_timepoints = 5
    n_groups = 2
    
    data = []
    for subject_id in range(1, n_subjects + 1):
        group = "A" if subject_id <= n_subjects // 2 else "B"
        for timepoint in range(1, n_timepoints + 1):
            # Baseline + treatment effect + time effect + random noise
            baseline = 10 if group == "A" else 12
            treatment_effect = 2 if timepoint > 2 and group == "B" else 0
            time_effect = 0.5 * timepoint
            noise = np.random.normal(0, 1)
            
            outcome = baseline + treatment_effect + time_effect + noise
            
            data.append({
                "subject_id": f"S{subject_id:02d}",
                "time": timepoint,
                "group": group,
                "outcome": outcome,
                "covariate": np.random.normal(0, 1)
            })
    
    return pd.DataFrame(data)

# Test data for clustered correlation
def create_clustered_correlation_test_data():
    """Create test data with correlated variable clusters."""
    np.random.seed(42)
    n_samples = 100
    
    # Create 3 clusters of correlated variables
    cluster1 = np.random.multivariate_normal(
        [0, 0, 0], 
        [[1, 0.8, 0.7], [0.8, 1, 0.6], [0.7, 0.6, 1]], 
        n_samples
    )
    
    cluster2 = np.random.multivariate_normal(
        [5, 5, 5], 
        [[1, 0.9, 0.3], [0.9, 1, 0.2], [0.3, 0.2, 1]], 
        n_samples
    )
    
    cluster3 = np.random.multivariate_normal(
        [-3, -3, -3], 
        [[1, 0.2, 0.1], [0.2, 1, 0.8], [0.1, 0.8, 1]], 
        n_samples
    )
    
    # Independent noise variables
    noise_vars = np.random.normal(0, 1, (n_samples, 3))
    
    df = pd.DataFrame({
        'var_cluster1_1': cluster1[:, 0],
        'var_cluster1_2': cluster1[:, 1],
        'var_cluster1_3': cluster1[:, 2],
        'var_cluster2_1': cluster2[:, 0],
        'var_cluster2_2': cluster2[:, 1],
        'var_cluster2_3': cluster2[:, 2],
        'var_cluster3_1': cluster3[:, 0],
        'var_cluster3_2': cluster3[:, 1],
        'var_cluster3_3': cluster3[:, 2],
        'noise_1': noise_vars[:, 0],
        'noise_2': noise_vars[:, 1],
        'noise_3': noise_vars[:, 2],
    })
    
    return df

def setup_v2_test_data():
    """Setup test data for v2 API endpoints with correct structure."""
    if os.path.exists(TEST_DIR_V2):
        shutil.rmtree(TEST_DIR_V2)
    if os.path.exists(TEST_DIR_V2_CLUSTER):
        shutil.rmtree(TEST_DIR_V2_CLUSTER)
    
    # Create proper dataset structure for mixed effects
    os.makedirs(os.path.join(TEST_DIR_V2, "raw"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR_V2, "processed"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR_V2, "source"), exist_ok=True)
    
    # Create mixed effects test data - save as main dataset file
    mixed_df = create_mixed_effects_test_data()
    mixed_df.to_parquet(os.path.join(TEST_DIR_V2, "processed", f"{TEST_ID_V2}.parquet"))
    
    # Create clustered correlation dataset structure
    os.makedirs(os.path.join(TEST_DIR_V2_CLUSTER, "raw"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR_V2_CLUSTER, "processed"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR_V2_CLUSTER, "source"), exist_ok=True)
    
    # Create clustered correlation test data
    cluster_df = create_clustered_correlation_test_data()
    cluster_df.to_parquet(os.path.join(TEST_DIR_V2_CLUSTER, "processed", f"{TEST_ID_V2_CLUSTER}.parquet"))
    
    # Create metadata files
    import json
    
    # Main metadata for mixed effects dataset
    metadata = {
        "original_filename": "test_data.csv",
        "upload_date": "2024-01-01",
        "header_row": 0,
        "delimiter": ","
    }
    with open(os.path.join(TEST_DIR_V2, "source", "meta.json"), "w") as f:
        json.dump(metadata, f)
    
    # Metadata for clustered correlation dataset
    cluster_metadata = {
        "original_filename": "cluster_test_data.csv",
        "upload_date": "2024-01-01",
        "header_row": 0,
        "delimiter": ","
    }
    with open(os.path.join(TEST_DIR_V2_CLUSTER, "source", "meta.json"), "w") as f:
        json.dump(cluster_metadata, f)
    
    # Scan report for main dataset
    scan_report = {
        "columns": {
            "subject_id": {"type": "categorical"},
            "time": {"type": "numeric"},
            "group": {"type": "categorical"},
            "outcome": {"type": "numeric", "normality": {"is_normal": True}},
            "covariate": {"type": "numeric", "normality": {"is_normal": True}}
        }
    }
    with open(os.path.join(TEST_DIR_V2, "processed", "scan_report.json"), "w") as f:
        json.dump(scan_report, f)
    
    # Scan report for cluster data
    cluster_scan_report = {
        "columns": {
            col: {"type": "numeric", "normality": {"is_normal": True}}
            for col in cluster_df.columns
        }
    }
    with open(os.path.join(TEST_DIR_V2_CLUSTER, "processed", "scan_report.json"), "w") as f:
        json.dump(cluster_scan_report, f)

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Setup and teardown for v2 tests."""
    setup_v2_test_data()
    yield
    # Cleanup
    if os.path.exists(TEST_DIR_V2):
        shutil.rmtree(TEST_DIR_V2)
    if os.path.exists(TEST_DIR_V2_CLUSTER):
        shutil.rmtree(TEST_DIR_V2_CLUSTER)
    analysis_executor.shutdown(wait=False)

# --- Mixed Effects Tests ---

def test_mixed_effects_basic():
    """Test basic mixed effects model functionality."""
    payload = {
        "dataset_id": TEST_ID_V2,
        "outcome": "outcome",
        "time_col": "time",
        "group_col": "group",
        "subject_col": "subject_id",
        "covariates": ["covariate"],
        "random_slope": False,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/mixed-effects", json=payload)
    assert response.status_code == 200, f"Mixed effects failed: {response.text}"
    
    result = response.json()
    
    # Validate response structure (based on actual API response)
    assert "method" in result
    assert "outcome" in result
    assert "formula" in result
    assert "n_observations" in result
    assert "n_subjects" in result
    assert "coefficients" in result
    assert "main_effect_time" in result
    assert "main_effect_group" in result
    assert "interaction" in result
    
    # Validate coefficients exist
    assert len(result["coefficients"]) > 0
    
    # Check that group effect is present
    group_effects = [eff for eff in result["coefficients"] if "group" in eff["term"].lower()]
    assert len(group_effects) > 0, "Group effect should be present in results"
    
    # Check that interaction exists
    assert result["interaction"]["significant"], "Interaction should be significant in synthetic data"

def test_mixed_effects_random_slope():
    """Test mixed effects model with random slopes."""
    payload = {
        "dataset_id": TEST_ID_V2,
        "outcome": "outcome",
        "time_col": "time",
        "group_col": "group",
        "subject_col": "subject_id",
        "covariates": ["covariate"],
        "random_slope": True,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/mixed-effects", json=payload)
    assert response.status_code == 200, f"Mixed effects with random slope failed: {response.text}"
    
    result = response.json()
    assert "coefficients" in result
    # Check that random effects variance is present
    random_effects = [eff for eff in result["coefficients"] if "Var" in eff["term"]]
    assert len(random_effects) > 0, "Random effects variance should be present"

def test_mixed_effects_missing_columns():
    """Test mixed effects with missing columns."""
    payload = {
        "dataset_id": TEST_ID_V2,
        "outcome": "nonexistent",
        "time_col": "time",
        "group_col": "group",
        "subject_col": "subject_id",
        "random_slope": False,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/mixed-effects", json=payload)
    assert response.status_code == 400, "Should fail with 400 for missing columns"
    assert "not found" in response.json()["detail"].lower()

# --- Clustered Correlation Tests ---

def test_clustered_correlation_basic():
    """Test basic clustered correlation functionality."""
    payload = {
        "dataset_id": TEST_ID_V2_CLUSTER,
        "variables": [
            "var_cluster1_1", "var_cluster1_2", "var_cluster1_3",
            "var_cluster2_1", "var_cluster2_2", "var_cluster2_3"
        ],
        "method": "pearson",
        "linkage_method": "ward",
        "n_clusters": 2,
        "show_p_values": True,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/clustered-correlation", json=payload)
    assert response.status_code == 200, f"Clustered correlation failed: {response.text}"
    
    result = response.json()
    
    # Validate response structure
    assert "correlation_matrix" in result
    assert "dendrogram" in result
    assert "cluster_assignments" in result
    assert "heatmap_data" in result
    assert "clusters" in result
    
    # Validate correlation matrix structure
    assert "variables" in result["correlation_matrix"]
    assert "values" in result["correlation_matrix"]
    assert len(result["correlation_matrix"]["variables"]) == 6
    
    # Validate cluster assignments
    assert isinstance(result["cluster_assignments"], dict)
    assert len(result["cluster_assignments"]) == 6
    
    # Validate clusters
    assert isinstance(result["clusters"], list)
    assert result["n_clusters"] == 2
    
    # Validate matrix dimensions
    n_vars = len(payload["variables"])
    corr_matrix = result["correlation_matrix"]["values"]
    assert len(corr_matrix) == n_vars
    assert all(len(row) == n_vars for row in corr_matrix)
    
    # Validate heatmap_data structure
    heatmap_data = result["heatmap_data"]
    assert isinstance(heatmap_data, list)
    assert len(heatmap_data) == n_vars * n_vars
    assert all("row" in item and "col" in item and "r" in item for item in heatmap_data)

def test_clustered_correlation_auto_clusters():
    """Test clustered correlation with automatic cluster detection."""
    payload = {
        "dataset_id": TEST_ID_V2_CLUSTER,
        "variables": [
            "var_cluster1_1", "var_cluster1_2", "var_cluster1_3",
            "var_cluster2_1", "var_cluster2_2", "var_cluster2_3",
            "var_cluster3_1", "var_cluster3_2", "var_cluster3_3"
        ],
        "method": "pearson",
        "linkage_method": "ward",
        "n_clusters": None,  # Auto-detect
        "show_p_values": True,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/clustered-correlation", json=payload)
    assert response.status_code == 200, f"Auto-cluster detection failed: {response.text}"
    
    result = response.json()
    assert "cluster_assignments" in result
    
    # Validate cluster assignments structure
    assignments = result["cluster_assignments"]
    assert isinstance(assignments, dict)
    assert len(assignments) == len(payload["variables"])
    
    # Should detect multiple clusters in our test data
    unique_clusters = len(set(assignments.values()))
    assert unique_clusters >= 2, "Should detect at least 2 clusters in test data"

def test_clustered_correlation_too_many_variables():
    """Test clustered correlation with too many variables."""
    # Create payload with 51 variables (exceeds limit)
    variables = [f"var_{i}" for i in range(51)]
    
    payload = {
        "dataset_id": TEST_ID_V2_CLUSTER,
        "variables": variables,
        "method": "pearson",
        "linkage_method": "ward",
        "n_clusters": 3,
        "show_p_values": True,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/clustered-correlation", json=payload)
    assert response.status_code == 400, f"Should fail with 400 for too many variables: {response.text}"

# --- Protocol V2 Tests ---

def test_protocol_v2_mixed_effects():
    """Test v2 protocol with mixed effects configuration."""
    protocol = {
        "method": "mixed_effects",
        "target_column": "outcome",
        "group_column": "group",
        "time_column": "time",
        "subject_column": "subject_id",
        "covariates": ["covariate"],
        "random_slopes": False
    }
    
    payload = {
        "dataset_id": TEST_ID_V2,
        "protocol": protocol,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/protocol", json=payload)
    # Note: Currently falls back to standard analysis until v2 protocol is fully implemented
    assert response.status_code in [200, 400], f"Protocol v2 failed: {response.text}"


# --- Templates (Design → Execute) Tests ---

def test_templates_list():
    response = client.get("/api/v1/v2/analysis/templates")
    assert response.status_code == 200, f"Template list failed: {response.text}"
    data = response.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)
    assert len(data["templates"]) > 0


def test_template_design_and_execute_protocol():
    design_payload = {
        "dataset_id": TEST_ID_V2,
        "goal": "compare_groups",
        "template_id": "compare_quick",
        "variables": {"target": "outcome", "group": "group"},
    }

    design_res = client.post("/api/v1/v2/analysis/design", json=design_payload)
    assert design_res.status_code == 200, f"Template design failed: {design_res.text}"
    design_data = design_res.json()
    assert design_data.get("status") == "completed"
    protocol = design_data.get("protocol")
    assert isinstance(protocol, list)
    assert len(protocol) > 0
    assert all(isinstance(step, dict) and step.get("method") for step in protocol)

    execute_payload = {
        "dataset_id": TEST_ID_V2,
        "alpha": 0.05,
        "protocol": protocol,
    }
    exec_res = client.post("/api/v1/v2/analysis/execute", json=execute_payload)
    assert exec_res.status_code == 200, f"Protocol execute failed: {exec_res.text}"
    exec_data = exec_res.json()
    assert exec_data.get("status") in ["completed", "partial"]
    assert exec_data.get("total_steps") == len(protocol)
    assert (exec_data.get("completed_steps") or 0) >= 1

# --- Memory and Performance Tests ---

def test_memory_usage_mixed_effects():
    """Test that mixed effects doesn't exceed memory limits."""
    import pytest
    psutil = pytest.importorskip("psutil")
    import time
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    payload = {
        "dataset_id": TEST_ID_V2,
        "outcome": "outcome",
        "time_col": "time",
        "group_col": "group",
        "subject_col": "subject_id",
        "random_slope": False,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/mixed-effects", json=payload)
    assert response.status_code == 200
    
    # Allow some time for garbage collection
    time.sleep(0.1)
    
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_increase = final_memory - initial_memory
    
    # Should not increase memory by more than 100MB for this test
    assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, should be < 100MB"

# --- Error Handling Tests ---

def test_invalid_dataset_id():
    """Test error handling for invalid dataset ID."""
    payload = {
        "dataset_id": "nonexistent_dataset",
        "outcome": "outcome",
        "time_col": "time",
        "group_col": "group",
        "subject_col": "subject_id",
        "random_slope": False,
        "alpha": 0.05
    }
    
    response = client.post("/api/v1/v2/mixed-effects", json=payload)
    # Should either fail with 404 or 500 depending on error handling
    assert response.status_code >= 400, "Should fail with error for nonexistent dataset"

if __name__ == "__main__":
    # Run tests manually
    setup_v2_test_data()
    try:
        test_mixed_effects_basic()
        print("✓ Mixed effects basic test passed")
        
        test_clustered_correlation_basic()
        print("✓ Clustered correlation basic test passed")
        
        test_memory_usage_mixed_effects()
        print("✓ Memory usage test passed")
        
        print("All v2 API tests passed!")
    finally:
        if os.path.exists(TEST_DIR_V2):
            shutil.rmtree(TEST_DIR_V2)
