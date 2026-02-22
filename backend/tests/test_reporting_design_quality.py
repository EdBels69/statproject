import io
import os
import sys
import tempfile

from docx import Document

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting import generate_protocol_docx_report, render_protocol_report


def test_render_protocol_report_adds_design_warning_when_study_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)

        run_data = {
            "dataset_id": "dataset_no_design",
            "results": {},
        }
        html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

        assert 'id="design"' in html
        assert "Предупреждение" in html
        assert "Секция дизайна" in html


def test_generate_protocol_docx_report_adds_design_warning_when_study_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)

        run_data = {
            "dataset_id": "dataset_no_design",
            "results": {},
            "protocol_name": "Protocol",
        }
        payload = generate_protocol_docx_report(run_data, dataset_name="Demo", style="gost")
        doc = Document(io.BytesIO(payload))
        text = "\n".join([p.text for p in doc.paragraphs if p.text])

        assert "Дизайн исследования" in text
        assert "Предупреждение" in text
        assert "Раздел Design неполный" in text
