import pandas as pd
import numpy as np
import json
import pytest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.sampler import DataSampler

def test_sampler_large_dataset():
    # 1. Generate Fake Large Data (10,000 rows)
    rows = 10000
    df = pd.DataFrame({
        "id": range(rows),
        "category": np.random.choice(["A", "B", "C", "D"], rows),
        "value_normal": np.random.normal(100, 15, rows),
        "value_outlier": np.random.exponential(10, rows)
    })
    
    # Inject an outlier
    df.loc[0, "value_normal"] = 9999.99

    # 2. Create Context
    context_str = DataSampler.create_llm_context(df)
    
    # 3. Verify Output
    print(f"Context Length (chars): {len(context_str)}")
    
    # Should be relatively small despite 10k rows
    assert len(context_str) < 5000, "Context is too large!"
    
    # Should contain summary
    assert "DATASET SUMMARY" in context_str
    assert "10000" in context_str # Row count
    
    # Should contain outlier info (Max/Min)
    assert "9999.99" in context_str
    
    # Should contain Head and Tail, but NOT the middle
    assert "9999" in context_str # Last ID
    assert "5000" not in context_str # Middle ID shouldn't be in the snippet
    
    print("Sampler Test Passed: Large dataset reduced successfully.")

if __name__ == "__main__":
    test_sampler_large_dataset()
