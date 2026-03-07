"""
Tests for Protocol Templates (TASK-009)
"""

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_list_templates():
    """Test standard template listing."""
    resp = client.get("/api/v1/analysis/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    templates = data["templates"]
    assert len(templates) > 0
    # Check for known template
    assert any(t["id"] == "compare_full" for t in templates)

def test_suggest_design_from_template():
    """Test generating a protocol from a template."""
    # 1. Upload a dummy dataset first
    csv_content = "id,outcome,group\n1,10,A\n2,20,B\n3,15,A"
    files = {"file": ("test_templ.csv", csv_content.encode(), "text/csv")}
    upl = client.post("/api/v1/datasets", files=files)
    dataset_id = upl.json()["id"]

    # 2. Call suggest_design
    payload = {
        "dataset_id": dataset_id,
        "goal": "compare_groups",
        "template_id": "compare_full",
        "variables": {
            "target": "outcome",
            "group": "group"
        }
    }
    resp = client.post("/api/v1/analysis/design", json=payload)
    if resp.status_code != 200:
        print(resp.json())
    assert resp.status_code == 200
    protocol = resp.json()
    
    assert protocol["name"] is not None
    assert len(protocol["steps"]) > 0
    # compare_full should have 'desc_stats' and 'hypothesis_test'
    step_ids = [s["id"] for s in protocol["steps"]]
    assert "desc_stats" in step_ids
    assert "hypothesis_test" in step_ids
