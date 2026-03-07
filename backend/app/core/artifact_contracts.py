from __future__ import annotations

from typing import Any, Dict, List, Tuple


ContractType = Tuple[type, ...]


ARTIFACT_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "source_meta.json": {
        "required": {
            "original_filename": (str,),
            "ingest_timestamp": (str,),
        },
    },
    "protocol.json": {
        "required": {
            "name": (str,),
            "alpha": (int, float),
            "steps": (list,),
        },
    },
    "results.json": {
        "required": {
            "dataset_id": (str,),
            "status": (str,),
            "results": (dict, list),
            "errors": (list,),
            "warnings": (list,),
        },
    },
    "verification.json": {
        "required": {
            "schema": (str,),
            "status": (str,),
            "summary": (dict,),
        },
    },
    "protocol_validation.json": {
        "required": {
            "schema": (str,),
            "status": (str,),
            "summary": (dict,),
            "steps": (list,),
        },
    },
    "bootstrap_trace.json": {
        "required": {
            "schema": (str,),
            "summary": (dict,),
            "steps": (list,),
        },
    },
    "multiplicity_trace.json": {
        "required": {
            "schema": (str,),
            "summary": (dict,),
            "steps": (list,),
        },
    },
    "hypothesis_discovery.json": {
        "required": {
            "schema": (str,),
            "count": (int,),
            "items": (list,),
        },
    },
    "reproducibility_manifest.json": {
        "required": {
            "schema": (str,),
            "run_id": (str,),
            "dataset_id": (str,),
            "artifacts": (list,),
        },
    },
    "reflection_log.json": {
        "required": {
            "schema": (str,),
            "run_id": (str,),
            "dataset_id": (str,),
            "rounds": (list,),
            "final_verification_status": (str,),
        },
    },
    "runtime_profile.json": {
        "required": {
            "schema": (str,),
            "summary": (dict,),
            "steps": (list,),
        },
    },
}


def _normalize_name(artifact_name: str) -> str:
    text = str(artifact_name or "").strip()
    return text.split("/")[-1]


def validate_artifact_contract(artifact_name: str, payload: Any) -> List[str]:
    name = _normalize_name(artifact_name)
    contract = ARTIFACT_CONTRACTS.get(name)
    if contract is None:
        return []

    if not isinstance(payload, dict):
        return [f"{name}: payload must be an object"]

    required = contract.get("required") if isinstance(contract.get("required"), dict) else {}
    errors: List[str] = []
    for field, expected_types in required.items():
        value = payload.get(field)
        if value is None:
            errors.append(f"{name}: missing required field '{field}'")
            continue
        if isinstance(expected_types, tuple) and expected_types:
            if not isinstance(value, expected_types):
                expected = ", ".join([tp.__name__ for tp in expected_types])
                errors.append(
                    f"{name}: field '{field}' has invalid type {type(value).__name__}, expected {expected}"
                )
    return errors


def assert_artifact_contract(artifact_name: str, payload: Any) -> None:
    errors = validate_artifact_contract(artifact_name, payload)
    if errors:
        raise ValueError("; ".join(errors))
