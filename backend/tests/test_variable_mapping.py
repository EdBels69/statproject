"""
Tests for Variable Workspace (TASK-008)
"""

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_variable_mapping_flow():
    """Test get and put variable mapping."""
    # 1. Upload dataset
    csv_content = "id,age,group\n1,20,A\n2,30,B\n3,40,A"
    files = {"file": ("test_vars.csv", csv_content.encode(), "text/csv")}
    response = client.post("/api/v1/datasets", files=files)
    assert response.status_code == 200
    dataset_id = response.json()["id"]

    # 2. Get initial mapping (should be empty or default)
    resp = client.get(f"/api/v1/datasets/{dataset_id}/variable_mapping")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] == dataset_id
    # mapping might be empty initially
    
    # 3. Update mapping
    # Let's say we want to set 'age' role to 'outcome'
    new_mapping = {
        "age": {
            "role": "outcome",
            "display_name": "Age Years",
            "include_descriptive": True
        },
        "group": {
            "role": "group",
            "group_var": True
        }
    }
    
    resp = client.put(f"/api/v1/datasets/{dataset_id}/variable_mapping", json={"mapping": new_mapping})
    assert resp.status_code == 200
    updated_data = resp.json()
    assert updated_data["mapping"]["age"]["role"] == "outcome"
    assert updated_data["mapping"]["age"]["display_name"] == "Age Years"

    # 4. Verify persistency
    resp = client.get(f"/api/v1/datasets/{dataset_id}/variable_mapping")
    assert resp.status_code == 200
    final_data = resp.json()
    assert final_data["mapping"]["age"]["role"] == "outcome"
    
    # 5. Check if semantics updated (optional but good)
    # semantics uses variable_mapping to determine roles
    sem_resp = client.get(f"/api/v1/datasets/{dataset_id}/semantics")
    if sem_resp.status_code == 200:
        sem = sem_resp.json()
        # 'age' should be in outcome_candidates or have role=outcome
        col_meta = sem["columns"].get("age", {})
        assert col_meta.get("role") == "outcome"
