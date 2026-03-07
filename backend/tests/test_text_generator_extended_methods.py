import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.text_generator import TextGenerator


def test_text_generator_ancova_ru_no_placeholder():
    payload = {
        "method": {"id": "ancova", "name": "ancova"},
        "p_value": 0.01,
        "stat_value": 4.2,
        "significant": True,
        "covariates": ["Возраст", "SpO2"],
    }
    text = TextGenerator.generate_conclusion(payload, {"outcome": "Глюкоза", "group": "Исход"}, style="ru")
    assert "Analysis completed" not in text
    assert "ANCOVA" in text
    assert "Глюкоза" in text


def test_text_generator_bayes_ru_reports_bf10():
    payload = {
        "method": {"id": "bayes_correlation", "name": "bayes_correlation"},
        "p_value": 0.0005,
        "bf10": 12.7,
        "effect_size": 0.31,
        "effect_size_name": "r",
        "significant": True,
    }
    text = TextGenerator.generate_conclusion(payload, {"target": "Глюкоза", "group": "СРБ"}, style="ru")
    assert "BF10=" in text
    assert "Байесов" in text
    assert "Analysis completed" not in text


def test_text_generator_generic_fallback_ru_not_english_placeholder():
    payload = {
        "method": {"id": "custom_new_method", "name": "custom_new_method"},
        "p_value": 0.2,
        "alpha": 0.05,
        "significant": False,
    }
    text = TextGenerator.generate_conclusion(payload, {"target": "X", "group": "Y"}, style="ru")
    assert "Analysis completed" not in text
    assert "Выполнен анализ" in text
