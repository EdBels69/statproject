"""Tests for nlq_router.py — Natural Language Query → Protocol pipeline."""
import pytest
from app.copilot.nlq_router import classify_intent, extract_variables, nlq_to_protocol


class TestClassifyIntent:
    def test_rct_keywords(self):
        template_id, conf = classify_intent("Сравнить две группы лечения в РКИ с плацебо")
        assert template_id == "rct_two_arm"
        assert conf > 0

    def test_before_after_keywords(self):
        template_id, conf = classify_intent("Оценить изменения до и после лечения")
        assert template_id == "before_after"
        assert conf > 0

    def test_cross_sectional_keywords(self):
        template_id, conf = classify_intent("Есть ли корреляция между возрастом и давлением?")
        assert template_id == "cross_sectional"
        assert conf > 0

    def test_longitudinal_keywords(self):
        template_id, conf = classify_intent("Mixed effects анализ по визитам")
        assert template_id == "longitudinal"
        assert conf > 0

    def test_responder_keywords(self):
        template_id, conf = classify_intent("Responder analysis с порогом ответа 10%")
        assert template_id == "responder_analysis"
        assert conf > 0

    def test_no_match(self):
        template_id, conf = classify_intent("Who won the football game?")
        assert template_id is None
        assert conf == 0.0


class TestExtractVariables:
    def test_rct_variables_from_columns(self):
        cols = ["PatientID", "Treatment_Group", "SBP_Score", "DBP_Score"]
        v = extract_variables("compare groups", cols, "rct_two_arm")
        assert v["group"] == "Treatment_Group"

    def test_before_after_variables(self):
        cols = ["ID", "Visit1_Score", "Visit2_Score", "Group"]
        v = extract_variables("before after", cols, "before_after")
        assert v.get("group") is not None or v.get("before") != ""


class TestNLQToProtocol:
    def test_matched_template(self):
        result = nlq_to_protocol(
            "Сравнить две группы в РКИ с плацебо",
            columns=["PatientID", "SBP_Score", "Treatment_Group"],
        )
        assert result["fallback"] is False
        assert result["template_id"] == "rct_two_arm"
        assert result["protocol"] is not None
        assert len(result["protocol"]["steps"]) >= 1

    def test_no_match_fallback(self):
        result = nlq_to_protocol(
            "What is the weather today?",
            columns=["A", "B"],
        )
        assert result["fallback"] is True
        assert result["protocol"] is None

    def test_longitudinal_match(self):
        result = nlq_to_protocol(
            "Проанализировать динамику по визитам с mixed effects",
            columns=["PID", "Group", "V1", "V2", "V3"],
        )
        assert result["fallback"] is False
        assert result["template_id"] == "longitudinal"
