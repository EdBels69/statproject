"""
Тесты для новых data wrangling actions:
split_column, recode_values, derive_column, bin_variable, string_clean
"""
import pytest
import pandas as pd
import numpy as np
from types import SimpleNamespace

from app.api.datasets import (
    _action_split_column,
    _action_recode_values,
    _action_derive_column,
    _action_bin_variable,
    _action_string_clean,
)


def _action(type_: str, column: str, config: dict = None, **kwargs):
    """Хелпер для создания объекта action."""
    return SimpleNamespace(type=type_, column=column, config=config or {}, **kwargs)


# ── split_column ──────────────────────────────────────────────────────────────

class TestSplitColumn:
    def test_split_rows_basic(self):
        df = pd.DataFrame({"treatments": ["аспирин, клопидогрел", "варфарин"], "id": [1, 2]})
        action = _action("split_column", "treatments", {"separator": ",", "mode": "rows", "trim": True})
        result = _action_split_column(df, action)
        assert len(result) == 3
        assert "аспирин" in result["treatments"].values
        assert "клопидогрел" in result["treatments"].values
        assert "варфарин" in result["treatments"].values

    def test_split_columns_basic(self):
        df = pd.DataFrame({"ab": ["A;B", "C;D"]})
        action = _action("split_column", "ab", {"separator": ";", "mode": "columns", "prefix": "item_"})
        result = _action_split_column(df, action)
        assert "item_1" in result.columns
        assert "item_2" in result.columns
        assert result["item_1"].iloc[0] == "A"

    def test_split_trim_whitespace(self):
        df = pd.DataFrame({"drugs": ["  аспирин ,  варфарин  "]})
        action = _action("split_column", "drugs", {"separator": ",", "mode": "rows", "trim": True})
        result = _action_split_column(df, action)
        assert result["drugs"].iloc[0] == "аспирин"
        assert result["drugs"].iloc[1] == "варфарин"

    def test_split_missing_column_raises(self):
        df = pd.DataFrame({"a": [1, 2]})
        action = _action("split_column", "nonexistent", {"mode": "rows"})
        with pytest.raises(ValueError, match="Колонка не найдена"):
            _action_split_column(df, action)

    def test_split_unknown_mode_raises(self):
        df = pd.DataFrame({"x": ["a,b"]})
        action = _action("split_column", "x", {"separator": ",", "mode": "diagonal"})
        with pytest.raises(ValueError, match="mode"):
            _action_split_column(df, action)


# ── recode_values ─────────────────────────────────────────────────────────────

class TestRecodeValues:
    def test_recode_basic(self):
        df = pd.DataFrame({"gender": ["1", "2", "1"]})
        action = _action("recode_values", "gender", {"mapping": {"1": "Мужской", "2": "Женский"}, "unmapped": "keep"})
        result = _action_recode_values(df, action)
        assert list(result["gender"]) == ["Мужской", "Женский", "Мужской"]

    def test_recode_unmapped_keep(self):
        df = pd.DataFrame({"code": ["1", "99", "2"]})
        action = _action("recode_values", "code", {"mapping": {"1": "Да", "2": "Нет"}, "unmapped": "keep"})
        result = _action_recode_values(df, action)
        assert result["code"].iloc[1] == "99"

    def test_recode_unmapped_null(self):
        df = pd.DataFrame({"code": ["1", "99", "2"]})
        action = _action("recode_values", "code", {"mapping": {"1": "Да", "2": "Нет"}, "unmapped": "null"})
        result = _action_recode_values(df, action)
        assert pd.isna(result["code"].iloc[1])

    def test_recode_empty_mapping_raises(self):
        df = pd.DataFrame({"x": ["a"]})
        action = _action("recode_values", "x", {"mapping": {}})
        with pytest.raises(ValueError, match="mapping"):
            _action_recode_values(df, action)

    def test_recode_missing_column_raises(self):
        df = pd.DataFrame({"a": [1]})
        action = _action("recode_values", "z", {"mapping": {"1": "yes"}})
        with pytest.raises(ValueError, match="Колонка не найдена"):
            _action_recode_values(df, action)


# ── derive_column ─────────────────────────────────────────────────────────────

class TestDeriveColumn:
    def test_bmi_formula(self):
        df = pd.DataFrame({"weight": [70.0, 90.0], "height": [175.0, 180.0]})
        action = _action("derive_column", "BMI", {
            "formula": "weight / (height / 100) ** 2",
            "source_columns": ["weight", "height"],
        })
        result = _action_derive_column(df, action)
        assert "BMI" in result.columns
        expected_bmi_0 = 70.0 / (1.75 ** 2)
        assert abs(result["BMI"].iloc[0] - expected_bmi_0) < 0.001

    def test_delta_formula(self):
        df = pd.DataFrame({"post": [10.0, 20.0], "pre": [5.0, 15.0]})
        action = _action("derive_column", "delta", {"formula": "post - pre"})
        result = _action_derive_column(df, action)
        assert list(result["delta"]) == [5.0, 5.0]

    def test_missing_source_column_raises(self):
        df = pd.DataFrame({"weight": [70.0]})
        action = _action("derive_column", "BMI", {
            "formula": "weight / height",
            "source_columns": ["weight", "height"],
        })
        with pytest.raises(ValueError, match="height"):
            _action_derive_column(df, action)

    def test_empty_formula_raises(self):
        df = pd.DataFrame({"x": [1.0]})
        action = _action("derive_column", "y", {"formula": ""})
        with pytest.raises(ValueError, match="формула"):
            _action_derive_column(df, action)

    def test_bad_formula_raises(self):
        df = pd.DataFrame({"x": [1.0]})
        action = _action("derive_column", "y", {"formula": "x + nonexistent_col"})
        with pytest.raises(ValueError, match="Ошибка в формуле"):
            _action_derive_column(df, action)


# ── bin_variable ──────────────────────────────────────────────────────────────

class TestBinVariable:
    def test_custom_bins(self):
        df = pd.DataFrame({"age": [25, 35, 55, 75]})
        action = _action("bin_variable", "age", {
            "new_column": "age_group",
            "method": "custom",
            "bins": [0, 30, 50, 70, 120],
            "labels": ["<30", "30-50", "50-70", "70+"],
        })
        result = _action_bin_variable(df, action)
        assert "age_group" in result.columns
        assert result["age_group"].iloc[0] == "<30"
        assert result["age_group"].iloc[3] == "70+"

    def test_equal_width_bins(self):
        df = pd.DataFrame({"score": [10, 30, 60, 90]})
        action = _action("bin_variable", "score", {
            "new_column": "score_bin",
            "method": "equal_width",
            "n_bins": 4,
        })
        result = _action_bin_variable(df, action)
        assert "score_bin" in result.columns
        assert result["score_bin"].notna().sum() == 4

    def test_quantile_bins(self):
        df = pd.DataFrame({"val": list(range(20))})
        action = _action("bin_variable", "val", {
            "new_column": "val_q",
            "method": "quantile",
            "n_bins": 4,
        })
        result = _action_bin_variable(df, action)
        assert "val_q" in result.columns

    def test_custom_bins_missing_raises(self):
        df = pd.DataFrame({"x": [1.0]})
        action = _action("bin_variable", "x", {"method": "custom", "bins": []})
        with pytest.raises(ValueError, match="bins"):
            _action_bin_variable(df, action)

    def test_missing_column_raises(self):
        df = pd.DataFrame({"a": [1.0]})
        action = _action("bin_variable", "z", {"method": "equal_width"})
        with pytest.raises(ValueError, match="Колонка не найдена"):
            _action_bin_variable(df, action)


# ── string_clean ──────────────────────────────────────────────────────────────

class TestStringClean:
    def test_trim(self):
        df = pd.DataFrame({"name": ["  Иванов  ", " Петров"]})
        action = _action("string_clean", "name", {"operations": ["trim"]})
        result = _action_string_clean(df, action)
        assert result["name"].iloc[0] == "Иванов"
        assert result["name"].iloc[1] == "Петров"

    def test_lowercase(self):
        df = pd.DataFrame({"diag": ["Диабет", "ГИПЕРТОНИЯ"]})
        action = _action("string_clean", "diag", {"operations": ["lowercase"]})
        result = _action_string_clean(df, action)
        assert result["diag"].iloc[0] == "диабет"
        assert result["diag"].iloc[1] == "гипертония"

    def test_uppercase(self):
        df = pd.DataFrame({"code": ["а01", "б02"]})
        action = _action("string_clean", "code", {"operations": ["uppercase"]})
        result = _action_string_clean(df, action)
        assert result["code"].iloc[0] == "А01"

    def test_replace(self):
        df = pd.DataFrame({"val": ["н/д", "5.2", "н/д"]})
        action = _action("string_clean", "val", {
            "operations": ["replace"],
            "replace_from": "н/д",
            "replace_to": "",
        })
        result = _action_string_clean(df, action)
        assert result["val"].iloc[0] == ""
        assert result["val"].iloc[1] == "5.2"

    def test_chain_operations(self):
        df = pd.DataFrame({"x": ["  ПРИВЕТ  "]})
        action = _action("string_clean", "x", {"operations": ["trim", "lowercase"]})
        result = _action_string_clean(df, action)
        assert result["x"].iloc[0] == "привет"

    def test_unknown_operation_raises(self):
        df = pd.DataFrame({"x": ["test"]})
        action = _action("string_clean", "x", {"operations": ["base64encode"]})
        with pytest.raises(ValueError, match="base64encode"):
            _action_string_clean(df, action)

    def test_missing_column_raises(self):
        df = pd.DataFrame({"a": ["x"]})
        action = _action("string_clean", "z", {"operations": ["trim"]})
        with pytest.raises(ValueError, match="Колонка не найдена"):
            _action_string_clean(df, action)


# ── NaN preservation ──────────────────────────────────────────────────────────

class TestNaNPreservation:
    """Проверяем, что NaN не превращается в строку 'nan'."""

    def test_split_column_preserves_nan(self):
        df = pd.DataFrame({"x": ["a,b", None, "c,d"], "id": [1, 2, 3]})
        action = _action("split_column", "x", {"separator": ",", "mode": "rows", "trim": True})
        result = _action_split_column(df, action)
        nan_rows = result[result["x"].isna()]
        assert len(nan_rows) >= 1, "NaN строки должны сохраняться"
        assert "nan" not in result["x"].dropna().values

    def test_recode_preserves_nan(self):
        df = pd.DataFrame({"g": ["1", None, "2"]})
        action = _action("recode_values", "g", {"mapping": {"1": "М", "2": "Ж"}, "unmapped": "keep"})
        result = _action_recode_values(df, action)
        assert result["g"].iloc[0] == "М"
        assert result["g"].iloc[2] == "Ж"
        assert result["g"].iloc[1] is None or pd.isna(result["g"].iloc[1])

    def test_string_clean_preserves_nan(self):
        df = pd.DataFrame({"diag": ["  ДИАБЕТ  ", None, "ГИПЕРТОНИЯ"]})
        action = _action("string_clean", "diag", {"operations": ["trim", "lowercase"]})
        result = _action_string_clean(df, action)
        assert result["diag"].iloc[0] == "диабет"
        assert result["diag"].iloc[1] is None or pd.isna(result["diag"].iloc[1])
        assert result["diag"].iloc[2] == "гипертония"
