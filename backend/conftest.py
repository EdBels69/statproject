"""
Pytest configuration and fixtures for backend tests.
Memory-optimized for M1 8GB constraints.
"""

import pytest
import pandas as pd
import numpy as np
import os
import shutil
from fastapi.testclient import TestClient

from app.main import app
from app.api.datasets import DATA_DIR

# Test dataset IDs
TEST_ID_V2 = "test_dataset_v2_integration"
TEST_DIR_V2 = os.path.join(DATA_DIR, TEST_ID_V2)

@pytest.fixture(scope="session")
def test_client():
    """Test client fixture with memory management."""
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function", autouse=True)
def memory_cleanup():
    """Cleanup memory between tests to avoid OOM on M1 8GB."""
    import gc
    
    # Force garbage collection before test
    gc.collect()
    
    yield
    
    # Force garbage collection after test
    gc.collect()

@pytest.fixture(scope="module")
def mixed_effects_test_data():
    """Fixture for mixed effects test data."""
    np.random.seed(42)
    n_subjects = 10
    n_timepoints = 5
    n_groups = 2
    
    data = []
    for subject_id in range(1, n_subjects + 1):
        group = "A" if subject_id <= n_subjects // 2 else "B"
        for timepoint in range(1, n_timepoints + 1):
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

@pytest.fixture(scope="module")
def clustered_correlation_test_data():
    """Fixture for clustered correlation test data."""
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

@pytest.fixture(scope="function")
def setup_v2_test_environment(mixed_effects_test_data, clustered_correlation_test_data):
    """Setup test environment for v2 API tests."""
    # Create test directory
    if os.path.exists(TEST_DIR_V2):
        shutil.rmtree(TEST_DIR_V2)
    os.makedirs(os.path.join(TEST_DIR_V2, "raw"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR_V2, "processed"), exist_ok=True)
    
    # Save test data
    mixed_effects_test_data.to_parquet(os.path.join(TEST_DIR_V2, "processed", f"{TEST_ID_V2}_mixed.parquet"))
    clustered_correlation_test_data.to_parquet(os.path.join(TEST_DIR_V2, "processed", f"{TEST_ID_V2}_cluster.parquet"))
    
    # Create mock scan reports
    import json
    
    mixed_scan_report = {
        "columns": {
            "subject_id": {"type": "categorical"},
            "time": {"type": "numeric"},
            "group": {"type": "categorical"},
            "outcome": {"type": "numeric", "normality": {"is_normal": True}},
            "covariate": {"type": "numeric", "normality": {"is_normal": True}}
        }
    }
    
    cluster_scan_report = {
        "columns": {
            col: {"type": "numeric", "normality": {"is_normal": True}}
            for col in clustered_correlation_test_data.columns
        }
    }
    
    with open(os.path.join(TEST_DIR_V2, "processed", "scan_report_mixed.json"), "w") as f:
        json.dump(mixed_scan_report, f)
    
    with open(os.path.join(TEST_DIR_V2, "processed", "scan_report_cluster.json"), "w") as f:
        json.dump(cluster_scan_report, f)
    
    yield TEST_ID_V2
    
    # Cleanup
    if os.path.exists(TEST_DIR_V2):
        shutil.rmtree(TEST_DIR_V2)

# Mock for memory-intensive operations
@pytest.fixture
def mock_memory_intensive_operations():
    """Mock memory-intensive operations for testing."""
    from unittest.mock import patch
    
    with patch('app.api.v2.analysis_executor') as mock_executor:
        # Mock the executor to run in main thread for testing
        mock_executor.__enter__ = lambda self: None
        mock_executor.__exit__ = lambda self, *args: None
        
        def mock_run_in_executor(executor, func, *args):
            # Run in main thread for tests
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return func(*args)
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            yield

# Skip memory-intensive tests on CI or low-memory environments
def pytest_runtest_setup(item):
    """Skip memory-intensive tests in certain environments."""
    memory_intensive_markers = [mark for mark in item.iter_markers() if mark.name == 'memory_intensive']
    
    if memory_intensive_markers:
        # Check if we're in CI or low-memory environment
        if os.environ.get('CI') or os.environ.get('LOW_MEMORY'):
            pytest.skip("Skipping memory-intensive test in CI/low-memory environment")

# Custom markers
def pytest_configure(config):
    config.addinivalue_line("markers", "memory_intensive: mark test as memory-intensive")
    config.addinivalue_line("markers", "slow: mark test as slow-running")
    config.addinivalue_line("markers", "integration: mark test as integration test")