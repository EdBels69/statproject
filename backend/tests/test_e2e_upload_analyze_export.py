import sys
import os
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.api.datasets import DATA_DIR
import shutil
from io import BytesIO

client = TestClient(app)


def test_e2e_upload_analyze_export():
    print("=== E2E Test: Upload → Analyze → Export ===")
    
    # 1. Upload Dataset
    print("\n1. UPLOAD: Uploading test dataset...")
    df = pd.DataFrame({
        "Group": ["A"]*30 + ["B"]*30,
        "Value": np.concatenate([np.random.normal(10, 2, 30), np.random.normal(12, 2, 30)])
    })
    
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    
    files = {"file": ("test_data.csv", csv_buffer, "text/csv")}
    upload_resp = client.post("/api/v1/datasets", files=files)
    
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    dataset_id = upload_resp.json()["id"]
    print(f"   ✓ Dataset uploaded: {dataset_id}")
    
    # 2. Analyze (Design Protocol)
    print("\n2. ANALYZE: Designing analysis protocol...")
    design_payload = {
        "dataset_id": dataset_id,
        "goal": "compare_groups",
        "variables": {"target": "Value", "group": "Group"}
    }
    design_resp = client.post("/api/v1/analysis/design", json=design_payload)
    
    assert design_resp.status_code == 200, f"Design failed: {design_resp.text}"
    protocol = design_resp.json()
    print(f"   ✓ Protocol generated: {len(protocol['steps'])} steps")
    
    # 3. Execute Analysis
    print("\n3. ANALYZE: Running analysis protocol...")
    run_payload = {
        "dataset_id": dataset_id,
        "protocol": protocol
    }
    run_resp = client.post("/api/v1/analysis/protocol/run", json=run_payload)
    
    assert run_resp.status_code == 200, f"Run failed: {run_resp.text}"
    run_id = run_resp.json()["run_id"]
    print(f"   ✓ Analysis completed: {run_id}")
    
    # 4. Fetch Results
    print("\n4. ANALYZE: Fetching results...")
    res_resp = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
    
    assert res_resp.status_code == 200, f"Fetch results failed: {res_resp.text}"
    results = res_resp.json()
    print(f"   ✓ Results fetched: {len(results['results'])} steps completed")

    print("\n4b. EXPORT: Downloading DOCX via export endpoint...")
    export_docx_resp = client.post(
        "/api/v1/analysis/export/docx",
        json={"dataset_name": dataset_id, "results": results, "filename": "results.docx"},
    )
    assert export_docx_resp.status_code == 200, f"DOCX export failed: {export_docx_resp.text}"
    assert export_docx_resp.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    docx_content = export_docx_resp.content
    assert len(docx_content) > 500, "DOCX export too small"
    assert docx_content[:2] == b"PK", "DOCX header missing"
    print(f"   ✓ DOCX exported: {len(docx_content)} bytes")
    
    # Verify analysis quality
    hypothesis_key = None
    for key in results['results'].keys():
        if 'hypothesis' in key.lower() or 'compare' in key.lower():
            hypothesis_key = key
            break
    
    assert hypothesis_key is not None, "No hypothesis test result found"
    step_res = results['results'][hypothesis_key]
    
    assert 'p_value' in step_res, "P-value missing from results"
    assert 'conclusion' in step_res, "Conclusion missing from results"
    print(f"   ✓ P-value: {step_res['p_value']:.4f}")
    print(f"   ✓ Significant: {step_res.get('significant', False)}")
    
    # 5. Export Report
    print("\n5. EXPORT: Downloading report...")
    export_resp = client.get(f"/api/v1/analysis/report/{dataset_id}?target_col=Value&group_col=Group")
    
    assert export_resp.status_code == 200, f"Export failed: {export_resp.text}"
    report_content = export_resp.content
    print(f"   ✓ Report exported: {len(report_content)} bytes")
    
    # Verify report format
    assert len(report_content) > 0, "Report is empty"
    assert b"<html" in report_content or b"PDF" in report_content, "Report format unexpected"
    print("   ✓ Report format verified")

    print("\n6. EXPORT: Downloading PDF report...")
    pdf_resp = client.get(f"/api/v1/analysis/report/{dataset_id}/pdf?target_col=Value&group_col=Group")
    assert pdf_resp.status_code == 200, f"PDF export failed: {pdf_resp.text}"
    assert pdf_resp.headers.get("content-type", "").startswith("application/pdf")
    pdf_content = pdf_resp.content
    assert len(pdf_content) > 1000, "PDF report too small"
    assert pdf_content[:4] == b"%PDF", "PDF header missing"
    print(f"   ✓ PDF report exported: {len(pdf_content)} bytes")

    print("\n7. EXPORT: Downloading protocol PDF report...")
    protocol_pdf_resp = client.get(f"/api/v1/analysis/protocol/report/{run_id}/pdf?dataset_id={dataset_id}")
    assert protocol_pdf_resp.status_code == 200, f"Protocol PDF export failed: {protocol_pdf_resp.text}"
    assert protocol_pdf_resp.headers.get("content-type", "").startswith("application/pdf")
    protocol_pdf = protocol_pdf_resp.content
    assert len(protocol_pdf) > 1000, "Protocol PDF too small"
    assert protocol_pdf[:4] == b"%PDF", "Protocol PDF header missing"
    print(f"   ✓ Protocol PDF exported: {len(protocol_pdf)} bytes")

    print("\n8. EXPORT: Downloading protocol DOCX report...")
    protocol_docx_resp = client.get(f"/api/v1/analysis/protocol/report/{run_id}/docx?dataset_id={dataset_id}")
    assert protocol_docx_resp.status_code == 200, f"Protocol DOCX export failed: {protocol_docx_resp.text}"
    assert protocol_docx_resp.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    protocol_docx = protocol_docx_resp.content
    assert len(protocol_docx) > 500, "Protocol DOCX too small"
    assert protocol_docx[:2] == b"PK", "DOCX header missing"
    print(f"   ✓ Protocol DOCX exported: {len(protocol_docx)} bytes")
    
    # 9. Cleanup
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if os.path.exists(ds_dir):
        shutil.rmtree(ds_dir)
    print("\n=== E2E Test PASSED ===\n")


if __name__ == "__main__":
    test_e2e_upload_analyze_export()
