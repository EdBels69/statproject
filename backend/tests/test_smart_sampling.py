import pandas as pd

from app.llm.smart_sampling import build_smart_sample


def test_smart_sampling_redacts_pii():
    df = pd.DataFrame(
        {
            "email": ["user@example.com", "test@site.org"],
            "phone": ["+7 999 123-45-67", "89161234567"],
            "age": [34, 45],
            "gender": ["male", "female"],
        }
    )
    sample = build_smart_sample(df, max_rows=4, max_cols=6, redact_mode="pii")
    rows = sample.get("rows") or []
    assert rows, "Expected sample rows"
    for row in rows:
        assert row.get("email") == "[REDACTED]"
        assert row.get("phone") == "[REDACTED]"
        assert row.get("gender") in {"male", "female", None}


def test_smart_sampling_strict_masks_strings():
    df = pd.DataFrame(
        {
            "comment": ["hello", "world"],
            "age": [10, 20],
        }
    )
    sample = build_smart_sample(df, max_rows=4, max_cols=4, redact_mode="strict")
    rows = sample.get("rows") or []
    assert rows, "Expected sample rows"
    for row in rows:
        assert row.get("comment") == "[REDACTED]"
