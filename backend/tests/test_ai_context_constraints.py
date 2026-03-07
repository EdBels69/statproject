from app.modules.ai_context import safe_plan_constraints


def test_safe_plan_constraints_allows_20000_steps():
    c = safe_plan_constraints({"max_steps": 20000})
    assert c["max_steps"] == 20000


def test_safe_plan_constraints_caps_to_hard_limit():
    c = safe_plan_constraints({"max_steps": 999999})
    assert c["max_steps"] == 20000


def test_safe_plan_constraints_off_maps_to_hard_limit():
    c = safe_plan_constraints({"max_steps": "off"})
    assert c["max_steps"] == 20000
