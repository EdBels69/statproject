import os
import sys

import pandas as pd
import pytest
from fastapi import BackgroundTasks

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import v2


class _DummyPipeline:
    def __init__(self, root: str):
        self.root = root
        self.saved_payload = None

    def create_analysis_run(self, dataset_id: str, protocol_payload):
        run_dir = os.path.join(self.root, dataset_id, "analysis", "run_0001")
        os.makedirs(run_dir, exist_ok=True)
        return run_dir

    def save_run_results(self, run_dir, payload):
        self.saved_payload = payload

    def build_result_ir(self, payload):
        return {"blocks": [], "warnings": payload.get("warnings", [])}


def test_normalize_analysis_mode_supports_comprehensive_and_expert():
    assert v2._normalize_analysis_mode("comprehensive") == "comprehensive"
    assert v2._normalize_analysis_mode("expert_comprehensive") == "expert_comprehensive"
    assert v2._normalize_analysis_mode("expert") == "expert_comprehensive"
    assert v2._normalize_analysis_mode("confirmatory") == "publication"
    assert v2._normalize_analysis_mode("discovery") == "discovery"
    assert v2._normalize_analysis_mode("data_prep") == "data_prep"


@pytest.mark.anyio
async def test_execute_protocol_rejects_data_prep_mode(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_data_prep_execute_block",
        protocol=[],
        alpha=0.05,
        globals={"analysis_mode": "data_prep"},
    )
    with pytest.raises(v2.HTTPException) as exc:
        await v2.execute_protocol(request, BackgroundTasks())

    assert exc.value.status_code == 400
    assert "data_prep" in str(exc.value.detail).lower()


@pytest.mark.anyio
async def test_execute_protocol_warns_when_design_not_confirmed(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "load_design_review", lambda base_dir, dataset_id: {"confirmed": False})
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_soft_check",
        protocol=[],
        alpha=0.05,
        globals={"allow_unconfirmed_design": True},
    )
    response = await v2.execute_protocol(request, BackgroundTasks())

    assert response["status"] == "completed"
    assert response["design_review_confirmed"] is False
    assert any("Design Review" in w for w in (response.get("warnings") or []))
    assert isinstance(dummy_pipeline.saved_payload, dict)
    assert dummy_pipeline.saved_payload.get("design_review", {}).get("confirmed") is False


@pytest.mark.anyio
async def test_execute_protocol_requires_design_confirmation(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "load_design_review", lambda base_dir, dataset_id: {"confirmed": False})
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_soft_check_gate",
        protocol=[],
        alpha=0.05,
        globals={},
    )
    with pytest.raises(v2.HTTPException) as exc:
        await v2.execute_protocol(request, BackgroundTasks())

    assert exc.value.status_code == 400
    assert "Design Review" in str(exc.value.detail)


@pytest.mark.anyio
async def test_execute_protocol_allows_without_confirmation_when_gate_disabled(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "load_design_review", lambda base_dir, dataset_id: {"confirmed": False})
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", False)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_soft_check_cfg_off",
        protocol=[],
        alpha=0.05,
        globals={},
    )
    response = await v2.execute_protocol(request, BackgroundTasks())

    assert response["status"] == "completed"
    assert response["design_review_confirmed"] is False
    assert response["design_review_required"] is False
    assert any("CLINIMETRIA_REQUIRE_DESIGN_REVIEW" in w for w in (response.get("warnings") or []))


@pytest.mark.anyio
async def test_execute_protocol_ignores_globals_confirmation_without_backend_artifact(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "load_design_review", lambda base_dir, dataset_id: {"confirmed": False})
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_soft_check_globals_only",
        protocol=[],
        alpha=0.05,
        globals={"design_confirmed": True},
    )
    with pytest.raises(v2.HTTPException) as exc:
        await v2.execute_protocol(request, BackgroundTasks())

    assert exc.value.status_code == 400
    assert "backend-артефакте" in str(exc.value.detail)


@pytest.mark.anyio
async def test_execute_protocol_uses_backend_artifact_confirmation(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(
        v2,
        "load_design_review",
        lambda base_dir, dataset_id: {
            "confirmed": True,
            "confirmed_at": "2026-02-07T18:10:00",
            "confirmed_by": "test-user",
            "confirmed_source": "test",
        },
    )
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_soft_check_artifact_ok",
        protocol=[],
        alpha=0.05,
        globals={},
    )
    response = await v2.execute_protocol(request, BackgroundTasks())

    assert response["status"] == "completed"
    assert response["design_review_confirmed"] is True
    assert response["design_review_artifact_confirmed"] is True
    assert isinstance(dummy_pipeline.saved_payload, dict)
    assert dummy_pipeline.saved_payload.get("design_review", {}).get("confirmed") is True
    assert dummy_pipeline.saved_payload.get("design_review", {}).get("confirmed_source") == "test"


@pytest.mark.anyio
async def test_execute_protocol_publication_mode_blocks_design_bypass(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "load_design_review", lambda base_dir, dataset_id: {"confirmed": False})
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_publication_no_design",
        protocol=[],
        alpha=0.05,
        globals={"analysis_mode": "publication", "allow_unconfirmed_design": True},
    )
    with pytest.raises(v2.HTTPException) as exc:
        await v2.execute_protocol(request, BackgroundTasks())

    assert exc.value.status_code == 400
    assert "Publication mode" in str(exc.value.detail)


@pytest.mark.anyio
async def test_execute_protocol_publication_mode_requires_analysis_set(tmp_path, monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    dummy_pipeline = _DummyPipeline(str(tmp_path))
    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(
        v2,
        "load_design_review",
        lambda base_dir, dataset_id: {
            "confirmed": True,
            "confirmed_at": "2026-02-07T18:10:00",
            "confirmed_by": "test-user",
            "confirmed_source": "test",
        },
    )
    monkeypatch.setattr(v2, "pipeline", dummy_pipeline)
    monkeypatch.setattr(v2.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    request = v2.ExecuteProtocolRequest(
        dataset_id="ds_publication_no_analysis_set",
        protocol=[],
        alpha=0.05,
        globals={"analysis_mode": "publication"},
    )
    with pytest.raises(v2.HTTPException) as exc:
        await v2.execute_protocol(request, BackgroundTasks())

    assert exc.value.status_code == 400
    assert "analysis_set_id" in str(exc.value.detail)


@pytest.mark.anyio
async def test_plan_analysis_appends_design_review_warning(monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    def _fake_build_ai_context(**kwargs):
        return {
            "columns": [{"name": "group"}, {"name": "outcome"}],
            "study_design": {"design": {"group_column": "group", "outcomes": ["outcome"]}},
        }

    def _fake_safe_plan_constraints(preferences):
        return {}

    def _fake_build_exploratory_plan(**kwargs):
        return {
            "protocol": [{"id": "r1", "method": "descriptive_compare", "config": {"outcome": "outcome", "group": "group"}}],
            "globals": {},
            "notes": [],
        }

    async def _fake_analyze_research_design(**kwargs):
        return {
            "protocol_name": "AI Plan",
            "protocol": [{"id": "ai1", "method": "descriptive_compare", "config": {"outcome": "outcome", "group": "group"}}],
            "globals": {},
            "notes": [],
        }

    def _fake_enforce_protocol_constraints(protocol, constraints):
        return protocol

    def _fake_load_study_design(base_dir, dataset_id):
        return {"design": {"group_column": "group", "outcomes": ["outcome"]}}

    def _fake_evaluate_protocol_quality(protocol, study_design=None, scan_report=None):
        return {"score": 80.0, "issues": []}

    async def _fake_critique_protocol(**kwargs):
        return None

    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "build_ai_context", _fake_build_ai_context)
    monkeypatch.setattr(v2, "safe_plan_constraints", _fake_safe_plan_constraints)
    monkeypatch.setattr(v2, "build_exploratory_plan", _fake_build_exploratory_plan)
    monkeypatch.setattr(v2, "analyze_research_design", _fake_analyze_research_design)
    monkeypatch.setattr(v2, "enforce_protocol_constraints", _fake_enforce_protocol_constraints)
    monkeypatch.setattr(v2, "load_study_design", _fake_load_study_design)
    monkeypatch.setattr(v2, "evaluate_protocol_quality", _fake_evaluate_protocol_quality)
    monkeypatch.setattr(v2, "critique_protocol", _fake_critique_protocol)

    request = v2.AnalysisPlanRequest(
        dataset_id="ds_soft_plan",
        text="Сформируй план",
        protocol=None,
        preferences={},
    )
    response = await v2.plan_analysis_with_ai(request)

    assert response["status"] == "completed"
    assert response["design_review_confirmed"] is False
    assert any("Design Review" in n for n in (response.get("notes") or []))
    assert response["analysis_mode"] == "exploratory"
    assert isinstance(response.get("cleaning_plan"), dict)
    assert isinstance(response.get("cohort_plan"), dict)
    assert isinstance(response.get("report_spec"), dict)
    assert response.get("globals", {}).get("analysis_mode") == "exploratory"


@pytest.mark.anyio
async def test_plan_analysis_data_prep_returns_cleaning_only(monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})

    def _fake_build_ai_context(**kwargs):
        return {"columns": [{"name": "group"}, {"name": "outcome"}], "study_design": {"design": {}}}

    def _fake_safe_plan_constraints(preferences):
        return {"max_steps": 20, "max_variables_per_step": 8, "max_predictors": 6}

    def _fake_load_study_design(base_dir, dataset_id):
        return {"design": {"group_column": "group", "outcomes": ["outcome"]}}

    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "build_ai_context", _fake_build_ai_context)
    monkeypatch.setattr(v2, "safe_plan_constraints", _fake_safe_plan_constraints)
    monkeypatch.setattr(v2, "load_study_design", _fake_load_study_design)

    request = v2.AnalysisPlanRequest(
        dataset_id="ds_data_prep_plan",
        text="Подготовь данные",
        protocol=None,
        preferences={"analysis_mode": "data_prep"},
    )
    response = await v2.plan_analysis_with_ai(request)

    assert response["status"] == "completed"
    assert response["analysis_mode"] == "data_prep"
    assert response.get("globals", {}).get("analysis_mode") == "data_prep"
    assert response.get("protocol") == []
    assert bool(response.get("cleaning_plan", {}).get("required")) is True
    assert bool(response.get("cohort_plan", {}).get("required")) is False
    assert response.get("report_spec", {}).get("style") == "prep"


@pytest.mark.anyio
async def test_plan_analysis_publication_mode_builds_structured_contract(monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0], "x1": [0.1, None]})

    def _fake_build_ai_context(**kwargs):
        return {
            "columns": [{"name": "group"}, {"name": "outcome"}, {"name": "x1"}],
            "study_design": {"design": {"group_column": "group", "outcomes": ["outcome"]}},
        }

    def _fake_safe_plan_constraints(preferences):
        return {}

    def _fake_build_exploratory_plan(**kwargs):
        return {
            "protocol": [{"id": "r1", "method": "descriptive_compare", "config": {"outcome": "outcome", "group": "group"}}],
            "globals": {},
            "notes": [],
        }

    async def _fake_analyze_research_design(**kwargs):
        return {
            "protocol_name": "AI Plan",
            "protocol": [
                {
                    "id": "m1",
                    "method": "logistic_regression",
                    "config": {"outcome": "outcome", "predictors": ["x1"], "group": "group"},
                }
            ],
            "globals": {},
            "notes": [],
        }

    def _fake_enforce_protocol_constraints(protocol, constraints):
        return protocol

    def _fake_load_study_design(base_dir, dataset_id):
        return {"design": {"group_column": "group", "outcomes": ["outcome"]}}

    def _fake_evaluate_protocol_quality(protocol, study_design=None, scan_report=None):
        return {"score": 80.0, "issues": []}

    async def _fake_critique_protocol(**kwargs):
        return None

    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "build_ai_context", _fake_build_ai_context)
    monkeypatch.setattr(v2, "safe_plan_constraints", _fake_safe_plan_constraints)
    monkeypatch.setattr(v2, "build_exploratory_plan", _fake_build_exploratory_plan)
    monkeypatch.setattr(v2, "analyze_research_design", _fake_analyze_research_design)
    monkeypatch.setattr(v2, "enforce_protocol_constraints", _fake_enforce_protocol_constraints)
    monkeypatch.setattr(v2, "load_study_design", _fake_load_study_design)
    monkeypatch.setattr(v2, "evaluate_protocol_quality", _fake_evaluate_protocol_quality)
    monkeypatch.setattr(v2, "critique_protocol", _fake_critique_protocol)

    request = v2.AnalysisPlanRequest(
        dataset_id="ds_publication_plan",
        text="Сформируй план для публикации",
        protocol=None,
        preferences={"analysis_mode": "publication"},
    )
    response = await v2.plan_analysis_with_ai(request)

    assert response["status"] == "completed"
    assert response["analysis_mode"] == "publication"
    assert response.get("globals", {}).get("analysis_mode") == "publication"
    assert response.get("cohort_plan", {}).get("required") is True
    assert response.get("cohort_plan", {}).get("strict") is True
    assert response.get("report_spec", {}).get("style") == "publication"
    assert response.get("report_spec", {}).get("strict_interpretations") is True


@pytest.mark.anyio
async def test_plan_analysis_expert_mode_builds_strict_contract(monkeypatch):
    async def _fake_load_dataset_async(dataset_id: str):
        return pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0], "x1": [0.1, None]})

    def _fake_build_ai_context(**kwargs):
        return {
            "columns": [{"name": "group"}, {"name": "outcome"}, {"name": "x1"}],
            "study_design": {"design": {"group_column": "group", "outcomes": ["outcome"]}},
        }

    def _fake_safe_plan_constraints(preferences):
        return {}

    def _fake_build_exploratory_plan(**kwargs):
        return {
            "protocol": [{"id": "r1", "method": "descriptive_compare", "config": {"outcome": "outcome", "group": "group"}}],
            "globals": {},
            "notes": [],
        }

    async def _fake_analyze_research_design(**kwargs):
        return {
            "protocol_name": "AI Plan",
            "protocol": [
                {
                    "id": "m1",
                    "method": "random_forest",
                    "config": {"outcome": "outcome", "predictors": ["x1"], "task": "regression"},
                }
            ],
            "globals": {},
            "notes": [],
        }

    def _fake_enforce_protocol_constraints(protocol, constraints):
        return protocol

    def _fake_load_study_design(base_dir, dataset_id):
        return {"design": {"group_column": "group", "outcomes": ["outcome"]}}

    def _fake_evaluate_protocol_quality(protocol, study_design=None, scan_report=None):
        return {"score": 80.0, "issues": []}

    async def _fake_critique_protocol(**kwargs):
        return None

    monkeypatch.setattr(v2, "load_dataset_async", _fake_load_dataset_async)
    monkeypatch.setattr(v2, "build_ai_context", _fake_build_ai_context)
    monkeypatch.setattr(v2, "safe_plan_constraints", _fake_safe_plan_constraints)
    monkeypatch.setattr(v2, "build_exploratory_plan", _fake_build_exploratory_plan)
    monkeypatch.setattr(v2, "analyze_research_design", _fake_analyze_research_design)
    monkeypatch.setattr(v2, "enforce_protocol_constraints", _fake_enforce_protocol_constraints)
    monkeypatch.setattr(v2, "load_study_design", _fake_load_study_design)
    monkeypatch.setattr(v2, "evaluate_protocol_quality", _fake_evaluate_protocol_quality)
    monkeypatch.setattr(v2, "critique_protocol", _fake_critique_protocol)

    request = v2.AnalysisPlanRequest(
        dataset_id="ds_expert_plan",
        text="Сформируй экспертный план",
        protocol=None,
        preferences={"analysis_mode": "expert_comprehensive"},
    )
    response = await v2.plan_analysis_with_ai(request)

    assert response["status"] == "completed"
    assert response["analysis_mode"] == "expert_comprehensive"
    assert response.get("globals", {}).get("analysis_mode") == "expert_comprehensive"
    assert response.get("cohort_plan", {}).get("required") is True
    assert response.get("cohort_plan", {}).get("strict") is True
    assert response.get("report_spec", {}).get("style") == "expert"
    assert response.get("report_spec", {}).get("strict_interpretations") is True
