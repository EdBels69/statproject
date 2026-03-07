"""
Tests for Protocol Execution (TASK-010)
"""

from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)

def test_protocol_execution_flow():
    """Test full protocol execution."""
    # 1. Upload dataset
    csv_content = "id,outcome,group\n1,10,A\n2,20,B\n3,15,A\n4,25,B\n5,12,A\n6,22,B"
    files = {"file": ("test_proto.csv", csv_content.encode(), "text/csv")}
    upl = client.post("/api/v1/datasets", files=files)
    assert upl.status_code == 200
    dataset_id = upl.json()["id"]

    # 2. Define Protocol
    protocol = {
        "name": "Test Protocol",
        "steps": [
            {
                "id": "step1_desc",
                "type": "descriptive_compare",
                "target": "outcome",
                "group": "group"
            },
            {
                "id": "step2_test",
                "type": "compare",
                "target": "outcome",
                "group": "group",
                "method": "t_test_independent"
            }
        ]
    }

    # 3. Run Protocol
    payload = {
        "dataset_id": dataset_id,
        "protocol": protocol,
        "alpha": 0.05
    }
    
    start_time = time.time()
    resp = client.post("/api/v1/analysis/protocol/run", json=payload)
    if resp.status_code != 200:
        print("Run Error:", resp.json())
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    run_id = data["run_id"]
    assert run_id is not None

    # 4. Verify Results retrieval
    # Endpoint: /api/v1/analysis/run/{run_id}?dataset_id=...
    res_resp = client.get(f"/api/v1/analysis/run/{run_id}", params={"dataset_id": dataset_id})
    assert res_resp.status_code == 200
    results = res_resp.json()
    
    # Check structure
    assert "results" in results
    steps_res = results["results"]
    assert "step1_desc" in steps_res
    assert "step2_test" in steps_res
    
    # Check content
    desc = steps_res["step1_desc"]
    assert desc["type"] == "table_1"
    
    test = steps_res["step2_test"]
    assert test["type"] == "compare"
    assert "p_value" in test
    
    print(f"Protocol executed in {time.time() - start_time:.2f}s")
