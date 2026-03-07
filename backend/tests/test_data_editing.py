"""
Tests for Data Editing Functionality (TASK-007)
"""

import pytest
from httpx import AsyncClient
import pandas as pd
import io
import warnings
from app.main import app

@pytest.mark.asyncio
async def test_update_cell():
    """Test updating a single cell value."""
    # 1. Upload dataset
    csv_content = "id,val,cat\n1,10,A\n2,20,B\n3,30,C"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
        response = await ac.post("/api/datasets", files=files)
        assert response.status_code == 200
        dataset_id = response.json()["id"]

        # 2. Modify cell (Row 1, Col 'val' -> 999)
        # Note: Row index is 0-based from dataframe
        action = {
            "type": "update_cell",
            "row_index": 1,
            "column": "val",
            "value": 999
        }
        
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", FutureWarning)
            mod_resp = await ac.post(f"/api/datasets/{dataset_id}/modify", json={
                "modification": {"actions": [action]}
            })
        assert mod_resp.status_code == 200
        incompatible_dtype = [
            w for w in caught
            if "incompatible dtype" in str(w.message).lower()
        ]
        assert not incompatible_dtype
        
        # 3. Verify change
        data_resp = await ac.get(f"/api/datasets/{dataset_id}?limit=100")
        assert data_resp.status_code == 200
        data = data_resp.json()
        
        # Row 1 in CSV (0-indexed) is id=2.
        # Check rows in data['head']
        # head might not be sorted by index, but verify if row with id=2 has 999
        
        rows = data["head"]
        target_row = next((r for r in rows if str(r.get("id")) == "2"), None)
        assert target_row is not None
        assert target_row["val"] == 999

@pytest.mark.asyncio
async def test_drop_row():
    """Test dropping a row."""
    csv_content = "id,val\n1,10\n2,20\n3,30"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        files = {"file": ("rows.csv", csv_content.encode(), "text/csv")}
        res = await ac.post("/api/datasets", files=files)
        did = res.json()["id"]
        
        # Drop row index 1 (id=2)
        action = {"type": "drop_row", "row_index": 1}
        await ac.post(f"/api/datasets/{did}/modify", json={"modification": {"actions": [action]}})
        
        # Verify
        res = await ac.get(f"/api/datasets/{did}")
        head = res.json()["head"]
        assert len(head) == 2
        ids = [int(r["id"]) for r in head]
        assert 2 not in ids

@pytest.mark.asyncio
async def test_drop_column():
    """Test dropping a column."""
    csv_content = "A,B,C\n1,2,3"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        files = {"file": ("cols.csv", csv_content.encode(), "text/csv")}
        res = await ac.post("/api/datasets", files=files)
        did = res.json()["id"]
        
        action = {"type": "drop_col", "column": "B"}
        await ac.post(f"/api/datasets/{did}/modify", json={"modification": {"actions": [action]}})
        
        res = await ac.get(f"/api/datasets/{did}")
        cols = [c["name"] for c in res.json()["columns"]]
        assert "A" in cols
        assert "C" in cols
        assert "B" not in cols
