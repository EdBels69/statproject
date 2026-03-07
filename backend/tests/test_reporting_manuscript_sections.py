import io
import os
import sys
import tempfile
import zipfile

from docx import Document

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting import generate_protocol_docx_report, render_protocol_report


def _simple_run_data() -> dict:
    return {
        "dataset_id": "report_sections_ds",
        "alpha": 0.05,
        "results": {
            "step_compare": {
                "type": "hypothesis_test",
                "method": {"id": "t_test_ind", "name": "Independent t-test"},
                "method_id": "t_test_ind",
                "p_value": 0.01,
                "stat_value": 2.45,
                "effect_size": 0.62,
                "plot_stats": {
                    "A": {"count": 20, "mean": 10.1, "sd": 1.1, "median": 10.0, "q1": 9.4, "q3": 10.8},
                    "B": {"count": 20, "mean": 11.2, "sd": 1.0, "median": 11.1, "q1": 10.5, "q3": 11.8},
                },
                "conclusion": "Group means differ significantly.",
            }
        },
    }


def test_render_protocol_report_includes_methods_results_and_limitations(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        html = render_protocol_report(_simple_run_data(), dataset_name="Demo", style="apa7")

    assert 'id="methods"' in html
    assert 'id="results"' in html
    assert 'id="limitations"' in html
    assert "Methods" in html
    assert "Results" in html
    assert "Limitations" in html
    assert "Independent t-test" in html


def test_generate_protocol_docx_report_includes_methods_and_limitations(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        payload = generate_protocol_docx_report(_simple_run_data(), dataset_name="Demo", style="apa7")

    doc = Document(io.BytesIO(payload))
    text = "\n".join([p.text for p in doc.paragraphs if p.text])

    assert "Methods" in text
    assert "Limitations" in text
    assert "Statistical Analysis Results" in text


def test_generate_protocol_docx_report_contains_internal_step_links(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        payload = generate_protocol_docx_report(_simple_run_data(), dataset_name="Demo", style="apa7")

    with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
        doc_xml = archive.read("word/document.xml").decode("utf-8")

    assert 'w:bookmarkStart' in doc_xml
    assert 'w:name="step_step_compare"' in doc_xml
    assert 'w:hyperlink w:anchor="step_step_compare"' in doc_xml
