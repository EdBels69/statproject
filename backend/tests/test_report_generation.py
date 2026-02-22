"""
Tests for Report Generation (TASK-011)
"""

from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)

def test_docx_report_generation():
    """Test generating a DOCX report from a protocol run."""
    # 1. Upload dataset
    csv_content = "id,outcome,group\n1,10,A\n2,20,B\n3,15,A\n4,25,B\n5,12,A\n6,22,B"
    files = {"file": ("test_rep.csv", csv_content.encode(), "text/csv")}
    upl = client.post("/api/v1/datasets", files=files)
    assert upl.status_code == 200
    dataset_id = upl.json()["id"]

    # 2. Run Protocol
    protocol = {
        "name": "Report Test Protocol",
        "steps": [
            {
                "id": "step1",
                "type": "descriptive_compare",
                "target": "outcome",
                "group": "group"
            }
        ]
    }
    payload = {
        "dataset_id": dataset_id,
        "protocol": protocol,
        "alpha": 0.05
    }
    run_resp = client.post("/api/v1/analysis/protocol/run", json=payload)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    # 3. Request DOCX Report
    # Endpoint: /api/v1/analysis/protocol/report/{run_id}/docx
    # Params: dataset_id required
    start_time = time.time()
    rep_resp = client.get(
        f"/api/v1/analysis/protocol/report/{run_id}/docx",
        params={"dataset_id": dataset_id}
    )
    
    if rep_resp.status_code != 200:
        print("Report Error:", rep_resp.text)
        
    assert rep_resp.status_code == 200
    assert rep_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(rep_resp.content) > 0
    
    # Check filename in header
    assert "attachment; filename=" in rep_resp.headers["content-disposition"]
    
    print(f"Report generated in {time.time() - start_time:.2f}s, size: {len(rep_resp.content)} bytes")
