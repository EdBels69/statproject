"""
Tests for Data Editing Functionality (TASK-007) - Synchronous Version
"""

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_update_cell_sync():
    """Test updating a single cell value."""
    # 1. Upload dataset
    csv_content = "id,val,cat\n1,10,A\n2,20,B\n3,30,C"
    files = {"file": ("test_sync.csv", csv_content.encode(), "text/csv")}
    response = client.post("/api/v1/datasets", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    dataset_id = response.json()["id"]

    # 2. Modify cell (Row 1, Col 'val' -> 999)
    # Row index is 0-based. Row 1 is the second row (id=2)
    action = {
        "type": "update_cell",
        "row_index": 1,
        "column": "val",
        "value": 999
    }
    
    mod_resp = client.post(f"/api/v1/datasets/{dataset_id}/modify", json={
        "actions": [action]
    })
    assert mod_resp.status_code == 200, f"Modify failed: {mod_resp.text}"
    
    # 3. Verify change
    data_resp = client.get(f"/api/v1/datasets/{dataset_id}?limit=100")
    assert data_resp.status_code == 200
    data = data_resp.json()
    
    rows = data["head"]
    # Looking for row where id=2. It should have index 1 if order preserved.
    # But let's find it explicitly.
    target_row = next((r for r in rows if str(r.get("id")) == "2"), None)
    assert target_row is not None
    assert target_row["val"] == 999

def test_drop_row_sync():
    """Test dropping a row."""
    csv_content = "id,val\n1,10\n2,20\n3,30"
    files = {"file": ("rows_sync.csv", csv_content.encode(), "text/csv")}
    res = client.post("/api/v1/datasets", files=files)
    did = res.json()["id"]
    
    # Drop row index 1 (id=2)
    action = {"type": "drop_row", "row_index": 1}
    client.post(f"/api/v1/datasets/{did}/modify", json={"actions": [action]})
    
    # Verify
    res = client.get(f"/api/v1/datasets/{did}")
    head = res.json()["head"]
    assert len(head) == 2
    ids = [int(r["id"]) for r in head]
    assert 2 not in ids

def test_drop_column_sync():
    """Test dropping a column."""
    csv_content = "A,B,C\n1,2,3"
    files = {"file": ("cols_sync.csv", csv_content.encode(), "text/csv")}
    res = client.post("/api/v1/datasets", files=files)
    did = res.json()["id"]
    
    action = {"type": "drop_col", "column": "B"}
    client.post(f"/api/v1/datasets/{did}/modify", json={"actions": [action]})
    
    res = client.get(f"/api/v1/datasets/{did}")
    cols = [c["name"] for c in res.json()["columns"]]
    assert "A" in cols
    assert "C" in cols
    assert "B" not in cols
