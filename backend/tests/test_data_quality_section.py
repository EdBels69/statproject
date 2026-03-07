"""Tests for Data Quality section in HTML report."""


class TestDataQualitySection:
    """Ensure _add_data_quality_section renders without crash."""

    def test_section_renders_with_empty_data(self):
        from app.modules.reporting_html import ProtocolReport

        run_data = {
            "results": {},
            "step_meta": {},
            "dataset_id": "nonexistent",
        }
        rpt = ProtocolReport(run_data, dataset_name="test")
        rpt.is_ru = True
        rpt.html_parts = []
        rpt._add_data_quality_section()
        html_out = "".join(rpt.html_parts)
        assert "data-quality" in html_out
        assert "Качество данных" in html_out

    def test_section_renders_cleaning_log(self):
        """If cleaning_log has steps, they should appear in output."""
        from app.modules.reporting_html import ProtocolReport

        run_data = {
            "results": {},
            "step_meta": {},
            "dataset_id": "nonexistent",
            "protocol_plan": {
                "column_selection_report": {
                    "total_columns": 100,
                    "analyzed_total": 30,
                    "excluded_total": 70,
                    "excluded": {
                        "high_missing": ["col_A (95%)", "col_B (80%)"],
                        "constant": ["col_C"],
                        "id_like": ["patient_id"],
                        "mixed_types": [],
                        "group_time_subject": ["group"],
                        "not_in_analysis": ["col_D"],
                    },
                    "selection_logic": "Из 100 столбцов отобрано 30.",
                    "recommendations": [
                        "Столбцы с >70% пропусков: проверьте."
                    ],
                }
            },
        }
        rpt = ProtocolReport(run_data, dataset_name="test")
        rpt.is_ru = True
        rpt.html_parts = []
        rpt._add_data_quality_section()
        html_out = "".join(rpt.html_parts)
        assert "30" in html_out  # analyzed_total
        assert "70" in html_out  # excluded_total
        assert "col_A" in html_out
        assert "Рекомендации" in html_out


class TestDesignTypeLabels:
    """Ensure design type labels are translated."""

    def test_repeated_measures_wide_label(self):
        from app.modules.reporting_html import _DESIGN_TYPE_LABELS_RU

        assert "repeated_measures_wide" in _DESIGN_TYPE_LABELS_RU
        label = _DESIGN_TYPE_LABELS_RU["repeated_measures_wide"]
        assert "Повторные" in label
        assert "широкий" in label


class TestColumnSelectionReport:
    """Test column_selection_report in protocol_rules."""

    def test_build_exploratory_plan_has_column_report(self):
        """build_exploratory_plan should return column_selection_report dict."""
        from app.modules.protocol_rules import build_exploratory_plan

        scan = {
            "columns": {
                "id": {"type": "int64", "missing_ratio": 0, "unique_count": 100},
                "age": {"type": "float64", "missing_ratio": 0.01, "unique_count": 50},
                "group": {
                    "type": "object",
                    "missing_ratio": 0,
                    "unique_count": 2,
                    "categories": ["A", "B"],
                },
                "empty_col": {"type": "float64", "missing_ratio": 0.95, "unique_count": 2},
            }
        }
        study = {
            "design": {
                "design_type": "two_groups",
                "group_column": "group",
                "outcomes": ["age"],
                "categorical_outcomes": [],
                "id_like_columns": ["id"],
            },
            "analysis_policy": {},
        }

        result = build_exploratory_plan(
            dataset_id="test",
            base_dir="/tmp",
            scan_report=scan,
            study_design=study,
        )
        assert "column_selection_report" in result
        csr = result["column_selection_report"]
        assert csr["total_columns"] == 4
        assert csr["analyzed_total"] >= 1
        assert isinstance(csr["excluded"], dict)
        assert isinstance(csr["selection_logic"], str)
        assert len(csr["selection_logic"]) > 10
