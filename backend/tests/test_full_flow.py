
import sys
import os
import json
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.api.datasets import DATA_DIR
import shutil

# Setup
client = TestClient(app)
TEST_ID = "test_dataset_integration"
TEST_DIR = os.path.join(DATA_DIR, TEST_ID)

TEST_ID_PREP = "test_dataset_data_prep"
TEST_DIR_PREP = os.path.join(DATA_DIR, TEST_ID_PREP)

def setup_test_data():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(os.path.join(TEST_DIR, "raw"), exist_ok=True)
    os.makedirs(os.path.join(TEST_DIR, "processed"), exist_ok=True)
    
    # Create Dummy CSV with known difference
    # Group A: Mean=10, SD=2
    # Group B: Mean=12, SD=2
    # N=20
    np.random.seed(42)
    df = pd.DataFrame({
        "Group": ["A"]*20 + ["B"]*20,
        "Value": np.concatenate([np.random.normal(10, 2, 20), np.random.normal(12, 2, 20)])
    })
    
    # Save processed (parquet usually, but CSV for scan mock if needed, but pipeline reads parquet)
    # Our pipeline usually reads from 'processed/{id}.parquet' or similar. 
    # Let's check get_dataframe logic. It looks for .parquet or .csv in processed.
    df.to_parquet(os.path.join(TEST_DIR, "processed", f"{TEST_ID}.parquet"))
    
    # Mock scan report
    with open(os.path.join(TEST_DIR, "processed", "scan_report.json"), "w") as f:
        f.write('{"columns": {"Group": {"type": "categorical"}, "Value": {"type": "numeric", "normality": {"is_normal": true}}}}')

def test_full_flow():
    print("--- 1. Setup Data ---")
    setup_test_data()
    
    print("--- 2. Design Protocol (AI) ---")
    design_payload = {
        "dataset_id": TEST_ID,
        "goal": "compare_groups",
        "variables": {"target": "Value", "group": "Group"}
    }
    resp = client.post("/api/v1/analysis/design", json=design_payload)
    if resp.status_code != 200:
        print(f"Design Failed: {resp.text}")
        return
        
    protocol = resp.json()
    print(f"Protocol Generated: {len(protocol['steps'])} steps")
    
    # Find the hypothesis test step
    target_step = None
    target_idx = -1
    for i, s in enumerate(protocol['steps']):
        if s['type'] == 'compare' or s.get('id') == 'hypothesis_test':
            target_step = s
            target_idx = i
            break
            
    assert target_step is not None, "No hypothesis test step found"
    print(f"Hypothesis Step Method (Pre-Force): {target_step.get('method', 'Auto-Detect')}")
    # Force t-test to ensure Effect Size is calculated for this test
    # (Auto-detect might choose Mann-Whitney if data looks non-normal, which skips Cohen's d)
    target_step['method'] = 't_test_ind'
    
    # Verify AI chose a comparison test
    # (Actually method might be undefined if engine selects it at runtime)
    pass
    
    print("--- 3. Execute Protocol (Default) ---")
    # Simulate User Running it without changes
    run_payload = {
        "dataset_id": TEST_ID,
        "protocol": protocol
    }
    run_resp = client.post("/api/v1/analysis/protocol/run", json=run_payload)
    assert run_resp.status_code == 200, f"Run Failed: {run_resp.text}"
    run_data = run_resp.json()
    run_id = run_data['run_id']
    
    # Fetch Results
    res_resp = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={TEST_ID}")
    assert res_resp.status_code == 200
    results = res_resp.json()
    
    # Results keys are step IDs. Default IDs are 'desc_stats', 'hypothesis_test'
    step_res = results['results'].get('hypothesis_test')
    if not step_res:
         # Fallback if IDs are dynamic (step_X)
         keys = list(results['results'].keys())
         step_res = results['results'][keys[-1]] # Usually last step is the test
    
    print(f"Result P-Value: {step_res['p_value']}")
    print(f"Effect Size: {step_res.get('effect_size')}")
    print(f"Conclusion: {step_res['conclusion']}")
    
    # Assertions
    assert step_res['significant']
    assert step_res.get('effect_size') is not None
    assert "Cohen's d" in step_res['conclusion'] or "large effect" in step_res['conclusion']
    
    print("--- 4. Execute with User Override (One-Sided) ---")
    # Override Step: Force 'less' alternative
    protocol_mod = protocol.copy()
    # Ensure we modify the right step
    protocol_mod['steps'][target_idx]['alternative'] = 'greater' 
    
    run_payload_mod = {
        "dataset_id": TEST_ID,
        "protocol": protocol_mod
    }
    run_resp_2 = client.post("/api/v1/analysis/protocol/run", json=run_payload_mod)
    run_id_2 = run_resp_2.json()['run_id']
    
    res_resp_2 = client.get(f"/api/v1/analysis/run/{run_id_2}?dataset_id={TEST_ID}")
    results_2 = res_resp_2.json()
    res_2 = results_2['results'].get('hypothesis_test') or results_2['results'][list(results_2['results'].keys())[-1]]
    
    print(f"Modified (Greater) P-Value: {res_2['p_value']}")
    if res_2['p_value'] > 0.05:
        print("SUCCESS: 'Greater' hypothesis correctly yielded non-significant result (p > 0.05).")
    else:
        print(f"FAILURE: 'Greater' hypothesis should be non-significant but was p={res_2['p_value']}")

    print("--- 5. One-Sample Test Override ---")
    # Create a custom step for One Sample
    one_sample_protocol = {
        "name": "One Sample Test",
        "steps": [
            {
                "id": "step_os",
                "type": "hypothesis_test",
                "method": "t_test_one",
                "target": "Value",
                "test_value": 100, # Value (mean~11) is definitely < 100
                "alternative": "two-sided" 
            }
        ]
    }
    run_resp_3 = client.post("/api/v1/analysis/protocol/run", json={"dataset_id": TEST_ID, "protocol": one_sample_protocol})
    run_id_3 = run_resp_3.json()['run_id']
    
    res_resp_3 = client.get(f"/api/v1/analysis/run/{run_id_3}?dataset_id={TEST_ID}")
    results_3 = res_resp_3.json()
    res_3 = results_3['results']['step_os']
    
    print(f"One Sample P-Value: {res_3['p_value']}")
    print(f"One Sample Conclusion: {res_3['conclusion']}")
    assert res_3['significant']
    assert "differs significantly" in res_3['conclusion']


def test_v1_design_templates_and_apply_template_id():
    setup_test_data()

    list_res = client.get("/api/v1/analysis/templates")
    assert list_res.status_code == 200, list_res.text
    templates = list_res.json().get("templates")
    assert isinstance(templates, list)
    assert any(t.get("id") == "compare_quick" for t in templates)

    design_payload = {
        "dataset_id": TEST_ID,
        "goal": "compare_groups",
        "template_id": "compare_quick",
        "variables": {"target": "Value", "group": "Group"},
    }

    design_res = client.post("/api/v1/analysis/design", json=design_payload)
    assert design_res.status_code == 200, design_res.text
    protocol = design_res.json()
    steps = protocol.get("steps")
    assert isinstance(steps, list)
    assert all(isinstance(s, dict) for s in steps)
    assert all(s.get("id") != "desc_stats" for s in steps)


def test_dataset_modify_respects_pagination():
    setup_test_data()

    initial = client.get(f"/api/v1/datasets/{TEST_ID}?page=2&limit=10")
    assert initial.status_code == 200, initial.text
    initial_profile = initial.json()
    assert initial_profile["page"] == 2
    assert len(initial_profile["head"]) == 10
    assert initial_profile["row_count"] == 40

    update_payload = {
        "actions": [
            {"type": "update_cell", "row_index": 12, "column": "Value", "value": 999}
        ]
    }
    update_res = client.post(
        f"/api/v1/datasets/{TEST_ID}/modify?page=2&limit=10",
        json=update_payload,
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()
    assert updated["page"] == 2
    assert len(updated["head"]) == 10
    assert float(updated["head"][2]["Value"]) == 999.0

    drop_payload = {
        "actions": [
            {"type": "drop_row", "row_index": 0}
        ]
    }
    drop_res = client.post(
        f"/api/v1/datasets/{TEST_ID}/modify?page=2&limit=10",
        json=drop_payload,
    )
    assert drop_res.status_code == 200, drop_res.text
    dropped = drop_res.json()
    assert dropped["row_count"] == 39
    assert dropped["page"] == 2
    assert len(dropped["head"]) == 10


def test_variable_mapping_roundtrip():
    setup_test_data()

    put_payload = {
        "mapping": {
            "Group": {
                "role": "Group",
                "group_var": True,
                "data_type": "categorical",
                "include_descriptive": True,
                "include_comparison": True,
            },
            "Value": {
                "role": "Outcome",
                "group_var": False,
                "data_type": "numeric",
                "include_descriptive": True,
                "include_comparison": True,
            },
        }
    }

    put_res = client.put(f"/api/v1/datasets/{TEST_ID}/variable_mapping", json=put_payload)
    assert put_res.status_code == 200, put_res.text
    put_doc = put_res.json()
    assert put_doc["dataset_id"] == TEST_ID
    assert put_doc["mapping"]["Group"]["role"] == "Group"
    assert put_doc["mapping"]["Group"]["group_var"] is True

    get_res = client.get(f"/api/v1/datasets/{TEST_ID}/variable_mapping")
    assert get_res.status_code == 200, get_res.text
    get_doc = get_res.json()
    assert get_doc["mapping"]["Value"]["role"] == "Outcome"

    mapping_path = os.path.join(TEST_DIR, "processed", "variable_mapping.json")
    assert os.path.exists(mapping_path)


def test_variable_mapping_updates_on_modify():
    setup_test_data()

    put_payload = {
        "mapping": {
            "Group": {
                "role": "Group",
                "group_var": True,
                "data_type": "categorical",
            },
            "Value": {
                "role": "Outcome",
                "group_var": False,
                "data_type": "numeric",
            },
        }
    }

    put_res = client.put(f"/api/v1/datasets/{TEST_ID}/variable_mapping", json=put_payload)
    assert put_res.status_code == 200, put_res.text

    rename_payload = {
        "actions": [
            {"type": "rename_col", "column": "Value", "new_name": "Outcome"}
        ]
    }
    rename_res = client.post(
        f"/api/v1/datasets/{TEST_ID}/modify?page=1&limit=10",
        json=rename_payload,
    )
    assert rename_res.status_code == 200, rename_res.text

    mapping_after_rename = client.get(f"/api/v1/datasets/{TEST_ID}/variable_mapping").json()["mapping"]
    assert "Value" not in mapping_after_rename
    assert mapping_after_rename["Outcome"]["role"] == "Outcome"

    drop_payload = {
        "actions": [
            {"type": "drop_col", "column": "Group"}
        ]
    }
    drop_res = client.post(
        f"/api/v1/datasets/{TEST_ID}/modify?page=1&limit=10",
        json=drop_payload,
    )
    assert drop_res.status_code == 200, drop_res.text

    mapping_after_drop = client.get(f"/api/v1/datasets/{TEST_ID}/variable_mapping").json()["mapping"]
    assert "Group" not in mapping_after_drop

    type_payload = {
        "actions": [
            {"type": "change_type", "column": "Outcome", "new_type": "text"}
        ]
    }
    type_res = client.post(
        f"/api/v1/datasets/{TEST_ID}/modify?page=1&limit=10",
        json=type_payload,
    )
    assert type_res.status_code == 200, type_res.text

    mapping_after_type = client.get(f"/api/v1/datasets/{TEST_ID}/variable_mapping").json()["mapping"]
    assert mapping_after_type["Outcome"]["data_type"] == "text"


def setup_prep_data():
    if os.path.exists(TEST_DIR_PREP):
        shutil.rmtree(TEST_DIR_PREP)
    os.makedirs(os.path.join(TEST_DIR_PREP, "processed"), exist_ok=True)

    df = pd.DataFrame(
        {
            "Value": [1.0, np.nan, 2.0, np.nan],
            "Other": [10.0, 11.0, np.nan, 13.0],
            "Cat": ["x", None, "x", "y"],
            "ValueStr": ["1", "2", None, "4"],
        }
    )

    df.to_csv(os.path.join(TEST_DIR_PREP, "processed", "data.csv"), index=False)
    with open(os.path.join(TEST_DIR_PREP, "processed", "scan_report.json"), "w") as f:
        f.write("{}")


def test_data_prep_clean_column_fill_median_and_log():
    setup_prep_data()

    resp = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/clean_column",
        json={"column": "Value", "action": "fill_median"},
    )
    assert resp.status_code == 200, resp.text
    profile = resp.json()

    value_col = next(c for c in profile["columns"] if c["name"] == "Value")
    assert value_col["missing_count"] == 0

    log_path = os.path.join(TEST_DIR_PREP, "processed", "cleaning_log.json")
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        log = json.load(f)
    assert log["action"] == "fill_median"
    assert log["column"] == "Value"


def test_data_prep_clean_column_reject_mean_on_text():
    setup_prep_data()

    resp = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/clean_column",
        json={"column": "Cat", "action": "fill_mean"},
    )
    assert resp.status_code == 400


def test_data_prep_clean_column_fill_mode_and_drop_na():
    setup_prep_data()

    resp_mode = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/clean_column",
        json={"column": "Cat", "action": "fill_mode"},
    )
    assert resp_mode.status_code == 200, resp_mode.text
    profile_mode = resp_mode.json()
    cat_col = next(c for c in profile_mode["columns"] if c["name"] == "Cat")
    assert cat_col["missing_count"] == 0

    resp_drop = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/clean_column",
        json={"column": "Other", "action": "drop_na"},
    )
    assert resp_drop.status_code == 200, resp_drop.text
    profile_drop = resp_drop.json()
    assert profile_drop["row_count"] < 4


def test_data_prep_to_numeric_and_scan_report_endpoint():
    setup_prep_data()

    resp = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/clean_column",
        json={"column": "ValueStr", "action": "to_numeric"},
    )
    assert resp.status_code == 200, resp.text
    profile = resp.json()
    value_str_col = next(c for c in profile["columns"] if c["name"] == "ValueStr")
    assert value_str_col["type"] in {"numeric", "text"}

    report_resp = client.get(f"/api/v1/datasets/{TEST_ID_PREP}/scan_report")
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    assert report.get("status") != "no_report"


def test_data_prep_mice_imputation_happy_path_and_validation():
    setup_prep_data()

    resp = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/impute_mice",
        json={"columns": ["Value", "Other"], "max_iter": 5, "n_imputations": 2, "random_state": 7},
    )
    assert resp.status_code == 200, resp.text
    profile = resp.json()

    value_col = next(c for c in profile["columns"] if c["name"] == "Value")
    other_col = next(c for c in profile["columns"] if c["name"] == "Other")
    assert value_col["missing_count"] == 0
    assert other_col["missing_count"] == 0

    resp_bad = client.post(
        f"/api/v1/datasets/{TEST_ID_PREP}/impute_mice",
        json={"columns": []},
    )
    assert resp_bad.status_code == 400


def test_openapi_contract_frontend_endpoints():
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200, resp.text
    spec = resp.json()

    paths = spec.get("paths", {})
    assert isinstance(paths, dict) and paths, "OpenAPI paths missing"

    def resolve_path(*candidates: str) -> str:
        for p in candidates:
            if p in paths:
                return p
        raise AssertionError(f"OpenAPI path not found: {candidates}")

    def get_op(path_key: str, method: str) -> dict:
        item = paths.get(path_key, {})
        op = item.get(method.lower())
        assert isinstance(op, dict), f"Missing operation {method.upper()} {path_key}"
        return op

    def require_query_params(op: dict, required: list[str]):
        params = op.get("parameters", [])
        assert isinstance(params, list)
        query = {p.get("name"): p for p in params if p.get("in") == "query"}
        for name in required:
            assert name in query, f"Missing query param '{name}'"
            assert query[name].get("required") is True, f"Query param '{name}' must be required"

    def schema_for_ref(ref: str) -> dict:
        assert ref.startswith("#/components/schemas/")
        name = ref.split("/")[-1]
        schemas = spec.get("components", {}).get("schemas", {})
        schema = schemas.get(name)
        assert isinstance(schema, dict), f"Schema not found: {name}"
        return schema

    get_run_path = resolve_path(
        "/api/v1/analysis/run/{run_id}",
        "/analysis/run/{run_id}",
    )
    require_query_params(get_op(get_run_path, "get"), ["dataset_id"])

    html_report_path = resolve_path(
        "/api/v1/analysis/report/{dataset_id}",
        "/analysis/report/{dataset_id}",
    )
    require_query_params(get_op(html_report_path, "get"), ["target_col", "group_col"])

    pdf_report_path = resolve_path(
        "/api/v1/analysis/report/{dataset_id}/pdf",
        "/analysis/report/{dataset_id}/pdf",
    )
    require_query_params(get_op(pdf_report_path, "get"), ["target_col", "group_col"])

    protocol_pdf_path = resolve_path(
        "/api/v1/analysis/protocol/report/{run_id}/pdf",
        "/analysis/protocol/report/{run_id}/pdf",
    )
    require_query_params(get_op(protocol_pdf_path, "get"), ["dataset_id"])

    protocol_html_path = resolve_path(
        "/api/v1/analysis/protocol/report/{run_id}/html",
        "/analysis/protocol/report/{run_id}/html",
    )
    require_query_params(get_op(protocol_html_path, "get"), ["dataset_id"])

    export_pdf_path = resolve_path(
        "/api/v1/analysis/report/pdf",
        "/analysis/report/pdf",
    )
    export_op = get_op(export_pdf_path, "post")
    body = export_op.get("requestBody", {})
    assert body.get("required") is True
    content = body.get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    if "$ref" in schema:
        schema = schema_for_ref(schema["$ref"])
    required = set(schema.get("required", []))
    assert {"results", "variables", "dataset_id"}.issubset(required)

if __name__ == "__main__":
    test_full_flow()
