import sys
import os

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app


client = TestClient(app)


def test_knowledge_terms_list():
    response = client.get("/api/v1/v2/knowledge/terms")
    assert response.status_code == 200
    payload = response.json()
    assert "terms" in payload
    assert isinstance(payload["terms"], list)
    assert len(payload["terms"]) > 0


def test_knowledge_term_explanation_ok():
    response = client.get("/api/v1/v2/knowledge/terms/p_value?level=junior")
    assert response.status_code == 200
    payload = response.json()
    assert payload["term"]
    assert payload["term_ru"]
    assert payload["definition"]


def test_knowledge_term_explanation_404():
    response = client.get("/api/v1/v2/knowledge/terms/__missing__")
    assert response.status_code == 404
    payload = response.json()
    assert "detail" in payload


def test_knowledge_tests_list():
    response = client.get("/api/v1/v2/knowledge/tests")
    assert response.status_code == 200
    payload = response.json()
    assert "tests" in payload
    assert isinstance(payload["tests"], list)
    assert any(item.get("key") == "t_test_ind" for item in payload["tests"])


def test_knowledge_test_rationale_with_assumptions():
    response = client.get(
        "/api/v1/v2/knowledge/tests/t_test_ind?level=junior&shapiro_p=0.01&levene_p=0.2"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["test_id"] == "t_test_ind"
    assert isinstance(payload.get("assumption_checks"), list)
    by_key = {a.get("assumption"): a for a in payload.get("assumption_checks")}
    assert "normality" in by_key
    assert by_key["normality"].get("passed") is False
    assert "homogeneity" in by_key
    assert by_key["homogeneity"].get("passed") is True


def test_knowledge_effect_size_interpretation():
    response = client.get("/api/v1/v2/knowledge/effect-size?type=cohens_d&value=0.6")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "cohens_d"
    assert payload["label"] != "unknown"


def test_knowledge_effect_size_eta_squared_alias():
    response = client.get("/api/v1/v2/knowledge/effect-size?type=eta_squared&value=0.12")
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] != "unknown"


def test_knowledge_power_recommendation():
    response = client.get("/api/v1/v2/knowledge/power?power=0.4")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "critical"


def test_knowledge_power_validation():
    response = client.get("/api/v1/v2/knowledge/power?power=1.2")
    assert response.status_code == 422

