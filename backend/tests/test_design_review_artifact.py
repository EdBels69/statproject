import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import datasets as ds
from app.core.pipeline import PipelineManager


client = TestClient(app)


def test_design_review_artifact_confirm_revoke_endpoints(tmp_path, monkeypatch):
    dataset_id = "design_review_endpoint_ds"
    dataset_dir = os.path.join(str(tmp_path), dataset_id, "processed")
    os.makedirs(dataset_dir, exist_ok=True)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.get(f"/api/v1/datasets/{dataset_id}/design_review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed"] is False
    assert payload["artifact_exists"] is False

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/confirm",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "details": {"context": "test"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed"] is True
    assert payload["artifact_exists"] is True
    assert payload["confirmed_by"] == "qa-user"
    assert payload["confirmed_source"] == "frontend-test"

    artifact_path = os.path.join(str(tmp_path), dataset_id, "processed", "design_review.json")
    assert os.path.exists(artifact_path)
    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    assert artifact.get("confirmed") is True

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/revoke",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "reason": "mapping_changed",
            "details": {"context": "test"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["confirmed"] is False
    assert payload["artifact_exists"] is True
    assert payload["revoked_by"] == "qa-user"
    assert payload["revoke_reason"] == "mapping_changed"
    assert isinstance(payload.get("revoked_at"), str)
