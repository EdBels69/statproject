from io import BytesIO
from typing import Any, Dict, Optional

from app.modules.reporting import generate_protocol_docx_report
from app.modules.analysis_result_v2 import normalize_run_data_results


def create_results_document(
    results: Dict[str, Any],
    dataset_name: Optional[str] = None,
    style: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> BytesIO:
    ds_name = dataset_name or "Dataset"
    run_data: Dict[str, Any]

    if isinstance(results, dict) and isinstance(results.get("results"), dict):
        run_data = results
    else:
        payload = results if isinstance(results, dict) else {}

        looks_like_step_result = isinstance(payload, dict) and (
            "type" in payload or "p_value" in payload or "method" in payload
        )
        looks_like_steps_map = isinstance(payload, dict) and any(
            isinstance(v, dict) for v in payload.values()
        )

        if looks_like_step_result:
            run_data = {"protocol_name": "Results", "results": {"analysis": payload}}
        elif looks_like_steps_map:
            run_data = {"protocol_name": "Results", "results": payload}
        else:
            run_data = {"protocol_name": "Results", "results": {"analysis": payload}}

    run_data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})
    docx_bytes = generate_protocol_docx_report(run_data, dataset_name=ds_name, style=style, options=options)
    buffer = BytesIO()
    buffer.write(docx_bytes)
    buffer.seek(0)
    return buffer
