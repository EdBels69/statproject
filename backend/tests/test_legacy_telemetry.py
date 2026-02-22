import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules import legacy_telemetry as lt


def test_legacy_telemetry_records_and_persists(tmp_path, monkeypatch):
    out_path = tmp_path / "legacy_telemetry.json"
    monkeypatch.setattr(lt.settings, "CLINIMETRIA_LEGACY_TELEMETRY_PATH", str(out_path))

    lt.reset_legacy_telemetry()
    lt.record_legacy_hit("/api/v1/analysis/design")
    lt.record_legacy_hit("/api/v1/analysis/design")
    lt.record_legacy_hit("/api/v1/v2/ai/analyze-design")

    snap = lt.get_legacy_snapshot()
    assert snap["total_hits"] == 3
    assert isinstance(snap.get("endpoints"), list)

    by_endpoint = {item["endpoint"]: item for item in snap["endpoints"]}
    assert by_endpoint["/api/v1/analysis/design"]["count"] == 2
    assert by_endpoint["/api/v1/v2/ai/analyze-design"]["count"] == 1
    assert out_path.exists()

    with open(out_path, "r", encoding="utf-8") as f:
        persisted = json.load(f)
    assert persisted.get("total_hits") == 3

    lt.reset_legacy_telemetry()
