from io import BytesIO
from typing import Any, Dict, Optional

from app.modules.reporting import generate_protocol_docx_report


def create_results_document(results: Dict[str, Any], dataset_name: Optional[str] = None) -> BytesIO:
    ds_name = dataset_name or "Dataset"
    run_data: Dict[str, Any]

    if isinstance(results, dict) and isinstance(results.get("results"), dict):
        run_data = results
    else:
        run_data = {"protocol_name": "Results", "results": results if isinstance(results, dict) else {}}

    docx_bytes = generate_protocol_docx_report(run_data, dataset_name=ds_name)
    buffer = BytesIO()
    buffer.write(docx_bytes)
    buffer.seek(0)
    return buffer
