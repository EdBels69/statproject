"""Tests for ExcelIntelligence, DataQualityGate, and DataLineage."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# ExcelIntelligence
# ---------------------------------------------------------------------------

class TestExcelIntelligence:

    def test_analyze_csv_detects_header(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        # Create CSV with numeric/empty junk row, then header, then data
        csv_content = "1,2,3,4\nName,Age,City,Score\nAlice,30,NYC,85\nBob,25,LA,90\n"
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        ei = ExcelIntelligence()
        structure = ei.analyze_structure(str(csv_path), original_filename="test.csv")

        assert structure.header_row == 1  # Should detect row 1 as header

    def test_read_clean_csv_removes_footnotes(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        csv_content = "Name,Age,Score\nAlice,30,85\nBob,25,90\n* Note: this is a footnote\n"
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        ei = ExcelIntelligence()
        df, structure = ei.read_clean(str(csv_path), original_filename="test.csv")

        assert len(df) == 2  # Only data rows, footnote removed
        assert structure.footnote_rows_skipped >= 1

    def test_read_clean_csv_removes_empty_rows(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        csv_content = "Name,Age\nAlice,30\n,,\nBob,25\n"
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        ei = ExcelIntelligence()
        df, structure = ei.read_clean(str(csv_path), original_filename="test.csv")

        assert len(df) == 2
        assert "Name" in df.columns

    def test_read_clean_csv_removes_empty_columns(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        csv_content = "Name,Age,Empty\nAlice,30,\nBob,25,\n"
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        ei = ExcelIntelligence()
        df, structure = ei.read_clean(str(csv_path), original_filename="test.csv")

        assert "Empty" not in df.columns
        assert len(df.columns) == 2

    def test_xlsx_structure_analysis(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        df = pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [30, 25]})
        xlsx_path = tmp_path / "test.xlsx"
        df.to_excel(str(xlsx_path), index=False, engine="openpyxl")

        ei = ExcelIntelligence()
        structure = ei.analyze_structure(str(xlsx_path), original_filename="test.xlsx")

        assert structure.header_row == 0
        assert structure.sheet_names == ["Sheet1"]
        assert len(structure.issues) == 0

    def test_read_clean_xlsx(self, tmp_path):
        from app.modules.excel_intelligence import ExcelIntelligence

        df_orig = pd.DataFrame({"Name": ["Alice", "Bob", "Carol"], "Age": [30, 25, 35]})
        xlsx_path = tmp_path / "test.xlsx"
        df_orig.to_excel(str(xlsx_path), index=False, engine="openpyxl")

        ei = ExcelIntelligence()
        df, structure = ei.read_clean(str(xlsx_path), original_filename="test.xlsx")

        assert len(df) == 3
        assert list(df.columns) == ["Name", "Age"]


# ---------------------------------------------------------------------------
# DataQualityGate
# ---------------------------------------------------------------------------

class TestDataQualityGate:

    def test_basic_clean_data(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "age": [25, 30, 35, 40, 45],
            "name": ["A", "B", "C", "D", "E"],
            "score": [80.0, 85.0, 90.0, 75.0, 88.0],
        })

        gate = DataQualityGate()
        report = gate.run(df)

        assert report.is_ready is True
        assert report.overall_score > 0.5
        assert len(report.df_clean) == 5
        assert len(report.cleaning_log) >= 0

    def test_removes_duplicates(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "x": [1, 2, 2, 3, 3, 3],
            "y": ["a", "b", "b", "c", "c", "c"],
        })

        gate = DataQualityGate()
        report = gate.run(df)

        assert report.rows_final < report.rows_original
        assert len(report.df_clean) == 3  # 3 unique rows
        assert any(s.get("action") == "remove_duplicates" for s in report.cleaning_log if isinstance(s, dict))

    def test_drops_high_missing_columns(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "good": [1, 2, 3, 4, 5],
            "bad": [np.nan, np.nan, np.nan, np.nan, 1],  # 80% missing
        })

        gate = DataQualityGate(max_missing_threshold=0.7)
        report = gate.run(df)

        assert "bad" not in report.df_clean.columns

    def test_imputes_numeric_missing(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "val": [10.0, 20.0, np.nan, 40.0, 50.0],
        })

        gate = DataQualityGate(imputation_strategy="median")
        report = gate.run(df)

        assert report.df_clean["val"].isna().sum() == 0

    def test_outlier_detection(self):
        from app.modules.data_quality_gate import DataQualityGate

        values = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 100]  # 100 is outlier, all unique
        df = pd.DataFrame({"val": values})

        gate = DataQualityGate(outlier_policy="flag")
        report = gate.run(df)

        # With "flag" policy, outliers stay but are logged
        assert len(report.df_clean) == len(df.drop_duplicates())
        has_outlier_step = any(
            s.get("action") == "outlier_detection"
            for s in report.cleaning_log if isinstance(s, dict)
        )
        assert has_outlier_step

    def test_data_contract_generated(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "age": [25, 30, 35],
            "name": ["Alice", "Bob", "Carol"],
        })

        gate = DataQualityGate()
        report = gate.run(df)

        contract = report.data_contract
        assert contract["schema"] == "clinimetria.data_contract"
        assert "age" in contract["columns"]
        assert "name" in contract["columns"]
        assert contract["columns"]["age"]["dtype"] == "numeric"
        assert contract["columns"]["name"]["dtype"] == "categorical"

    def test_cleaning_log_and_plan_serializable(self):
        from app.modules.data_quality_gate import DataQualityGate

        df = pd.DataFrame({
            "x": [1, 2, 2, 3],
            "y": [np.nan, "a", "b", "c"],
        })

        gate = DataQualityGate()
        report = gate.run(df)

        log_json = gate.to_cleaning_log_json(report)
        plan_json = gate.to_cleaning_plan_json(report)

        # Should be JSON-serializable
        json.dumps(log_json, default=str)
        json.dumps(plan_json, default=str)

        assert log_json["schema"] == "clinimetria.cleaning_log"
        assert plan_json["schema"] == "clinimetria.cleaning_plan"

    def test_analysis_set_hash(self):
        from app.modules.data_quality_gate import compute_analysis_set_hash

        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        h1 = compute_analysis_set_hash(df)
        h2 = compute_analysis_set_hash(df)
        assert h1 == h2  # deterministic

        df2 = pd.DataFrame({"x": [1, 2, 4], "y": [4, 5, 6]})
        h3 = compute_analysis_set_hash(df2)
        assert h1 != h3  # different data = different hash


# ---------------------------------------------------------------------------
# DataLineage
# ---------------------------------------------------------------------------

class TestDataLineage:

    def test_record_and_serialize(self):
        from app.modules.data_lineage import DataLineage

        lineage = DataLineage(source_filename="test.xlsx")

        df1 = pd.DataFrame({"a": [1, 2, 3]})
        df2 = pd.DataFrame({"a": [1, 2]})

        lineage.record(
            "remove_duplicates",
            details={"method": "exact"},
            df_before=df1,
            df_after=df2,
        )

        doc = lineage.to_document()
        assert doc["schema"] == "clinimetria.data_lineage"
        assert doc["source"] == "test.xlsx"
        assert len(doc["steps"]) == 1
        assert doc["steps"][0]["action"] == "remove_duplicates"
        assert doc["steps"][0]["rows_before"] == 3
        assert doc["steps"][0]["rows_after"] == 2

    def test_snapshot(self):
        from app.modules.data_lineage import DataLineage

        lineage = DataLineage()
        df = pd.DataFrame({"x": [1, 2, 3]})

        h = lineage.record_snapshot("raw", df)
        assert isinstance(h, str) and len(h) == 64  # SHA256

        doc = lineage.to_document()
        assert "raw" in doc["snapshots"]
        assert doc["snapshots"]["raw"] == h

    def test_save_and_load(self, tmp_path):
        from app.modules.data_lineage import DataLineage

        lineage = DataLineage(source_filename="data.csv")
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        lineage.record("normalize", details={"headers": True}, df_before=df, df_after=df)
        lineage.record_snapshot("after_normalize", df)

        path = str(tmp_path / "lineage.json")
        lineage.save(path)

        loaded = DataLineage.load(path)
        doc = loaded.to_document()

        assert doc["source"] == "data.csv"
        assert len(doc["steps"]) == 2
        assert "after_normalize" in doc["snapshots"]

    def test_summary_text(self):
        from app.modules.data_lineage import DataLineage

        lineage = DataLineage()
        df1 = pd.DataFrame({"x": range(10)})
        df2 = pd.DataFrame({"x": range(8)})

        lineage.record("remove_duplicates", df_before=df1, df_after=df2)
        lineage.record("impute_missing", details={"strategy": "median"}, df_before=df2, df_after=df2)

        text = lineage.summary_text(is_ru=True)
        assert "Этапы подготовки данных" in text
        assert "remove_duplicates" in text
        assert "impute_missing" in text

        text_en = lineage.summary_text(is_ru=False)
        assert "Data preparation steps" in text_en
