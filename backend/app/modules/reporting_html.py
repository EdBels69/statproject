"""
reporting_html.py — HTML report generation extracted from reporting.py.

Contains the ProtocolReport class which generates comprehensive HTML reports
from Protocol Analysis Run data.
"""
from __future__ import annotations

import base64
from collections import Counter
import html
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from jinja2 import Environment, FileSystemLoader

from app.modules.analysis_result_v2 import normalize_run_data_results
from app.modules.reporting_contracts import (
    build_report_integrity_context,
    filter_step_pairs_for_report,
)
from app.modules.reporting_plots import _render_plot_png_bytes, _report_plot_theme
from app.modules.plot_config import apply_publication_config, get_group_colors, COLORS
from app.modules.reporting import (
    _dedupe_step_payloads,
    _safe_float,
    _fmt_p_inline,
    _resolve_dataset_dir_path,
    _sha256_file,
    _build_provenance_file_context,
    _extract_protocol_findings,
    _build_discussion_conclusion,
    _method_label_from_type,
    _method_label_from_id,
    _normalize_correction_key,
    _format_correction_label,
    _format_boolean_label,
    _format_validation_status_label,
    _extract_bootstrap_policy,
    _format_bootstrap_policy_text,
    _extract_multiplicity_policy,
    _format_multiplicity_policy_text,
    _extract_hypothesis_discovery_doc,
    _normalize_hypothesis_method_id,
    _split_hypothesis_suggested_methods,
    _extract_executed_methods_by_step,
    _build_hypothesis_discovery_context,
    _protocol_validation_provenance_rows,
    _compact_report_text,
    _clean_report_messages,
    _protocol_validation_section_context,
    _bootstrap_trace_lines,
    _is_placeholder_interpretation,
    _extract_step_context_value,
    _build_step_display,
    _generate_fallback_interpretation,
    _preview_values,
    _step_scope_summary,
    _batch_method_selection_rationale,
    _extract_report_methods,
    _build_report_limitations,
    _interpret_bf10_ru,
    _normalize_report_density,
    _parse_accent_css,
    _coerce_alpha,
    _normalize_method_text,
    _batch_target_label,
    _collect_batch_inferential_rows,
    _build_pairwise_comparison_rows,
    _format_axis_label,
    _format_group_axis_label,
    _method_selection_rationale_ru,
    _parse_accent_rgb,
)

try:
    from app.modules.reporting_utils import normalize_comparisons, add_significance_bracket
except ImportError:
    def normalize_comparisons(*args, **kwargs):
        return []
    def add_significance_bracket(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_DESIGN_TYPE_LABELS_RU = {
    "cross_sectional": "Поперечное исследование",
    "longitudinal": "Лонгитюдное исследование",
    "repeated_measures": "Повторные измерения",
    "repeated_measures_wide": "Повторные измерения (широкий формат)",
    "repeated_measures_long": "Повторные измерения (длинный формат)",
    "time_series": "Временной ряд",
    "experimental": "Экспериментальное исследование",
    "rct": "Рандомизированное контролируемое исследование",
    "case_control": "Случай-контроль",
    "cohort": "Когортное исследование",
    "single_group": "Одна группа (пре-пост)",
    "two_groups": "Две группы (межгрупповое сравнение)",
    "multi_group": "Множественные группы",
}

_DESIGN_TYPE_LABELS_EN = {
    "cross_sectional": "Cross-sectional study",
    "longitudinal": "Longitudinal study",
    "repeated_measures": "Repeated measures",
    "repeated_measures_wide": "Repeated measures (wide format)",
    "repeated_measures_long": "Repeated measures (long format)",
    "time_series": "Time series",
    "experimental": "Experimental study",
    "rct": "Randomized controlled trial",
    "case_control": "Case-control study",
    "cohort": "Cohort study",
    "single_group": "Single group (pre-post)",
    "two_groups": "Two groups (between-group comparison)",
    "multi_group": "Multiple groups",
}


def _fmt_stat(v: Any, digits: int = 2) -> str:
    """Format a numeric value for report display."""
    try:
        if v is None:
            return "-"
        f = float(v)
        return f"{f:.{digits}f}" if np.isfinite(f) else "-"
    except Exception:
        return "-"


class ProtocolReport:
    """
    Generates a comprehensive HTML report from a Protocol Analysis Run.
    V2 Report Engine supporting multi-step protocols.
    """
    
    def __init__(self, run_data: Dict, dataset_name: str = "Dataset", style: str = "gost", options: Optional[Dict[str, Any]] = None):
        self.data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})  # The full results.json
        self.dataset_name = dataset_name
        self.style = style or "gost"
        self.options = options if isinstance(options, dict) else {}
        self.html_parts = []
        self.is_ru = False
        
    def generate_html(self) -> str:
        self._add_header()

        try:
            from app.core.pipeline import PipelineManager

            result_ir = PipelineManager.build_result_ir(self.data)
        except Exception:
            result_ir = {}

        blocks = result_ir.get("blocks") if isinstance(result_ir, dict) else None
        if not isinstance(blocks, list):
            blocks = []

        results = self.data.get("results", {})
        step_meta_map = self.data.get("step_meta") if isinstance(self.data, dict) else None
        if not isinstance(step_meta_map, dict):
            step_meta_map = {}

        import re

        def iter_steps():
            if blocks:
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    step_id = block.get("id")
                    res = block.get("payload")
                    if isinstance(step_id, str) and isinstance(res, dict):
                        yield step_id, res
                return
            if isinstance(results, dict):
                for step_id, res in results.items():
                    if isinstance(step_id, str) and isinstance(res, dict):
                        yield step_id, res

        raw_steps = list(iter_steps())
        integrity_ctx = build_report_integrity_context(self.data)
        filtered_steps, filter_meta = filter_step_pairs_for_report(raw_steps, integrity_ctx)
        self._report_integrity_ctx = integrity_ctx
        self._report_step_filter = filter_meta
        deduped = _dedupe_step_payloads(filtered_steps)

        self._add_overview()
        self._add_provenance()
        self._add_protocol_validation()
        self._add_study_design()
        self._add_data_quality_section()
        self._add_methods()
        self._add_hypothesis_discovery()
        self._add_global_descriptive_section()

        def _visit_sort_key(v: Optional[str]) -> tuple:
            if not v:
                return (1, 1_000_000, "")
            s = str(v).strip()
            m = re.search(r"\bV\s*(\d+)\b", s, flags=re.IGNORECASE)
            if m:
                try:
                    return (0, int(m.group(1)), "")
                except Exception:
                    return (0, 1_000_000, s)
            try:
                return (0, int(float(s)), "")
            except Exception:
                return (0, 1_000_000, s)

        def _extract_visit(step_id: str, meta: Dict[str, Any]) -> Optional[str]:
            for k in ["visit", "timepoint", "time", "visit_label", "time_label", "v"]:
                v = meta.get(k) if isinstance(meta, dict) else None
                if isinstance(v, (int, float)):
                    try:
                        return f"V{int(v)}"
                    except Exception:
                        pass
                if isinstance(v, str) and v.strip():
                    s = v.strip()
                    m = re.search(r"\bV\s*(\d+)\b", s, flags=re.IGNORECASE)
                    if m:
                        return f"V{m.group(1)}"
                    return s

            where = meta.get("filter") if isinstance(meta, dict) else None
            if isinstance(where, dict):
                col = str(where.get("col") or where.get("column") or "").strip().lower()
                val = where.get("value") if "value" in where else where.get("val")
                if col and any(x in col for x in ["visit", "визит", "time", "точк", "v"]):
                    if isinstance(val, (int, float)):
                        try:
                            return f"V{int(val)}"
                        except Exception:
                            pass
                    if isinstance(val, str) and val.strip():
                        s = val.strip()
                        m = re.search(r"\bV\s*(\d+)\b", s, flags=re.IGNORECASE)
                        if m:
                            return f"V{m.group(1)}"
                        return s

            m = re.search(r"(?:^|[_\-])v\s*(\d+)(?:$|[_\-])", step_id, flags=re.IGNORECASE)
            if m:
                return f"V{m.group(1)}"
            m = re.search(r"\bV\s*(\d+)\b", step_id, flags=re.IGNORECASE)
            if m:
                return f"V{m.group(1)}"
            return None

        def _extract_target(res: Dict[str, Any], meta: Dict[str, Any]) -> Optional[str]:
            cfg = meta.get("config") if isinstance(meta, dict) else None
            if isinstance(cfg, dict):
                for k in ["target", "outcome", "endpoint", "y"]:
                    v = cfg.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            for k in ["target", "outcome", "endpoint", "y"]:
                v = meta.get(k) if isinstance(meta, dict) else None
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in ["target", "outcome", "endpoint", "y"]:
                v = res.get(k) if isinstance(res, dict) else None
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        def _type_weight(t: Optional[str]) -> int:
            m = {
                "table_1": 0,
                "compare": 1,
                "hypothesis_test": 1,
                "regression": 2,
                "correlation": 3,
                "clustered_correlation": 3,
                "mixed_effects": 4,
                "survival": 5,
                "responders": 6,
                "batch_compare_by_factor": 7,
            }
            return int(m.get(str(t or "").strip(), 99))

        is_ru = bool(getattr(self, "is_ru", False))

        enriched = []
        for e in deduped:
            step_id = e.get("step_id") if isinstance(e, dict) else None
            payload = e.get("res") if isinstance(e, dict) else None
            if not isinstance(step_id, str) or not isinstance(payload, dict):
                continue
            meta = step_meta_map.get(step_id)
            meta = meta if isinstance(meta, dict) else {}
            target = _extract_target(payload, meta)
            visit = _extract_visit(step_id, meta)
            enriched.append({"step_id": step_id, "res": payload, "dup_count": int(e.get("dup_count") or 1), "target": target, "visit": visit, "rtype": payload.get("type")})

        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for row in enriched:
            t = row.get("target")
            v = row.get("visit")
            t_label = str(t) if t else ("Без показателя" if is_ru else "Unspecified target")
            v_label = str(v) if v else ("Все визиты" if is_ru else "All visits")
            grouped.setdefault(t_label, {}).setdefault(v_label, []).append(row)

        def _target_sort_key(label: str) -> tuple:
            if label in {"Без показателя", "Unspecified target"}:
                return (1, "")
            return (0, label.casefold())

        ordered_targets = sorted(grouped.keys(), key=_target_sort_key)
        ordered_deduped: List[Dict[str, Any]] = []
        for t_label in ordered_targets:
            visits_map = grouped.get(t_label) or {}
            ordered_visits = sorted(visits_map.keys(), key=lambda vv: _visit_sort_key(None if vv in {"Все визиты", "All visits"} else vv))
            for v_label in ordered_visits:
                items = visits_map.get(v_label) or []
                items_sorted = sorted(items, key=lambda r: (_type_weight(r.get("rtype")), str(r.get("step_id"))))
                ordered_deduped.extend(items_sorted)

        if grouped:
            self._add_editorial_index(grouped, ordered_targets, step_meta_map=step_meta_map)

        toc_map = {e["step_id"]: e["res"] for e in ordered_deduped if isinstance(e, dict) and isinstance(e.get("step_id"), str) and isinstance(e.get("res"), dict)}
        self._add_toc(toc_map, step_meta_map=step_meta_map)

        self._skip_table1_steps = self._add_table1_multi(ordered_deduped, step_meta_map)
        if not self._skip_table1_steps:
            self._skip_table1_steps = self._add_batch_descriptive_bridge(ordered_deduped, step_meta_map)

        total_steps = len(filtered_steps)
        source_total_steps = int(filter_meta.get("source_total_steps") or len(raw_steps))
        excluded_steps = len(filter_meta.get("excluded_step_ids") or [])
        unique_steps = len(deduped)
        removed = max(0, total_steps - unique_steps)
        type_counts = Counter([str((e.get("res") or {}).get("type") or "result") for e in deduped if isinstance(e, dict)])
        type_lines = "".join(
            [
                f"<tr><td>{html.escape(t)}</td><td class=\"stat-val\">{int(c)}</td></tr>"
                for t, c in sorted(type_counts.items(), key=lambda x: (-int(x[1]), str(x[0])))
            ]
        )
        self.html_parts.append(
            f"""
            <div class=\"card\" id=\"summary\">
                <h2>{'Сводка отчёта' if is_ru else 'Report Summary'}</h2>
                <table>
                    <tbody>
                        <tr><td><strong>{'Шагов (всего)' if is_ru else 'Steps (total)'}</strong></td><td class=\"stat-val\">{total_steps}</td></tr>
                        <tr><td><strong>{'Шагов (до фильтра)' if is_ru else 'Steps (source)'}</strong></td><td class=\"stat-val\">{source_total_steps}</td></tr>
                        <tr><td><strong>{'Исключено верификатором' if is_ru else 'Excluded by verifier'}</strong></td><td class=\"stat-val\">{excluded_steps}</td></tr>
                        <tr><td><strong>{'Шагов (уникальных)' if is_ru else 'Steps (unique)'}</strong></td><td class=\"stat-val\">{unique_steps}</td></tr>
                        <tr><td><strong>{'Свернуто повторов' if is_ru else 'Duplicates collapsed'}</strong></td><td class=\"stat-val\">{removed}</td></tr>
                    </tbody>
                </table>
                <h3 style=\"margin-top: 14px;\">{'Состав по типам' if is_ru else 'By type'}</h3>
                <table>
                    <thead><tr><th>{'Тип' if is_ru else 'Type'}</th><th>{'Количество' if is_ru else 'Count'}</th></tr></thead>
                    <tbody>{type_lines}</tbody>
                </table>
            </div>
            """
        )

        self.html_parts.append(
            f"""
            <div class="card" id="results">
                <h2>{'Результаты' if is_ru else 'Results'}</h2>
                <p>{'Ниже представлены результаты по шагам протокола.' if is_ru else 'Step-by-step protocol results are presented below.'}</p>
            </div>
            """
        )
        
        for e in ordered_deduped:
            res = e.get("res") if isinstance(e, dict) else None
            step_id = e.get("step_id") if isinstance(e, dict) else None
            dup_count = int(e.get("dup_count") or 1) if isinstance(e, dict) else 1
            if not isinstance(res, dict) or not isinstance(step_id, str):
                continue
            if res.get("type") == "table_1":
                if not getattr(self, "_skip_table1_steps", False):
                    self._add_table_one(res, step_id, dup_count=dup_count)

        for e in ordered_deduped:
            res = e.get("res") if isinstance(e, dict) else None
            step_id = e.get("step_id") if isinstance(e, dict) else None
            dup_count = int(e.get("dup_count") or 1) if isinstance(e, dict) else 1
            if not isinstance(res, dict) or not isinstance(step_id, str):
                continue
            rtype = res.get("type")
            if rtype in [
                "compare",
                "hypothesis_test",
                "correlation",
                "regression",
                "survival",
                "mixed_effects",
                "clustered_correlation",
                "agreement",
                "assumption_test",
                "time_series",
            ]:
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
                step_meta = step_meta if isinstance(step_meta, dict) else {}
                self._add_analysis_section(res, step_id, dup_count=dup_count, step_meta=step_meta)
            elif rtype == "batch_compare_by_factor":
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
                step_meta = step_meta if isinstance(step_meta, dict) else {}
                self._add_longitudinal_section(res, step_id, step_meta=step_meta)
            elif rtype in {"batch_analysis", "timepoint_batch_analysis"}:
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
                step_meta = step_meta if isinstance(step_meta, dict) else {}
                self._add_batch_section(res, step_id, step_meta=step_meta)
            elif rtype == "responders":
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
                step_meta = step_meta if isinstance(step_meta, dict) else {}
                self._add_responder_section(res, step_id, step_meta=step_meta)
            elif rtype != "table_1":
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
                step_meta = step_meta if isinstance(step_meta, dict) else {}
                self._add_unknown_section(res, step_id, step_meta=step_meta)

        forest_data = self._build_forest_data()
        if isinstance(forest_data.get("effects"), list) and len(forest_data["effects"]) >= 2:
            try:
                forest_png = _render_plot_png_bytes(forest_data, is_ru=self.is_ru)
            except Exception:
                forest_png = None
            if forest_png:
                b64 = base64.b64encode(forest_png).decode()
                self.html_parts.append(
                    f"""
                    <div class="card" id="forest-plot">
                        <h2>{'Лес эффектов (Forest Plot)' if self.is_ru else 'Forest Plot: All Effect Sizes'}</h2>
                        <p><em>{
                            'Красные точки — статистически значимые результаты (p < α). Серые — незначимые.'
                            if self.is_ru else 'Red = significant, grey = non-significant.'
                        }</em></p>
                        <img src="data:image/png;base64,{b64}" style="max-width:100%;" />
                    </div>
                    """
                )

        self._add_discussion_conclusion()
        self._add_limitations()
        self._add_run_log()

        self._add_footer()
        return "\n".join(self.html_parts)

    def _resolve_dataset_dir(self, dataset_id: str) -> Optional[str]:
        return _resolve_dataset_dir_path(dataset_id)

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _build_forest_data(self) -> Dict[str, Any]:
        """Collect all effect sizes from results for forest plot."""
        results = self.data.get("results", {}) if isinstance(self.data, dict) else {}
        if not isinstance(results, dict):
            return {"type": "forest_plot", "plot_hint": "forest_plot", "effects": []}

        effects: List[Dict[str, Any]] = []
        for step_id, res in results.items():
            if not isinstance(res, dict):
                continue

            es = res.get("effect_size")
            es_name = res.get("effect_size_name", "")
            target = res.get("target_variable") or res.get("variable") or res.get("target") or step_id
            ci_l = res.get("effect_size_ci_lower")
            if ci_l is None:
                ci_l = res.get("effect_ci_lower")
            ci_h = res.get("effect_size_ci_upper")
            if ci_h is None:
                ci_h = res.get("effect_ci_upper")
            sig = bool(res.get("significant"))

            if es is not None:
                try:
                    effects.append(
                        {
                            "label": f"{target} ({es_name})" if es_name else str(target),
                            "effect_size": float(es),
                            "ci_lower": float(ci_l) if ci_l is not None else None,
                            "ci_upper": float(ci_h) if ci_h is not None else None,
                            "significant": sig,
                        }
                    )
                except Exception:
                    pass

            items = res.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    ies = item.get("effect_size")
                    ies_name = item.get("effect_size_name", "")
                    itarget = item.get("target") or item.get("variable") or item.get("outcome") or ""
                    ici_l = item.get("effect_size_ci_lower")
                    if ici_l is None:
                        ici_l = item.get("effect_ci_lower")
                    ici_h = item.get("effect_size_ci_upper")
                    if ici_h is None:
                        ici_h = item.get("effect_ci_upper")
                    isig = bool(item.get("significant"))
                    if ies is not None:
                        try:
                            effects.append(
                                {
                                    "label": f"{itarget} ({ies_name})" if ies_name else str(itarget),
                                    "effect_size": float(ies),
                                    "ci_lower": float(ici_l) if ici_l is not None else None,
                                    "ci_upper": float(ici_h) if ici_h is not None else None,
                                    "significant": isig,
                                }
                            )
                        except Exception:
                            pass

        effects.sort(key=lambda x: abs(x.get("effect_size", 0.0)), reverse=True)
        return {"type": "forest_plot", "plot_hint": "forest_plot", "effects": effects[:40]}

    def _add_overview(self):
        is_ru = bool(getattr(self, "is_ru", False))
        dataset_id = self.data.get("dataset_id") if isinstance(self.data, dict) else None
        ds_dir = self._resolve_dataset_dir(str(dataset_id) if dataset_id else "")
        scan_report = {}
        dtypes = {}
        variable_mapping = {}

        if ds_dir:
            processed_dir = os.path.join(ds_dir, "processed")
            scan_path = os.path.join(processed_dir, "scan_report.json")
            dtypes_path = os.path.join(processed_dir, "dtypes.json")
            mapping_path = os.path.join(processed_dir, "variable_mapping.json")
            if os.path.exists(scan_path):
                scan_report = self._load_json(scan_path)
            if os.path.exists(dtypes_path):
                dtypes = self._load_json(dtypes_path)
            if os.path.exists(mapping_path):
                variable_mapping = self._load_json(mapping_path)

        cols = (scan_report.get("columns") if isinstance(scan_report, dict) else None) or {}
        missing_report = scan_report.get("missing_report") if isinstance(scan_report, dict) else None
        sampling_info = scan_report.get("sampling_info") if isinstance(scan_report, dict) else None

        total_rows = None
        columns_with_missing = None
        missing_top = []
        if isinstance(missing_report, dict):
            total_rows = missing_report.get("total_rows")
            columns_with_missing = missing_report.get("columns_with_missing")
            by_col = missing_report.get("by_column")
            if isinstance(by_col, list):
                for row in by_col[:8]:
                    if isinstance(row, dict):
                        missing_top.append(row)

        type_counts: Dict[str, int] = {}
        for _, meta in cols.items():
            if not isinstance(meta, dict):
                continue
            t = str(meta.get("type") or "unknown")
            type_counts[t] = int(type_counts.get(t, 0)) + 1

        group_candidates = []
        for name, meta in cols.items():
            if not isinstance(meta, dict):
                continue
            u = meta.get("unique_count")
            if not isinstance(u, (int, float)):
                continue
            name_l = str(name).strip().lower()
            looks_group = any(k in name_l for k in ["группа", "group", "treatment", "arm", "cohort"]) or str(name) in {"Группа", "group"}
            if looks_group and 2 <= int(u) <= 20:
                group_candidates.append(str(name))

        group_counts: Dict[str, Dict[str, int]] = {}
        if ds_dir and group_candidates:
            try:
                parquet_path = os.path.join(ds_dir, "processed", f"{dataset_id}.parquet")
                if os.path.exists(parquet_path):
                    df = pd.read_parquet(parquet_path, columns=group_candidates)
                    for gc in group_candidates[:2]:
                        vc = df[gc].value_counts(dropna=False).head(12)
                        group_counts[gc] = {str(k): int(v) for k, v in vc.items()}
            except Exception:
                group_counts = {}

        mapping_roles = {}
        if isinstance(variable_mapping, dict) and variable_mapping:
            for col, meta in variable_mapping.items():
                if not isinstance(meta, dict):
                    continue
                role = meta.get("role") or meta.get("analysis_role")
                if isinstance(role, str) and role:
                    mapping_roles.setdefault(role, 0)
                    mapping_roles[role] += 1

        html = f"""
        <div class="card" id="overview">
            <h2>{'Сводка' if is_ru else 'Overview'}</h2>
            <table>
                <tbody>
                    <tr><td><strong>{'ID набора данных' if is_ru else 'Dataset ID'}</strong></td><td>{str(dataset_id) if dataset_id else '-'}</td></tr>
                    <tr><td><strong>{'Строки (скан)' if is_ru else 'Rows (scan)'}</strong></td><td>{str(total_rows) if isinstance(total_rows, (int, float)) else '-'}</td></tr>
                    <tr><td><strong>{'Столбцы (скан)' if is_ru else 'Columns (scan)'}</strong></td><td>{str(len(cols)) if isinstance(cols, dict) else '-'}</td></tr>
                    <tr><td><strong>{'Столбцы с пропусками' if is_ru else 'Columns with missing'}</strong></td><td>{str(columns_with_missing) if isinstance(columns_with_missing, (int, float)) else '-'}</td></tr>
                </tbody>
            </table>
        """

        if type_counts:
            type_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
            html += f"""
            <h3>{'Типы столбцов' if is_ru else 'Column Types'}</h3>
            <table>
                <thead><tr><th>{'Тип' if is_ru else 'Type'}</th><th>{'Количество' if is_ru else 'Count'}</th></tr></thead>
                <tbody>{type_rows}</tbody>
            </table>
            """

        if isinstance(sampling_info, dict) and sampling_info.get("sampled"):
            html += f"""
            <div class="ai-box">
                <strong>{'Сэмплирование при скане' if is_ru else 'Scan sampling'}:</strong> {sampling_info.get('sample_rows')} / {sampling_info.get('total_rows')} {'строк' if is_ru else 'rows'}, {sampling_info.get('scanned_columns')} / {sampling_info.get('total_columns')} {'столбцов' if is_ru else 'columns'}.
            </div>
            """

        if mapping_roles:
            role_rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(mapping_roles.items(), key=lambda kv: (-kv[1], kv[0]))])
            html += f"""
            <h3>{'Роли переменных (маппинг)' if is_ru else 'Variable Mapping Roles'}</h3>
            <table>
                <thead><tr><th>{'Роль' if is_ru else 'Role'}</th><th>{'Количество' if is_ru else 'Count'}</th></tr></thead>
                <tbody>{role_rows}</tbody>
            </table>
            """

        if missing_top:
            miss_rows = "".join([
                f"<tr><td>{str(r.get('column','-'))}</td><td>{str(r.get('missing_count','-'))}</td><td>{str(r.get('missing_percent','-'))}</td></tr>"
                for r in missing_top
            ])
            html += f"""
            <h3>{'Больше всего пропусков' if is_ru else 'Top Missing Columns'}</h3>
            <table>
                <thead><tr><th>{'Столбец' if is_ru else 'Column'}</th><th>{'Пропусков' if is_ru else 'Missing'}</th><th>%</th></tr></thead>
                <tbody>{miss_rows}</tbody>
            </table>
            """

        if group_counts:
            html += f"<h3>{'Распределение по группам' if is_ru else 'Group Distributions'}</h3>"
            for gc, counts in group_counts.items():
                rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in counts.items()])
                html += f"""
                <table>
                    <thead><tr><th colspan="2">{gc}</th></tr><tr><th>{'Значение' if is_ru else 'Value'}</th><th>{'Количество' if is_ru else 'Count'}</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                """

        html += "</div>"
        self.html_parts.append(html)

    def _add_provenance(self):
        is_ru = bool(getattr(self, "is_ru", False))
        dataset_id = self.data.get("dataset_id") if isinstance(self.data, dict) else None
        run_id = self.data.get("run_id") if isinstance(self.data, dict) else None
        ds_dir = self._resolve_dataset_dir(str(dataset_id) if dataset_id else "")

        source_meta: Dict[str, Any] = {}
        source_files: List[str] = []
        if ds_dir:
            source_dir = os.path.join(ds_dir, "source")
            meta_path = os.path.join(source_dir, "meta.json")
            if os.path.exists(meta_path):
                source_meta = self._load_json(meta_path)
            if os.path.isdir(source_dir):
                try:
                    source_files = [
                        str(name)
                        for name in sorted(os.listdir(source_dir))
                        if str(name) not in {"meta.json", ".", ".."} and os.path.isfile(os.path.join(source_dir, str(name)))
                    ]
                except Exception:
                    source_files = []

        source_name = source_meta.get("original_filename") or source_meta.get("filename")
        source_sheet = source_meta.get("sheet_name")
        source_header = source_meta.get("header_row")

        reproducibility = self.data.get("reproducibility") if isinstance(self.data, dict) else None
        reproducibility = reproducibility if isinstance(reproducibility, dict) else {}
        analysis_dataset = self.data.get("analysis_dataset") if isinstance(self.data.get("analysis_dataset"), dict) else None
        if not isinstance(analysis_dataset, dict):
            analysis_dataset = reproducibility.get("analysis_dataset") if isinstance(reproducibility.get("analysis_dataset"), dict) else {}
        analysis_set = self.data.get("analysis_set") if isinstance(self.data.get("analysis_set"), dict) else {}

        run_rel = "-"
        artifacts_rel = "-"
        if dataset_id and run_id:
            run_rel = os.path.join("workspace", "datasets", str(dataset_id), "analysis", str(run_id))
            artifacts_rel = os.path.join(run_rel, "artifacts")

        source_rel = "-"
        if dataset_id and source_files:
            source_rel = os.path.join("workspace", "datasets", str(dataset_id), "source", source_files[0])
        elif source_name:
            source_rel = str(source_name)

        repro_script = reproducibility.get("script")
        repro_payload = reproducibility.get("payload")
        repro_manifest = reproducibility.get("manifest")
        repro_protocol = reproducibility.get("protocol")
        repro_bootstrap_trace = reproducibility.get("bootstrap_trace")
        repro_hypothesis_discovery = reproducibility.get("hypothesis_discovery")
        repro_ready = reproducibility.get("ready")

        integrity_ctx = getattr(self, "_report_integrity_ctx", None)
        if not isinstance(integrity_ctx, dict):
            integrity_ctx = build_report_integrity_context(self.data)
        verification_ctx = integrity_ctx.get("verification") if isinstance(integrity_ctx.get("verification"), dict) else {}
        provenance_ctx = integrity_ctx.get("provenance") if isinstance(integrity_ctx.get("provenance"), dict) else {}
        filter_ctx = getattr(self, "_report_step_filter", None)
        if not isinstance(filter_ctx, dict):
            filter_ctx = {}

        verification_status = str(verification_ctx.get("status") or "missing").strip().lower()
        verification_present = bool(verification_ctx.get("present"))
        excluded_step_ids = [
            str(x).strip()
            for x in (filter_ctx.get("excluded_step_ids") if isinstance(filter_ctx.get("excluded_step_ids"), list) else [])
            if isinstance(x, str) and x.strip()
        ]
        excluded_step_ids_set = set(excluded_step_ids)

        if verification_status in {"passed", "ok"}:
            verification_label = "пройдено" if is_ru else "passed"
        elif verification_status in {"failed", "error", "blocked"}:
            verification_label = "ошибка" if is_ru else "failed"
        elif verification_present:
            verification_label = verification_status
        else:
            verification_label = "отсутствует" if is_ru else "missing"

        run_state_value = str(provenance_ctx.get("state") or "-")
        missing_state_artifacts = provenance_ctx.get("missing_state_artifacts")
        missing_state_artifacts = (
            [str(x) for x in missing_state_artifacts if str(x).strip()]
            if isinstance(missing_state_artifacts, list)
            else []
        )
        missing_state_artifacts_text = _preview_values(missing_state_artifacts, limit=8) or "-"
        missing_repro_fields = provenance_ctx.get("missing_reproducibility_fields")
        missing_repro_fields = (
            [str(x) for x in missing_repro_fields if str(x).strip()]
            if isinstance(missing_repro_fields, list)
            else []
        )
        missing_repro_fields_text = _preview_values(missing_repro_fields, limit=8) or "-"

        artifacts_list = reproducibility.get("artifacts") if isinstance(reproducibility.get("artifacts"), list) else []
        artifacts_preview = _preview_values(artifacts_list, limit=6) if artifacts_list else "-"

        rows = [
            (
                "ID набора данных" if is_ru else "Dataset ID",
                str(dataset_id) if dataset_id else "-",
            ),
            (
                "ID запуска (run_id)" if is_ru else "Run ID",
                str(run_id) if run_id else "-",
            ),
            (
                "Исходный файл" if is_ru else "Source file",
                str(source_name) if source_name else "-",
            ),
            (
                "Путь источника" if is_ru else "Source path",
                source_rel,
            ),
            (
                "Параметры чтения" if is_ru else "Import settings",
                (
                    f"{'sheet' if not is_ru else 'лист'}={source_sheet if source_sheet is not None else '-'}; "
                    f"{'header_row'}={source_header if source_header is not None else '-'}"
                ),
            ),
            (
                "Рабочая выборка (analysis_dataset)" if is_ru else "Analysis dataset",
                (
                    f"rows={analysis_dataset.get('rows', '-')}, cols={analysis_dataset.get('columns', '-')}, "
                    f"xlsx={analysis_dataset.get('xlsx', '-')}, parquet={analysis_dataset.get('parquet', '-')}"
                ),
            ),
            (
                "Замороженная выборка (analysis_set)" if is_ru else "Frozen analysis set",
                (
                    f"id={analysis_set.get('analysis_set_id', '-')}; "
                    f"n_selected={analysis_set.get('n_selected', '-')}; "
                    f"mode={analysis_set.get('mode', '-')}; enforce={analysis_set.get('enforce', '-')}"
                ),
            ),
            (
                "Воспроизводимость" if is_ru else "Reproducibility",
                (
                    f"ready={repro_ready}; "
                    f"script={repro_script or '-'}; payload={repro_payload or '-'}; "
                    f"manifest={repro_manifest or '-'}; protocol={repro_protocol or '-'}"
                ),
            ),
            (
                "Артефакт bootstrap-трассировки" if is_ru else "Bootstrap trace artifact",
                str(repro_bootstrap_trace or "-"),
            ),
            (
                "Артефакт гипотез" if is_ru else "Hypothesis discovery artifact",
                str(repro_hypothesis_discovery or "-"),
            ),
            (
                "Статус верификации" if is_ru else "Verification status",
                verification_label,
            ),
            (
                "Исключено шагов в отчёте" if is_ru else "Steps excluded from report",
                str(len(excluded_step_ids)),
            ),
            (
                "Состояние run_state" if is_ru else "Run state",
                run_state_value or "-",
            ),
            (
                "run_state: отсутствующие артефакты"
                if is_ru
                else "run_state missing artifacts",
                missing_state_artifacts_text,
            ),
            (
                "reproducibility: недостающие поля"
                if is_ru
                else "reproducibility missing fields",
                missing_repro_fields_text,
            ),
            (
                "Артефакты запуска" if is_ru else "Run artifacts",
                artifacts_preview,
            ),
            (
                "Путь запуска" if is_ru else "Run path",
                run_rel,
            ),
            (
                "Путь артефактов" if is_ru else "Artifacts path",
                artifacts_rel,
            ),
        ]
        rows.extend(
            _protocol_validation_provenance_rows(
                self.data if isinstance(self.data, dict) else {},
                is_ru=is_ru,
                dataset_id=dataset_id,
                run_id=run_id,
            )
        )

        rows_html = "".join(
            [
                "<tr>"
                + f"<td><strong>{html.escape(str(k))}</strong></td>"
                + f"<td>{html.escape(str(v))}</td>"
                + "</tr>"
                for k, v in rows
            ]
        )

        step_meta_map = self.data.get("step_meta") if isinstance(self.data.get("step_meta"), dict) else {}
        results = self.data.get("results") if isinstance(self.data.get("results"), dict) else {}
        step_ids: List[str] = []
        if isinstance(step_meta_map, dict):
            for sid in step_meta_map.keys():
                if isinstance(sid, str) and sid:
                    if sid in excluded_step_ids_set:
                        continue
                    step_ids.append(sid)
        if isinstance(results, dict):
            for sid in results.keys():
                if isinstance(sid, str) and sid and sid not in step_ids and sid not in excluded_step_ids_set:
                    step_ids.append(sid)

        plan_rows: List[str] = []
        for sid in step_ids[:180]:
            meta = step_meta_map.get(sid) if isinstance(step_meta_map.get(sid), dict) else {}
            res = results.get(sid) if isinstance(results.get(sid), dict) else {}
            cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}

            method_hint = cfg.get("method_id") or meta.get("method")
            method_hint_s = str(method_hint or "").strip().lower()
            method_obj = res.get("method") if isinstance(res.get("method"), dict) else {}
            method_id = (
                method_obj.get("id")
                or method_obj.get("name")
                or res.get("method_id")
                or method_hint
                or res.get("type")
            )
            method_label = _method_label_from_id(method_id, is_ru) or _method_label_from_type(res.get("type"), is_ru) or str(method_id or "-")
            scope = _step_scope_summary(meta, res, is_ru)

            rationale = None
            step_type = str(res.get("type") or "").strip().lower()
            if step_type in {"batch_analysis", "timepoint_batch_analysis"}:
                rationale = _batch_method_selection_rationale(meta, res, is_ru)
            elif is_ru:
                rationale = _method_selection_rationale_ru(res)

            if not rationale and method_hint_s and method_hint_s not in {"auto", "none"}:
                forced_label = _method_label_from_id(method_hint_s, is_ru) or method_hint_s
                rationale = (
                    f"Метод принудительно задан в протоколе: {forced_label}."
                    if is_ru
                    else f"Method is explicitly fixed by protocol: {forced_label}."
                )

            plan_rows.append(
                "<tr>"
                + f"<td>{html.escape(str(sid))}</td>"
                + f"<td>{html.escape(str(method_label))}</td>"
                + f"<td>{html.escape(str(scope))}</td>"
                + f"<td>{html.escape(str(rationale or '-'))}</td>"
                + "</tr>"
            )

        plan_table = ""
        if plan_rows:
            plan_table = f"""
            <h3>{'Карта шагов протокола: выборка, подгруппы и сравнения' if is_ru else 'Protocol map: cohort, subgroups and comparisons'}</h3>
            <table>
                <thead>
                    <tr>
                        <th>{'ID шага' if is_ru else 'Step ID'}</th>
                        <th>{'Метод' if is_ru else 'Method'}</th>
                        <th>{'Что сравнивается' if is_ru else 'Scope'}</th>
                        <th>{'Обоснование выбора теста' if is_ru else 'Selection rationale'}</th>
                    </tr>
                </thead>
                <tbody>{''.join(plan_rows)}</tbody>
            </table>
            """

        self.html_parts.append(
            f"""
            <div class="card" id="provenance">
                <h2>{'Воспроизводимость и provenance' if is_ru else 'Reproducibility and provenance'}</h2>
                <table>
                    <tbody>{rows_html}</tbody>
                </table>
                {plan_table}
            </div>
            """
        )

    def _add_protocol_validation(self):
        is_ru = bool(getattr(self, "is_ru", False))
        ctx = _protocol_validation_section_context(self.data if isinstance(self.data, dict) else {}, is_ru=is_ru)
        if not isinstance(ctx, dict) or not ctx.get("present"):
            return

        summary_rows = ctx.get("summary_rows") if isinstance(ctx.get("summary_rows"), list) else []
        issue_rows = ctx.get("issues") if isinstance(ctx.get("issues"), list) else []
        global_errors = ctx.get("global_errors") if isinstance(ctx.get("global_errors"), list) else []

        summary_html = "".join(
            [
                "<tr>"
                + f"<td><strong>{html.escape(str(k))}</strong></td>"
                + f"<td>{html.escape(str(v))}</td>"
                + "</tr>"
                for k, v in summary_rows
            ]
        )

        issues_html = ""
        if issue_rows:
            issue_body = "".join(
                [
                    "<tr>"
                    + f"<td>{html.escape(str(row.get('step_id') or '-'))}</td>"
                    + f"<td>{html.escape(str(row.get('method') or '-'))}</td>"
                    + f"<td>{html.escape(str(row.get('status') or '-'))}</td>"
                    + f"<td>{html.escape(str(row.get('issues') or '-'))}</td>"
                    + "</tr>"
                    for row in issue_rows
                    if isinstance(row, dict)
                ]
            )
            if issue_body:
                issues_html = f"""
                <h3>{'Проблемные шаги валидации' if is_ru else 'Validation findings by step'}</h3>
                <table>
                    <thead>
                        <tr>
                            <th>{'Шаг' if is_ru else 'Step'}</th>
                            <th>{'Метод' if is_ru else 'Method'}</th>
                            <th>{'Статус' if is_ru else 'Status'}</th>
                            <th>{'Замечания' if is_ru else 'Findings'}</th>
                        </tr>
                    </thead>
                    <tbody>{issue_body}</tbody>
                </table>
                """
        if not issues_html:
            issues_html = (
                f"<p>{'Критичных замечаний по шагам не найдено.' if is_ru else 'No critical step findings were detected.'}</p>"
            )

        global_errors_html = ""
        if global_errors:
            li = "".join([f"<li>{html.escape(str(msg))}</li>" for msg in global_errors])
            global_errors_html = f"""
            <h3>{'Глобальные ошибки валидации' if is_ru else 'Global validation errors'}</h3>
            <ul>{li}</ul>
            """

        self.html_parts.append(
            f"""
            <div class="card" id="protocol-validation">
                <h2>{'Валидация протокола' if is_ru else 'Protocol Validation'}</h2>
                <table><tbody>{summary_html}</tbody></table>
                {global_errors_html}
                {issues_html}
            </div>
            """
        )

    def _add_study_design(self):
        is_ru = bool(getattr(self, "is_ru", False))
        dataset_id = self.data.get("dataset_id") if isinstance(self.data, dict) else None
        ds_dir = self._resolve_dataset_dir(str(dataset_id) if dataset_id else "")
        study: Dict[str, Any] = {}
        design_warning = None
        if not ds_dir:
            design_warning = (
                "Секция дизайна недоступна: dataset_id отсутствует в артефакте запуска."
                if is_ru
                else "Design section unavailable: dataset_id missing in run artifacts."
            )
        else:
            study_path = os.path.join(ds_dir, "processed", "study_design.json")
            if not os.path.exists(study_path):
                design_warning = (
                    "Секция дизайна пустая: файл study_design.json не найден."
                    if is_ru
                    else "Design section empty: study_design.json was not found."
                )
            else:
                loaded = self._load_json(study_path)
                if isinstance(loaded, dict):
                    study = loaded
                else:
                    design_warning = (
                        "Секция дизайна пустая: study_design.json не удалось прочитать."
                        if is_ru
                        else "Design section empty: study_design.json could not be parsed."
                    )

        if design_warning:
            html_warning = f"""
            <div class="card" id="design">
                <h2>{'Дизайн исследования' if is_ru else 'Study Design'}</h2>
                <p style="color:#b91c1c;"><strong>{'Предупреждение' if is_ru else 'Warning'}:</strong> {html.escape(design_warning)}</p>
            </div>
            """
            self.html_parts.append(html_warning)
            return

        design = study.get("design") if isinstance(study.get("design"), dict) else {}
        policy = study.get("analysis_policy") if isinstance(study.get("analysis_policy"), dict) else {}
        design_type_raw = str(design.get("design_type") or "-")
        design_type_display = (
            _DESIGN_TYPE_LABELS_RU.get(design_type_raw, design_type_raw)
            if is_ru
            else _DESIGN_TYPE_LABELS_EN.get(design_type_raw, design_type_raw)
        )

        design_html = f"""
        <div class="card" id="design">
            <h2>{'Дизайн исследования' if is_ru else 'Study Design'}</h2>
            <table>
                <tbody>
                    <tr><td><strong>{'Тип дизайна' if is_ru else 'Design type'}</strong></td><td>{html.escape(design_type_display)}</td></tr>
                    <tr><td><strong>{'Группировка' if is_ru else 'Group'}</strong></td><td>{html.escape(str(design.get('group_column') or '-'))}</td></tr>
                    <tr><td><strong>{'Время/визит' if is_ru else 'Time'}</strong></td><td>{html.escape(str(design.get('time_column') or '-'))}</td></tr>
                    <tr><td><strong>{'ID субъекта' if is_ru else 'Subject ID'}</strong></td><td>{html.escape(str(design.get('subject_column') or '-'))}</td></tr>
                </tbody>
            </table>
        """

        outcomes = design.get("outcomes")
        if isinstance(outcomes, list) and outcomes:
            design_html += f"""
            <h3>{'Числовые исходы (топ)' if is_ru else 'Numeric outcomes (top)'}</h3>
            <div style="color:#475569;">{html.escape(', '.join([str(o) for o in outcomes[:20]]))}</div>
            """

        cat_outcomes = design.get("categorical_outcomes")
        if isinstance(cat_outcomes, list) and cat_outcomes:
            design_html += f"""
            <h3>{'Категориальные исходы (топ)' if is_ru else 'Categorical outcomes (top)'}</h3>
            <div style="color:#475569;">{html.escape(', '.join([str(o) for o in cat_outcomes[:15]]))}</div>
            """

        endpoint_groups = design.get("endpoint_groups") if isinstance(design.get("endpoint_groups"), list) else []
        if endpoint_groups:
            rows = []
            for item in endpoint_groups[:12]:
                if not isinstance(item, dict):
                    continue
                ep = item.get("endpoint") or "endpoint"
                tps = item.get("timepoints") if isinstance(item.get("timepoints"), list) else []
                tp_line = ", ".join([str(t) for t in tps]) if tps else "-"
                rows.append(f"<tr><td>{html.escape(str(ep))}</td><td>{html.escape(tp_line)}</td></tr>")
            if rows:
                design_html += f"""
                <h3>{'Endpoint-группы' if is_ru else 'Endpoint groups'}</h3>
                <table>
                    <thead><tr><th>{'Endpoint' if is_ru else 'Endpoint'}</th><th>{'Визиты' if is_ru else 'Visits'}</th></tr></thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
                """

        if policy:
            runtime_multiplicity_policy = _extract_multiplicity_policy(
                self.data if isinstance(self.data, dict) else {},
                (
                    self.data.get("protocol_validation")
                    if isinstance(self.data, dict) and isinstance(self.data.get("protocol_validation"), dict)
                    else None
                ),
            )
            multiplicity_raw = (
                policy.get("multiplicity_correction")
                or runtime_multiplicity_policy.get("correction")
                or runtime_multiplicity_policy.get("multiplicity_correction")
            )
            multiplicity_label = _format_correction_label(multiplicity_raw, is_ru) if multiplicity_raw else ""
            if multiplicity_label:
                multiplicity_display = multiplicity_label
            else:
                multiplicity_display = str(multiplicity_raw or "-")
            post_hoc_correction_raw = (
                policy.get("post_hoc_correction")
                or runtime_multiplicity_policy.get("post_hoc_correction")
            )
            post_hoc_correction_label = _format_correction_label(post_hoc_correction_raw, is_ru) if post_hoc_correction_raw else ""
            if post_hoc_correction_label:
                post_hoc_correction_display = post_hoc_correction_label
            else:
                post_hoc_correction_display = str(post_hoc_correction_raw or "-")
            runtime_bootstrap_policy = _extract_bootstrap_policy(
                self.data if isinstance(self.data, dict) else {},
                (
                    self.data.get("protocol_validation")
                    if isinstance(self.data, dict) and isinstance(self.data.get("protocol_validation"), dict)
                    else None
                ),
            )
            bootstrap_enabled_raw = policy.get("bootstrap_ci")
            if bootstrap_enabled_raw is None:
                bootstrap_enabled_raw = runtime_bootstrap_policy.get("enabled")
            bootstrap_samples_raw = policy.get("bootstrap_samples")
            if bootstrap_samples_raw is None:
                bootstrap_samples_raw = runtime_bootstrap_policy.get("samples")
            bootstrap_display = _format_boolean_label(bool(bootstrap_enabled_raw), is_ru) if bootstrap_enabled_raw is not None else "-"
            bootstrap_samples_display = "-"
            try:
                if bootstrap_samples_raw is not None:
                    bootstrap_samples_display = str(int(bootstrap_samples_raw))
            except Exception:
                bootstrap_samples_display = str(bootstrap_samples_raw or "-")
            multiplicity_applied_display = "-"
            try:
                multiplicity_applied_raw = runtime_multiplicity_policy.get("n_applied_steps")
                if multiplicity_applied_raw is not None:
                    multiplicity_applied_display = str(int(multiplicity_applied_raw))
            except Exception:
                multiplicity_applied_display = str(runtime_multiplicity_policy.get("n_applied_steps") or "-")
            design_html += f"""
            <h3>{'Политика анализа' if is_ru else 'Analysis policy'}</h3>
            <table>
                <tbody>
                    <tr><td><strong>α</strong></td><td>{html.escape(str(policy.get('alpha') or '-'))}</td></tr>
                    <tr><td><strong>{'Поправка' if is_ru else 'Correction'}</strong></td><td>{html.escape(multiplicity_display)}</td></tr>
                    <tr><td><strong>Post-hoc</strong></td><td>{html.escape(str(policy.get('post_hoc') or '-'))}</td></tr>
                    <tr><td><strong>{'Post-hoc поправка' if is_ru else 'Post-hoc correction'}</strong></td><td>{html.escape(str(post_hoc_correction_display))}</td></tr>
                    <tr><td><strong>{'Применено шагов (multiplicity)' if is_ru else 'Multiplicity applied steps'}</strong></td><td>{html.escape(str(multiplicity_applied_display))}</td></tr>
                    <tr><td><strong>Bootstrap CI</strong></td><td>{html.escape(str(bootstrap_display))}</td></tr>
                    <tr><td><strong>Bootstrap samples</strong></td><td>{html.escape(str(bootstrap_samples_display))}</td></tr>
                </tbody>
            </table>
            """

        design_html += "</div>"
        self.html_parts.append(design_html)

    def _add_data_quality_section(self):
        """Render Data Quality section with cleaning log and excluded column reasons."""
        is_ru = bool(getattr(self, "is_ru", False))
        dataset_id = self.data.get("dataset_id") if isinstance(self.data, dict) else None
        ds_dir = self._resolve_dataset_dir(str(dataset_id) if dataset_id else "")

        scan_report: Dict[str, Any] = {}
        cleaning_log: Dict[str, Any] = {}
        if ds_dir:
            scan_path = os.path.join(ds_dir, "processed", "scan_report.json")
            if os.path.exists(scan_path):
                scan_report = self._load_json(scan_path) or {}
            cl_path = os.path.join(ds_dir, "processed", "cleaning_log.json")
            if not os.path.exists(cl_path):
                cl_path = os.path.join(ds_dir, "processed", "dataset_cleaning_log.json")
            if os.path.exists(cl_path):
                cleaning_log = self._load_json(cl_path) or {}

        protocol_run = self.data.get("protocol_plan") if isinstance(self.data, dict) else None
        if not isinstance(protocol_run, dict):
            protocol_run = {}
        col_report = (
            protocol_run.get("column_selection_report")
            if isinstance(protocol_run.get("column_selection_report"), dict)
            else {}
        )
        if not col_report:
            col_report = (
                self.data.get("column_selection_report")
                if isinstance(self.data, dict) and isinstance(self.data.get("column_selection_report"), dict)
                else {}
            )

        columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else {}
        if not isinstance(columns_meta, dict):
            columns_meta = {}
        total_cols = len(columns_meta)
        analyzed_total = col_report.get("analyzed_total", "?")
        excluded_total = col_report.get("excluded_total", "?")

        cl_steps = cleaning_log.get("steps") if isinstance(cleaning_log, dict) else []
        cl_steps = cl_steps if isinstance(cl_steps, list) else []
        rows_original = cleaning_log.get("rows_original", "?")
        rows_final = cleaning_log.get("rows_final", "?")
        cols_original = cleaning_log.get("cols_original", "?")
        cols_final = cleaning_log.get("cols_final", "?")
        quality_score = cleaning_log.get("overall_quality_score")

        cleaning_rows = ""
        for step_data in cl_steps:
            if not isinstance(step_data, dict):
                continue
            action = step_data.get("action", "-")
            details = step_data.get("details") if isinstance(step_data.get("details"), dict) else {}
            summary_parts: List[str] = []
            if action == "remove_duplicates":
                summary_parts.append(f"Удалено дубликатов: {details.get('rows_removed', 0)}")
            elif action == "drop_high_missing_columns":
                dropped = details.get("dropped", [])
                threshold_raw = details.get("threshold", 0.7)
                try:
                    threshold = float(threshold_raw)
                except Exception:
                    threshold = 0.7
                summary_parts.append(f"Удалено столбцов (>{threshold:.0%} пропусков): {len(dropped)}")
                if dropped:
                    summary_parts.append(f"  → {', '.join(str(c) for c in dropped[:10])}")
                    if len(dropped) > 10:
                        summary_parts.append(f"  ... и ещё {len(dropped) - 10}")
            elif action == "impute_missing_numeric":
                cols_imputed = details.get("columns", {})
                total_filled = details.get("total_filled", 0)
                strategy = details.get("strategy", "median")
                summary_parts.append(
                    f"Импутация ({strategy}): {len(cols_imputed)} столбцов, "
                    f"{total_filled} значений"
                )
            elif action == "impute_missing_categorical":
                cols_imputed = details.get("columns", {})
                summary_parts.append(f"Импутация (мода): {len(cols_imputed)} столбцов")
            elif action == "outlier_detection":
                total_out = details.get("total_outliers", 0)
                policy = details.get("policy", "flag")
                n_cols = len(details.get("columns", {}))
                summary_parts.append(f"Выбросы (IQR, {policy}): {total_out} в {n_cols} столбцах")
            else:
                summary_parts.append(str(action))

            for sp in summary_parts:
                cleaning_rows += f"<tr><td>{html.escape(str(action))}</td><td>{html.escape(sp)}</td></tr>"

        if not cleaning_rows:
            cleaning_rows = (
                f"<tr><td colspan='2'>{'Лог очистки не найден' if is_ru else 'Cleaning log not found'}</td></tr>"
            )

        excluded = col_report.get("excluded", {})
        excluded_rows = ""
        categories = [
            ("id_like", "ID-подобные" if is_ru else "ID-like"),
            ("group_time_subject", "Группировка / время / субъект" if is_ru else "Group / time / subject"),
            ("high_missing", "Высокая доля пропусков (>70%)" if is_ru else "High missing (>70%)"),
            ("constant", "Константные" if is_ru else "Constant"),
            ("mixed_types", "Смешанные типы" if is_ru else "Mixed types"),
            ("not_in_analysis", "Не включены (прочие причины)" if is_ru else "Not included (other)"),
        ]
        for key, label in categories:
            cols = excluded.get(key, []) if isinstance(excluded, dict) else []
            if not cols:
                continue
            cols_list = cols if isinstance(cols, list) else [str(cols)]
            preview = ", ".join(str(c) for c in cols_list[:8])
            if len(cols_list) > 8:
                preview += f" ... (+{len(cols_list) - 8})"
            excluded_rows += (
                f"<tr><td><strong>{html.escape(label)}</strong></td>"
                f"<td>{len(cols_list)}</td>"
                f"<td>{html.escape(preview)}</td></tr>"
            )

        if not excluded_rows:
            excluded_rows = (
                f"<tr><td colspan='3'>{'Нет данных об исключённых столбцах' if is_ru else 'No excluded column data'}</td></tr>"
            )

        recs = col_report.get("recommendations", []) if isinstance(col_report, dict) else []
        recs_html = ""
        if isinstance(recs, list) and recs:
            recs_li = "".join([f"<li>{html.escape(str(r))}</li>" for r in recs])
            recs_html = f"""
            <h3>{'Рекомендации по доработке первички' if is_ru else 'Recommendations for source data'}</h3>
            <ul>{recs_li}</ul>
            """

        selection_logic = col_report.get("selection_logic", "") if isinstance(col_report, dict) else ""
        logic_html = ""
        if selection_logic:
            logic_html = f"<p><em>{html.escape(str(selection_logic))}</em></p>"

        quality_html = ""
        if quality_score is not None:
            try:
                qs = float(quality_score)
                color = "#16a34a" if qs >= 0.7 else ("#ca8a04" if qs >= 0.4 else "#dc2626")
                quality_html = f"""
                <tr><td><strong>{'Общий балл качества' if is_ru else 'Overall quality score'}</strong></td>
                <td style="color:{color};font-weight:bold;">{qs:.2f}</td></tr>
                """
            except Exception:
                pass

        self.html_parts.append(
            f"""
            <div class="card" id="data-quality">
                <h2>{'Качество данных и очистка' if is_ru else 'Data Quality and Cleaning'}</h2>
                <table>
                    <tbody>
                        <tr><td><strong>{'Строк исходно' if is_ru else 'Original rows'}</strong></td><td>{rows_original}</td></tr>
                        <tr><td><strong>{'Строк после очистки' if is_ru else 'Final rows'}</strong></td><td>{rows_final}</td></tr>
                        <tr><td><strong>{'Столбцов исходно' if is_ru else 'Original columns'}</strong></td><td>{cols_original}</td></tr>
                        <tr><td><strong>{'Столбцов после очистки' if is_ru else 'Final columns'}</strong></td><td>{cols_final}</td></tr>
                        <tr><td><strong>{'Всего столбцов в scan_report' if is_ru else 'Total scan_report columns'}</strong></td><td>{total_cols}</td></tr>
                        <tr><td><strong>{'Столбцов в анализе' if is_ru else 'Columns in analysis'}</strong></td><td>{analyzed_total}</td></tr>
                        <tr><td><strong>{'Исключено столбцов' if is_ru else 'Excluded columns'}</strong></td><td>{excluded_total}</td></tr>
                        {quality_html}
                    </tbody>
                </table>

                <h3>{'Лог очистки' if is_ru else 'Cleaning Log'}</h3>
                <table>
                    <thead><tr>
                        <th>{'Операция' if is_ru else 'Operation'}</th>
                        <th>{'Детали' if is_ru else 'Details'}</th>
                    </tr></thead>
                    <tbody>{cleaning_rows}</tbody>
                </table>

                {logic_html}

                <h3>{'Исключённые столбцы' if is_ru else 'Excluded Columns'}</h3>
                <table>
                    <thead><tr>
                        <th>{'Причина' if is_ru else 'Reason'}</th>
                        <th>{'Кол-во' if is_ru else 'Count'}</th>
                        <th>{'Столбцы' if is_ru else 'Columns'}</th>
                    </tr></thead>
                    <tbody>{excluded_rows}</tbody>
                </table>

                {recs_html}
            </div>
            """
        )

    def _render_assumptions_badge(self, assumptions: Dict[str, Any], is_ru: bool) -> str:
        """Render assumptions check as compact badge-style HTML."""
        if not isinstance(assumptions, dict):
            return ""
        parts: List[str] = []
        for key in ("normality", "homogeneity"):
            info = assumptions.get(key)
            if not isinstance(info, dict):
                continue
            test_name = str(info.get("test", key)).strip().lower()
            p_val = info.get("p")
            if p_val is None:
                p_val = info.get("p_value")
            passed = info.get("passed")
            if p_val is None:
                continue
            try:
                p_f = float(p_val)
                p_str = f"p = {p_f:.3f}" if p_f >= 0.001 else "p < 0.001"
            except Exception:
                p_str = "?"
            if passed is True:
                badge_class = "assumption-pass"
                icon = "✓"
            elif passed is False:
                badge_class = "assumption-fail"
                icon = "✗"
            else:
                badge_class = "assumption-unknown"
                icon = "?"

            label_map_ru = {
                "shapiro": "Нормальность (Shapiro-Wilk)",
                "dagostino": "Нормальность (D'Agostino)",
                "levene": "Однородность дисперсий (Levene)",
                "bartlett": "Однородность (Bartlett)",
                "fligner": "Однородность (Fligner-Killeen)",
                "normality": "Нормальность",
                "homogeneity": "Однородность дисперсий",
            }
            label_map_en = {
                "shapiro": "Normality (Shapiro-Wilk)",
                "dagostino": "Normality (D'Agostino)",
                "levene": "Homogeneity of variance (Levene)",
                "bartlett": "Homogeneity (Bartlett)",
                "fligner": "Homogeneity (Fligner-Killeen)",
                "normality": "Normality",
                "homogeneity": "Homogeneity of variance",
            }
            label = label_map_ru.get(test_name, test_name) if is_ru else label_map_en.get(test_name, test_name)
            parts.append(
                f'<span class="{badge_class}" title="{html.escape(label)}: {html.escape(p_str)}">'
                f'{icon} {html.escape(label)}: {html.escape(p_str)}'
                f"</span>"
            )
        if not parts:
            return ""
        return '<div class="assumptions-line">' + " ".join(parts) + "</div>"

    def _render_power_badge(self, res: Dict[str, Any], is_ru: bool) -> str:
        if not isinstance(res, dict):
            return ""
        power = res.get("observed_power")
        if power is None:
            return ""
        try:
            pwr = float(power)
        except Exception:
            return ""
        if not np.isfinite(pwr):
            return ""
        color = "#16a34a" if pwr >= 0.8 else ("#ca8a04" if pwr >= 0.5 else "#dc2626")
        label = "Мощность" if is_ru else "Power"
        return (
            '<div class="assumptions-line">'
            f'<span style="background:{color}20;color:{color};padding:2px 8px;border-radius:4px;font-size:0.82em;">'
            f"⚡ {label}: {pwr:.0%}"
            "</span>"
            "</div>"
        )

    def _add_methods(self):
        is_ru = bool(getattr(self, "is_ru", False))
        summary = _extract_report_methods(self.data if isinstance(self.data, dict) else {}, is_ru=is_ru)
        rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
        missing = summary.get("missing_inferential_steps") if isinstance(summary.get("missing_inferential_steps"), list) else []

        if not rows and not missing:
            text = (
                "Методы не определены: в результатах нет исполнимых аналитических шагов."
                if is_ru
                else "Methods are unavailable: no analyzable steps were found in run results."
            )
            self.html_parts.append(
                f"""
                <div class="card" id="methods">
                    <h2>{'Методы' if is_ru else 'Methods'}</h2>
                    <p>{html.escape(text)}</p>
                </div>
                """
            )
            return

        body_rows = []
        for row in rows:
            method = str(row.get("method") or "-")
            count = int(row.get("count") or 0)
            steps = ", ".join([str(x) for x in (row.get("steps") or [])[:8]]) or "-"
            targets = ", ".join([str(x) for x in (row.get("targets") or [])[:10]]) or "-"
            body_rows.append(
                "<tr>"
                f"<td>{html.escape(method)}</td>"
                f"<td>{count}</td>"
                f"<td>{html.escape(steps)}</td>"
                f"<td>{html.escape(targets)}</td>"
                "</tr>"
            )

        warn_html = ""
        if missing:
            preview = ", ".join([str(x) for x in missing[:6]])
            if len(missing) > 6:
                preview += ", ..."
            warn_text = (
                f"Для некоторых инференциальных шагов отсутствует metadata метода: {preview}."
                if is_ru
                else f"Method metadata is missing for some inferential steps: {preview}."
            )
            warn_html = (
                f'<p style="color:#b91c1c;"><strong>{("Предупреждение" if is_ru else "Warning")}:</strong> '
                f"{html.escape(warn_text)}</p>"
            )

        self.html_parts.append(
            f"""
            <div class="card" id="methods">
                <h2>{'Методы' if is_ru else 'Methods'}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>{'Метод' if is_ru else 'Method'}</th>
                            <th>{'Шагов' if is_ru else 'Steps'}</th>
                            <th>{'ID шагов' if is_ru else 'Step IDs'}</th>
                            <th>{'Показатели' if is_ru else 'Targets'}</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(body_rows)}</tbody>
                </table>
                {warn_html}
            </div>
            """
        )

    def _add_hypothesis_discovery(self):
        is_ru = bool(getattr(self, "is_ru", False))
        ctx = _build_hypothesis_discovery_context(
            self.data if isinstance(self.data, dict) else {},
            is_ru=is_ru,
        )
        if not isinstance(ctx, dict) or not ctx.get("present"):
            return

        rows = ctx.get("rows") if isinstance(ctx.get("rows"), list) else []
        body = "".join(
            [
                "<tr>"
                + f"<td>{html.escape(str(row.get('id') or '-'))}</td>"
                + f"<td>{html.escape(str(row.get('title') or '-'))}</td>"
                + f"<td>{html.escape(str(row.get('h0') or '-'))}</td>"
                + f"<td>{html.escape(str(row.get('h1') or '-'))}</td>"
                + f"<td>{html.escape(str(row.get('suggested_method') or '-'))}</td>"
                + f"<td>{html.escape(', '.join([str(x) for x in (row.get('matched_steps') or [])]) or '-')}</td>"
                + f"<td>{html.escape(str(row.get('verdict_label') or '-'))}</td>"
                + f"<td>{html.escape(str(row.get('evidence') or '-'))}</td>"
                + "</tr>"
                for row in rows[:16]
                if isinstance(row, dict)
            ]
        )

        self.html_parts.append(
            f"""
            <div class="card" id="hypothesis-discovery">
                <h2>{'Гипотезы и их трассировка' if is_ru else 'Hypothesis discovery and traceability'}</h2>
                <table>
                    <tbody>
                        <tr><td><strong>{'Режим' if is_ru else 'Mode'}</strong></td><td>{html.escape(str(ctx.get('analysis_mode') or '-'))}</td></tr>
                        <tr><td><strong>{'Дизайн' if is_ru else 'Design'}</strong></td><td>{html.escape(str(ctx.get('design_type') or '-'))}</td></tr>
                        <tr><td><strong>{'Всего гипотез' if is_ru else 'Total hypotheses'}</strong></td><td>{html.escape(str(ctx.get('count') or len(rows)))}</td></tr>
                        <tr><td><strong>{'Покрыто шагами' if is_ru else 'Covered by executed steps'}</strong></td><td>{html.escape(str(ctx.get('covered') or 0))}</td></tr>
                        <tr><td><strong>{'Подтверждено' if is_ru else 'Supported'}</strong></td><td>{html.escape(str(ctx.get('supported') or 0))}</td></tr>
                        <tr><td><strong>{'Не подтверждено' if is_ru else 'Not supported'}</strong></td><td>{html.escape(str(ctx.get('not_supported') or 0))}</td></tr>
                        <tr><td><strong>{'Не оценено' if is_ru else 'Not evaluated'}</strong></td><td>{html.escape(str(ctx.get('not_evaluated') or 0))}</td></tr>
                    </tbody>
                </table>
                <h3>{'Список гипотез' if is_ru else 'Hypothesis list'}</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>{'Гипотеза' if is_ru else 'Hypothesis'}</th>
                            <th>H0</th>
                            <th>H1</th>
                            <th>{'Рекомендованный метод' if is_ru else 'Suggested method'}</th>
                            <th>{'Связанные шаги' if is_ru else 'Matched steps'}</th>
                            <th>{'Вердикт' if is_ru else 'Verdict'}</th>
                            <th>{'Доказательная сводка' if is_ru else 'Evidence summary'}</th>
                        </tr>
                    </thead>
                    <tbody>{body}</tbody>
                </table>
            </div>
            """
        )

    def _add_table1_multi(self, ordered_deduped: List[Dict[str, Any]], step_meta_map: Dict[str, Any]) -> bool:
        is_ru = bool(getattr(self, "is_ru", False))
        table_steps: List[Dict[str, Any]] = []
        group_col = None

        def _extract_target(res: Dict[str, Any], meta: Dict[str, Any]) -> Optional[str]:
            cfg = meta.get("config") if isinstance(meta, dict) else None
            if isinstance(cfg, dict):
                for k in ["target", "outcome", "endpoint", "y"]:
                    v = cfg.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            for k in ["target", "outcome", "endpoint", "y"]:
                v = meta.get(k) if isinstance(meta, dict) else None
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in ["target", "outcome", "endpoint", "y"]:
                v = res.get(k) if isinstance(res, dict) else None
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        for e in ordered_deduped:
            res = e.get("res") if isinstance(e, dict) else None
            step_id = e.get("step_id") if isinstance(e, dict) else None
            if not isinstance(res, dict) or not isinstance(step_id, str):
                continue
            if res.get("type") != "table_1":
                continue
            stats = res.get("data")
            if not isinstance(stats, dict) or not stats:
                continue
            meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
            meta = meta if isinstance(meta, dict) else {}
            target = _extract_target(res, meta) or step_id
            if not target:
                continue
            if group_col is None:
                cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
                group_col = cfg.get("group")
            table_steps.append({"target": target, "stats": stats})

        if len(table_steps) < 2:
            return False

        groups = [k for k in table_steps[0].get("stats", {}).keys() if k != "overall"]
        if not groups:
            return False

        dataset_id = self.data.get("dataset_id") if isinstance(self.data, dict) else None
        ds_dir = self._resolve_dataset_dir(str(dataset_id) if dataset_id else "")
        study_design = {}
        design = {}
        policy = {}
        if ds_dir:
            study_path = os.path.join(ds_dir, "processed", "study_design.json")
            if os.path.exists(study_path):
                study_design = self._load_json(study_path)
        if isinstance(study_design, dict):
            design = study_design.get("design") if isinstance(study_design.get("design"), dict) else {}
            policy = study_design.get("analysis_policy") if isinstance(study_design.get("analysis_policy"), dict) else {}
        cat_cols = design.get("categorical_outcomes") if isinstance(design.get("categorical_outcomes"), list) else []
        max_cat = int(policy.get("max_table1_categorical") or 40)
        max_cat = max(0, min(max_cat, 200))

        pval_map: Dict[str, Dict[str, Any]] = {}
        for e in ordered_deduped:
            res = e.get("res") if isinstance(e, dict) else None
            if not isinstance(res, dict):
                continue
            if res.get("type") != "batch_analysis":
                continue
            g = res.get("group") or res.get("group_column")
            if not g:
                continue
            items = res.get("items")
            if not isinstance(items, list):
                continue
            pval_map.setdefault(str(g), {})
            for it in items:
                if not isinstance(it, dict):
                    continue
                target = it.get("target") or it.get("outcome")
                if not target:
                    continue
                pval_map[str(g)][str(target)] = {
                    "p_raw": it.get("p_value"),
                    "p_adj": it.get("p_value_adj"),
                }

        def _fmt_p(value: Any) -> str:
            try:
                if value is None:
                    return "-"
                p = float(value)
                if not np.isfinite(p):
                    return "-"
                return "<0.001" if p < 0.001 else f"{p:.3f}"
            except Exception:
                return "-"

        def _summary(stats: Dict[str, Any], use_mean: bool) -> str:
            n = stats.get("count")
            n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
            if use_mean:
                return f"{_fmt_stat(stats.get('mean'))} ± {_fmt_stat(stats.get('std'))} {n_s}".strip()
            return f"{_fmt_stat(stats.get('median'))} [{_fmt_stat(stats.get('q1'))}; {_fmt_stat(stats.get('q3'))}] {n_s}".strip()

        any_adj = False
        for g in pval_map.values():
            for v in g.values():
                if isinstance(v, dict) and v.get("p_adj") is not None:
                    any_adj = True
                    break

        header_cells = ["Показатель" if is_ru else "Variable"]
        for g in groups:
            header_cells.append(str(g))
        header_cells.append("Итого" if is_ru else "Overall")
        header_cells.append("p(adj)" if any_adj else "p")

        rows_html = []
        for row in table_steps:
            stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
            # Decide mean vs median by Shapiro across groups
            all_normal = True
            for g in groups:
                sp = stats.get(g, {}).get("shapiro_p")
                if sp is None:
                    all_normal = False
                    break
                try:
                    if float(sp) < 0.05:
                        all_normal = False
                        break
                except Exception:
                    all_normal = False
                    break
            cells = [html.escape(str(row.get("target")))]
            for g in groups:
                cells.append(_summary(stats.get(g, {}), all_normal))
            cells.append(_summary(stats.get("overall", {}), all_normal))
            p_val = None
            if group_col and group_col in pval_map:
                p_info = pval_map.get(group_col, {}).get(str(row.get("target")))
                if isinstance(p_info, dict):
                    p_val = p_info.get("p_adj") if p_info.get("p_adj") is not None else p_info.get("p_raw")
            cells.append(_fmt_p(p_val))
            rows_html.append("<tr>" + "".join([f"<td>{c}</td>" for c in cells]) + "</tr>")

        # Add categorical rows (counts and %)
        if ds_dir and group_col and cat_cols:
            try:
                parquet_path = os.path.join(ds_dir, "processed", f"{dataset_id}.parquet")
                use_cols = [group_col] + [c for c in cat_cols if c != group_col]
                use_cols = list(dict.fromkeys([c for c in use_cols if c]))
                if os.path.exists(parquet_path) and use_cols:
                    df_cat = pd.read_parquet(parquet_path, columns=use_cols)
                    df_cat = df_cat[df_cat[group_col].notna()]
                    if not df_cat.empty:
                        group_series = df_cat[group_col].astype(str)
                        group_vals = [str(g) for g in groups]
                        group_totals = {str(g): int(df_cat[group_series == str(g)].shape[0]) for g in group_vals}
                        overall_total = int(df_cat.shape[0])

                        def _fmt_cnt_pct(count: int, total: int) -> str:
                            if total <= 0:
                                return "-"
                            pct = (float(count) / float(total)) * 100.0
                            return f"{int(count)} ({pct:.1f}%)"

                        cat_limit = min(len(cat_cols), max_cat)
                        for col in cat_cols[:cat_limit]:
                            if col not in df_cat.columns:
                                continue
                            series = df_cat[col].fillna("Missing").astype(str)
                            overall_counts = series.value_counts(dropna=False)
                            categories = [str(c) for c in overall_counts.index.tolist()]
                            if not categories:
                                continue

                            p_val = None
                            if group_col in pval_map:
                                p_info = pval_map.get(group_col, {}).get(str(col))
                                if isinstance(p_info, dict):
                                    p_val = p_info.get("p_adj") if p_info.get("p_adj") is not None else p_info.get("p_raw")

                            # Variable header row
                            header_cells = [f"<strong>{html.escape(str(col))}</strong>"]
                            header_cells += [""] * (len(groups) + 1)
                            header_cells.append(_fmt_p(p_val))
                            rows_html.append("<tr>" + "".join([f"<td>{c}</td>" for c in header_cells]) + "</tr>")

                            for cat in categories[:30]:
                                row_cells = [f"&nbsp;&nbsp;{html.escape(str(cat))}"]
                                for g in group_vals:
                                    cnt = int(df_cat[(group_series == str(g)) & (df_cat[col].fillna("Missing").astype(str) == cat)].shape[0])
                                    row_cells.append(_fmt_cnt_pct(cnt, group_totals.get(str(g), 0)))
                                cnt_overall = int(overall_counts.get(cat, 0))
                                row_cells.append(_fmt_cnt_pct(cnt_overall, overall_total))
                                row_cells.append("")
                                rows_html.append("<tr>" + "".join([f"<td>{c}</td>" for c in row_cells]) + "</tr>")
            except Exception:
                pass

        footnote = (
            "Примечание: если нормальность нарушена, используется медиана [Q1; Q3], иначе среднее ± SD."
            if is_ru
            else "Note: non-normal variables use median [Q1; Q3], otherwise mean ± SD."
        )

        html_block = f"""
        <div class="card" id="table1">
            <h2>{'Таблица 1. Описательная статистика (сводная)' if is_ru else 'Table 1. Descriptive statistics (summary)'}</h2>
            <table>
                <thead><tr>{''.join([f'<th>{html.escape(c)}</th>' for c in header_cells])}</tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
            <div style="margin-top:8px; color:#64748b; font-size:12px;">{footnote}</div>
        </div>
        """
        self.html_parts.append(html_block)
        return True

    def _add_batch_descriptive_bridge(self, ordered_deduped: List[Dict[str, Any]], step_meta_map: Dict[str, Any]) -> bool:
        is_ru = bool(getattr(self, "is_ru", False))
        rows: List[Dict[str, Any]] = []
        has_slice = False

        def _fmt_p(value: Any) -> str:
            try:
                if value is None:
                    return "-"
                p = float(value)
                if not np.isfinite(p):
                    return "-"
                return "<0.001" if p < 0.001 else f"{p:.4f}"
            except Exception:
                return "-"

        def _stats_text(stats: Dict[str, Any]) -> str:
            if not isinstance(stats, dict):
                return "-"
            mean = _fmt_stat(stats.get("mean"))
            sd = _fmt_stat(stats.get("sd"))
            med = _fmt_stat(stats.get("median"))
            q1 = _fmt_stat(stats.get("q1"))
            q3 = _fmt_stat(stats.get("q3"))
            n = stats.get("count")
            n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
            return f"{mean} ± {sd}; {med} [{q1}; {q3}] {n_s}".strip()

        def _append_rows(items: Any, step_id: str, slice_label: Optional[str], correction: Any, alpha: float) -> None:
            nonlocal has_slice
            rows_payload = _collect_batch_inferential_rows(items, alpha)
            payload_rows = rows_payload.get("rows") if isinstance(rows_payload, dict) else []
            payload_rows = payload_rows if isinstance(payload_rows, list) else []
            if slice_label:
                has_slice = True
            for row in payload_rows:
                if not isinstance(row, dict):
                    continue
                group_stats = row.get("group_stats")
                if not isinstance(group_stats, dict) or len(group_stats) < 2:
                    continue
                labels = list(group_stats.keys())[:2]
                rows.append(
                    {
                        "step_id": step_id,
                        "slice": slice_label,
                        "target": str(row.get("target") or "-"),
                        "g1": str(labels[0]),
                        "g2": str(labels[1]),
                        "g1_stats": _stats_text(group_stats.get(labels[0]) if isinstance(group_stats.get(labels[0]), dict) else {}),
                        "g2_stats": _stats_text(group_stats.get(labels[1]) if isinstance(group_stats.get(labels[1]), dict) else {}),
                        "p_raw": row.get("p_raw"),
                        "p_adj": row.get("p_adj"),
                        "method": _method_label_from_id(row.get("method"), is_ru) or str(row.get("method") or "-"),
                        "correction": _format_correction_label(correction, is_ru) if correction else "",
                    }
                )

        for e in ordered_deduped:
            step_id = e.get("step_id") if isinstance(e, dict) else None
            res = e.get("res") if isinstance(e, dict) else None
            if not isinstance(step_id, str) or not isinstance(res, dict):
                continue
            rtype = str(res.get("type") or "")
            if rtype not in {"batch_analysis", "timepoint_batch_analysis"}:
                continue
            alpha = _coerce_alpha(res.get("alpha"), (self.data or {}).get("alpha") if isinstance(self.data, dict) else None)
            if rtype == "batch_analysis":
                _append_rows(res.get("items"), step_id, None, res.get("multiplicity_correction"), alpha)
                continue
            slices = res.get("slices")
            slices = slices if isinstance(slices, dict) else {}
            for slice_key in sorted(slices.keys(), key=lambda x: str(x)):
                sr = slices.get(slice_key)
                if not isinstance(sr, dict):
                    continue
                _append_rows(
                    sr.get("items"),
                    step_id,
                    str(slice_key),
                    sr.get("multiplicity_correction") or res.get("multiplicity_correction"),
                    alpha,
                )

        if len(rows) < 2:
            return False

        head_cols = [
            ("Срез" if is_ru else "Slice") if has_slice else None,
            "Показатель" if is_ru else "Target",
            "Группа A" if is_ru else "Group A",
            "Группа B" if is_ru else "Group B",
            "p",
            "p(adj)",
            "Тест" if is_ru else "Test",
            "Поправка" if is_ru else "Correction",
            "ID шага" if is_ru else "Step ID",
        ]
        head_cols = [c for c in head_cols if c is not None]

        body = []
        for row in rows[:600]:
            cells = []
            if has_slice:
                cells.append(html.escape(str(row.get("slice") or "—")))
            cells.append(html.escape(str(row.get("target") or "-")))
            cells.append(
                html.escape(str(row.get("g1") or "-"))
                + ": "
                + html.escape(str(row.get("g1_stats") or "-"))
            )
            cells.append(
                html.escape(str(row.get("g2") or "-"))
                + ": "
                + html.escape(str(row.get("g2_stats") or "-"))
            )
            cells.append(f"<span class='stat-val'>{_fmt_p(row.get('p_raw'))}</span>")
            cells.append(f"<span class='stat-val'>{_fmt_p(row.get('p_adj'))}</span>")
            cells.append(html.escape(str(row.get("method") or "-")))
            cells.append(html.escape(str(row.get("correction") or "-")))
            cells.append(html.escape(str(row.get("step_id") or "-")))
            body.append("<tr>" + "".join([f"<td>{c}</td>" for c in cells]) + "</tr>")

        note = (
            "Таблица сформирована автоматически из batch/timepoint результатов, поскольку отдельный шаг table_1 отсутствует."
            if is_ru
            else "This table was generated from batch/timepoint outputs because a dedicated table_1 step is missing."
        )

        self.html_parts.append(
            f"""
            <div class="card" id="table1-batch-bridge">
                <h2>{'Таблица 1*. Описательная статистика для инференциальных тестов' if is_ru else 'Table 1*. Descriptives linked to inferential tests'}</h2>
                <table>
                    <thead><tr>{''.join([f"<th>{html.escape(str(c))}</th>" for c in head_cols])}</tr></thead>
                    <tbody>{''.join(body)}</tbody>
                </table>
                <div style="margin-top:8px;color:#64748b;font-size:12px;">{html.escape(note)}</div>
            </div>
            """
        )
        return True

    def _add_toc(self, results: Dict[str, Any], step_meta_map: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        if not results:
            return
        step_meta_map = step_meta_map if isinstance(step_meta_map, dict) else {}
        items = []
        if isinstance(results, list):
            for block in results:
                if not isinstance(block, dict):
                    continue
                step_id = block.get("id")
                rtype = block.get("kind")
                if not isinstance(step_id, str) or not step_id:
                    continue
                if not isinstance(rtype, str) or not rtype:
                    rtype = (block.get("payload") or {}).get("type") if isinstance(block.get("payload"), dict) else None
                rtype = rtype if isinstance(rtype, str) and rtype else "result"
                payload = block.get("payload") if isinstance(block.get("payload"), dict) else {}
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map.get(step_id), dict) else {}
                display = _build_step_display(step_id, payload if isinstance(payload, dict) else {}, step_meta, is_ru)
                items.append(
                    f'<li><a href="#step-{step_id}">{html.escape(display)}</a> '
                    f'<span style="color:#64748b;">(ID: {html.escape(step_id)}; {html.escape(str(rtype))})</span></li>'
                )
        elif isinstance(results, dict):
            for step_id, res in results.items():
                if not isinstance(step_id, str):
                    continue
                rtype = (res.get("type") if isinstance(res, dict) else None) or "result"
                step_meta = step_meta_map.get(step_id) if isinstance(step_meta_map.get(step_id), dict) else {}
                display = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
                items.append(
                    f'<li><a href="#step-{step_id}">{html.escape(display)}</a> '
                    f'<span style="color:#64748b;">(ID: {html.escape(step_id)}; {html.escape(str(rtype))})</span></li>'
                )
        toc_html = f"""
        <div class="card" id="toc">
            <h2>{'Содержание' if is_ru else 'Contents'}</h2>
            <ol style="margin: 0; padding-left: 18px;">
                {''.join(items)}
            </ol>
        </div>
        """
        self.html_parts.append(toc_html)

    def _add_editorial_index(
        self,
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]],
        ordered_targets: List[str],
        step_meta_map: Optional[Dict[str, Any]] = None,
    ):
        is_ru = bool(getattr(self, "is_ru", False))
        if not isinstance(grouped, dict) or not grouped:
            return
        step_meta_map = step_meta_map if isinstance(step_meta_map, dict) else {}

        import re

        def _visit_sort_key(v: str) -> tuple:
            if v in {"Все визиты", "All visits"}:
                return (1, 1_000_000, "")
            s = str(v).strip()
            m = re.search(r"\bV\s*(\d+)\b", s, flags=re.IGNORECASE)
            if m:
                try:
                    return (0, int(m.group(1)), "")
                except Exception:
                    return (0, 1_000_000, s)
            try:
                return (0, int(float(s)), "")
            except Exception:
                return (0, 1_000_000, s)

        parts = [
            f"""
            <div class=\"card\" id=\"editorial\">
                <h2>{'Навигация по показателям' if is_ru else 'Editorial Index'}</h2>
            """
        ]

        targets = ordered_targets if isinstance(ordered_targets, list) and ordered_targets else list(grouped.keys())
        for t_label in targets:
            visits_map = grouped.get(t_label)
            if not isinstance(visits_map, dict) or not visits_map:
                continue
            parts.append(f"<h3 style=\"margin-top: 18px;\">{html.escape(str(t_label))}</h3>")
            visits = sorted(visits_map.keys(), key=_visit_sort_key)
            for v_label in visits:
                items = visits_map.get(v_label)
                if not isinstance(items, list) or not items:
                    continue
                links = []
                for it in items:
                    sid = it.get("step_id") if isinstance(it, dict) else None
                    rtype = it.get("rtype") if isinstance(it, dict) else None
                    payload = it.get("res") if isinstance(it.get("res"), dict) else {}
                    if not isinstance(sid, str) or not sid:
                        continue
                    step_meta = step_meta_map.get(sid) if isinstance(step_meta_map.get(sid), dict) else {}
                    display = _build_step_display(sid, payload if isinstance(payload, dict) else {}, step_meta, is_ru)
                    t = f"{html.escape(display)}"
                    if isinstance(rtype, str) and rtype:
                        t += f" <span style=\"color:#64748b;\">(ID: {html.escape(sid)}; {html.escape(rtype)})</span>"
                    links.append(f"<li><a href=\"#step-{html.escape(sid)}\">{t}</a></li>")
                if not links:
                    continue
                parts.append(
                    f"""
                    <div style=\"margin-top: 10px;\">
                        <div style=\"color:#111; font-size: 12px; font-weight: 600;\">{html.escape(str(v_label))}</div>
                        <ul style=\"margin: 6px 0 0; padding-left: 18px;\">{''.join(links)}</ul>
                    </div>
                    """
                )

        parts.append("</div>")
        self.html_parts.append("\n".join(parts))

    def _add_unknown_section(self, res: Dict[str, Any], step_id: str, step_meta: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        rtype = (res.get("type") if isinstance(res, dict) else None) or "result"
        error = res.get("error") if isinstance(res, dict) else None
        display = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        title = f"{display} (ID: {step_id}; {rtype})"
        body = ""
        if isinstance(error, str) and error.strip():
            body += f"<div class=\"ai-box\"><strong>{'Ошибка' if is_ru else 'Error'}:</strong> {html.escape(error)}</div>"
        try:
            raw = json.dumps(res, ensure_ascii=False, indent=2, default=str)
        except Exception:
            raw = str(res)
        raw = raw[:12000]
        body += f"<pre style=\"white-space:pre-wrap; word-break:break-word; background:#f8fafc; border:1px solid #e2e8f0; padding:12px 14px;\">{html.escape(raw)}</pre>"
        self.html_parts.append(
            f"""
            <div class="card" id="step-{html.escape(step_id)}">
                <h2>{html.escape(title)}</h2>
                {body}
            </div>
            """
        )

    def _add_discussion_conclusion(self):
        is_ru = bool(getattr(self, "is_ru", False))
        summary = _extract_protocol_findings(self.data if isinstance(self.data, dict) else {})
        text = _build_discussion_conclusion(summary, is_ru=is_ru)
        discussion = text.get("discussion") if isinstance(text.get("discussion"), list) else []
        conclusion = text.get("conclusion") if isinstance(text.get("conclusion"), list) else []

        if discussion:
            body = "".join([f"<p>{html.escape(str(line))}</p>" for line in discussion])
            self.html_parts.append(
                f"""
                <div class="card" id="discussion">
                    <h2>{'Обсуждение' if is_ru else 'Discussion'}</h2>
                    {body}
                </div>
                """
            )

        if conclusion:
            items = "".join([f"<li>{html.escape(str(line))}</li>" for line in conclusion])
            self.html_parts.append(
                f"""
                <div class="card" id="conclusion">
                    <h2>{'Выводы' if is_ru else 'Conclusions'}</h2>
                    <ul>{items}</ul>
                </div>
                """
            )

    def _add_limitations(self):
        is_ru = bool(getattr(self, "is_ru", False))
        findings = _extract_protocol_findings(self.data if isinstance(self.data, dict) else {})
        methods_summary = _extract_report_methods(self.data if isinstance(self.data, dict) else {}, is_ru=is_ru)
        lines = _build_report_limitations(findings, methods_summary, is_ru=is_ru)
        if not lines:
            return
        items = "".join([f"<li>{html.escape(str(line))}</li>" for line in lines])
        self.html_parts.append(
            f"""
            <div class="card" id="limitations">
                <h2>{'Ограничения' if is_ru else 'Limitations'}</h2>
                <ul>{items}</ul>
            </div>
            """
        )

    def _add_run_log(self):
        log = self.data.get("log") if isinstance(self.data, dict) else None
        if not isinstance(log, list) or not log:
            return
        rows = "".join([f"<tr><td>{str(line)}</td></tr>" for line in log[-200:]])
        html = f"""
        <div class="card" id="run-log">
            <h2>Журнал выполнения</h2>
            <table>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
        self.html_parts.append(html)

    def _add_header(self):
        style_key = str(self.style or "apa7").strip().lower()
        is_ru = style_key in {"gost"}
        self.is_ru = is_ru
        density = _normalize_report_density(self.options.get("density"))
        accent = _parse_accent_css(self.options.get("accent"))
        if not accent:
            accent = "#111111" if style_key in {"gost", "simple", "editorial", "brutal"} else "#3498db"

        pad = "34px"
        body_font = "14px"
        if density == "compact":
            pad = "26px"
            body_font = "13px"
        elif density == "spacious":
            pad = "46px"
            body_font = "15px"

        if style_key == "gost":
            css = """
            <style>
                body { font-family: 'Times New Roman', 'Times', serif; line-height: 1.5; color: #111; max-width: 820px; margin: 0 auto; padding: __PAD__; font-size: __FONT__; }
                h1 { font-size: 22px; font-weight: 700; margin: 0 0 18px; padding-bottom: 10px; border-bottom: 1px solid #111; }
                h2 { font-size: 18px; font-weight: 700; margin-top: 28px; padding-bottom: 6px; border-bottom: 1px solid #ddd; }
                h3 { font-size: 15px; font-weight: 700; margin-top: 16px; }
                .card { background: #fff; border: 1px solid #ddd; padding: 18px 20px; margin-bottom: 18px; }
                table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
                th, td { padding: 10px 12px; border-bottom: 1px solid #e6e6e6; text-align: left; vertical-align: top; }
                th { background-color: #f7f7f7; font-weight: 700; color: #111; }
                .stat-val { font-family: 'Courier New', monospace; font-weight: 700; }
                .sig-yes { color: #0f5132; font-weight: 700; }
                .sig-no { color: #495057; }
                .plot-container { text-align: center; margin-top: 14px; }
                img { max-width: 100%; height: auto; border: 1px solid #e6e6e6; }
                .ai-box { background: #fafafa; border-left: 3px solid #111; padding: 12px 14px; margin-top: 14px; }
                .meta-info { color: #333; font-size: 13px; margin-bottom: 22px; }
                @media print { body { padding: 0; max-width: 100%; } .card { break-inside: avoid; border: none; padding: 0; margin-bottom: 26px; } }
            </style>
            """
        elif style_key == "simple":
            css = """
            <style>
                body { font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; line-height: 1.55; color: #111; max-width: 920px; margin: 0 auto; padding: __PAD__; font-size: __FONT__; }
                h1 { font-size: 20px; margin: 0 0 16px; padding-bottom: 10px; border-bottom: 1px solid #e5e7eb; }
                h2 { font-size: 16px; margin-top: 26px; padding-bottom: 6px; border-bottom: 1px solid #eef2f7; }
                h3 { font-size: 13px; margin-top: 14px; }
                .card { border: 1px solid #e5e7eb; padding: 16px 16px; margin-bottom: 14px; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
                th, td { padding: 9px 10px; border-bottom: 1px solid #f1f5f9; text-align: left; }
                th { font-weight: 700; color: #111; background: #fafafa; }
                .stat-val { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-weight: 600; }
                .sig-yes { color: #111; font-weight: 700; }
                .sig-no { color: #64748b; }
                .plot-container { text-align: center; margin-top: 12px; }
                img { max-width: 100%; height: auto; border: 1px solid #f1f5f9; }
                .ai-box { background: #fafafa; border-left: 2px solid #111; padding: 10px 12px; margin-top: 12px; }
                .meta-info { color: #475569; font-size: 12px; margin-bottom: 18px; }
                @media print { body { padding: 0; max-width: 100%; } .card { break-inside: avoid; border: none; padding: 0; margin-bottom: 22px; } }
            </style>
            """
        elif style_key == "editorial":
            css = """
            <style>
                :root { --accent: __ACCENT__; }
                body { font-family: 'Georgia', 'Times New Roman', serif; line-height: 1.62; color: #111; max-width: 940px; margin: 0 auto; padding: __PAD__; font-size: __FONT__; }
                h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 10px; }
                .meta-info { display: grid; grid-template-columns: 1fr auto; gap: 10px 18px; margin-bottom: 26px; padding-top: 14px; border-top: 2px solid #111; }
                .meta-info p { margin: 0; color: #111; font-size: 12px; }
                h2 { font-size: 18px; font-weight: 700; margin-top: 34px; padding-bottom: 8px; border-bottom: 1px solid #111; }
                h3 { font-size: 13px; font-weight: 700; margin-top: 14px; }
                .card { background: transparent; border: none; padding: 0; margin-bottom: 22px; }
                table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
                th, td { padding: 10px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
                th { font-weight: 700; color: #111; }
                .stat-val { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-weight: 650; }
                .sig-yes { color: #111; font-weight: 800; background: #fff7ed; border: 1px solid #111; padding: 2px 6px; }
                .sig-no { color: #475569; }
                .plot-container { text-align: center; margin-top: 14px; }
                img { max-width: 100%; height: auto; border: 1px solid #e5e7eb; }
                .ai-box { background: #fff; border: 1px solid #111; padding: 12px 14px; margin-top: 14px; }
                @media print { body { padding: 0; max-width: 100%; } .card { break-inside: avoid; } }
            </style>
            """
        elif style_key == "brutal":
            css = """
            <style>
                :root { --accent: __ACCENT__; }
                body { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace; line-height: 1.55; color: #111; max-width: 980px; margin: 0 auto; padding: __PAD__; font-size: __FONT__; }
                h1 { font-size: 22px; margin: 0 0 14px; padding-bottom: 10px; border-bottom: 3px solid #111; }
                h2 { font-size: 15px; margin-top: 26px; padding-bottom: 8px; border-bottom: 2px dashed #111; }
                h3 { font-size: 13px; margin-top: 14px; }
                .card { border: 2px solid #111; padding: 14px 14px; margin-bottom: 14px; background: #fff; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
                th, td { padding: 8px 8px; border: 1px solid #111; text-align: left; vertical-align: top; }
                th { font-weight: 800; }
                .stat-val { font-weight: 800; }
                .sig-yes { color: #111; font-weight: 800; }
                .sig-no { color: #111; }
                .ai-box { border: 2px solid #111; padding: 10px 12px; margin-top: 10px; }
                img { max-width: 100%; height: auto; border: 2px solid #111; }
                @media print { body { padding: 0; max-width: 100%; } .card { break-inside: avoid; } }
            </style>
            """
        else:
            css = """
            <style>
                :root { --accent: __ACCENT__; }
                body { font-family: 'Helvetica Neue', 'Helvetica', 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: __PAD__; font-size: __FONT__; }
                h1 { color: #2c3e50; border-bottom: 2px solid var(--accent); padding-bottom: 10px; margin-bottom: 20px; }
                h2 { color: #2980b9; margin-top: 40px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
                h3 { color: #16a085; font-size: 1.1em; margin-top: 20px; }
                .card { background: #fff; border: 1px solid #e1e4e8; padding: 25px; border-radius: 8px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
                table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.95em; }
                th, td { padding: 12px 15px; border-bottom: 1px solid #e1e4e8; text-align: left; }
                th { background-color: #f8f9fa; font-weight: 600; color: #444; }
                tr:last-child td { border-bottom: none; }
                .stat-val { font-family: 'SF Mono', 'Monaco', monospace; font-weight: 600; }
                .sig-yes { color: #27ae60; font-weight: bold; background: #eafaf1; padding: 2px 6px; border-radius: 4px; }
                .sig-no { color: #7f8c8d; }
                .plot-container { text-align: center; margin-top: 20px; background: #fff; padding: 10px; }
                img { max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #eee; }
                .ai-box { background: #f0f7fb; border-left: 4px solid var(--accent); padding: 15px; margin-top: 20px; border-radius: 0 4px 4px 0; }
                .meta-info { color: #666; font-size: 0.9em; margin-bottom: 30px; }
                @media print { body { padding: 0; max-width: 100%; } .card { break-inside: avoid; border: none; box-shadow: none; padding: 0; margin-bottom: 40px; } h1 { margin-top: 0; } }
            </style>
            """

        css = css.replace("__PAD__", pad).replace("__FONT__", body_font).replace("__ACCENT__", accent)
        assumption_css = """
                .assumptions-line { margin: 6px 0; display: flex; gap: 10px; flex-wrap: wrap; }
                .assumption-pass { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 0.82em; }
                .assumption-fail { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 0.82em; }
                .assumption-unknown { background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 0.82em; }
        """
        css = css.replace("</style>", f"{assumption_css}\n            </style>")
        self.html_parts.append(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{'Отчёт по анализу' if is_ru else 'Analysis Report'} - {self.dataset_name}</title>
            {css}
        </head>
        <body>
            <h1>{'Отчёт по статистическому анализу' if is_ru else 'Statistical Analysis Report'}</h1>
            <div class="meta-info">
                <p><strong>{'Протокол' if is_ru else 'Protocol'}:</strong> {self.data.get('protocol_name', 'Пользовательский анализ' if is_ru else 'Custom Analysis')}</p>
                <p><strong>{'Набор данных' if is_ru else 'Dataset'}:</strong> {self.dataset_name}</p>
                <p><strong>{'Дата формирования' if is_ru else 'Date Generated'}:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        """)

    def _add_table_one(self, res: Dict, step_id: str, dup_count: int = 1):
        is_ru = bool(getattr(self, "is_ru", False))
        stats = res.get("data", {})
        if not stats: return

        def _fmt_p(value: Any) -> str:
            try:
                if value is None:
                    return "-"
                p = float(value)
                if not np.isfinite(p):
                    return "-"
                return "< 0.001" if p < 0.001 else f"{p:.3f}"
            except Exception:
                return "-"
        
        groups = [k for k in stats.keys() if k != 'overall']

        dup_line = ""
        if isinstance(dup_count, int) and dup_count > 1:
            dup_line = f"<div style=\"margin-top:-8px;color:#64748b;font-size:12px;\">{('Повтор шага свернут: ×' if is_ru else 'Duplicate collapsed: ×')}{dup_count}</div>"
        
        html = f"""
        <div class="card" id="step-{step_id}">
            <h2>{'Таблица 1. Описательная статистика' if is_ru else 'Table 1: Descriptive Statistics'}</h2>
            {dup_line}
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%">{'Показатель' if is_ru else 'Characteristic'}</th>
                        {''.join([f'<th>{g} (n={stats[g]["count"]})</th>' for g in groups])}
                        <th>{'Итого' if is_ru else 'Overall'} (n={stats['overall']['count']})</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        metrics = [
            (("Среднее (SD)" if is_ru else "Mean (SD)"), lambda s: f"{_fmt_stat((s or {}).get('mean'), 2)} ({_fmt_stat((s or {}).get('std'), 2)})"),
            (
                ("95% ДИ (среднего)" if is_ru else "95% CI (Mean)"),
                lambda s: (
                    f"[{_fmt_stat((s or {}).get('ci_95_low'), 2)}, {_fmt_stat((s or {}).get('ci_95_high'), 2)}]"
                    if ((s or {}).get("ci_95_low") is not None and (s or {}).get("ci_95_high") is not None)
                    else "-"
                ),
            ),
            (
                ("Медиана [Q1, Q3]" if is_ru else "Median [Q1, Q3]"),
                lambda s: (
                    f"{_fmt_stat((s or {}).get('median'), 2)} [{_fmt_stat((s or {}).get('q1'), 2)}, {_fmt_stat((s or {}).get('q3'), 2)}]"
                    if ((s or {}).get("median") is not None and (s or {}).get("q1") is not None and (s or {}).get("q3") is not None)
                    else "-"
                ),
            ),
            ("IQR", lambda s: _fmt_stat((s or {}).get("iqr"), 2) if (s or {}).get("iqr") is not None else "-"),
            (
                ("Диапазон (min–max)" if is_ru else "Range (Min-Max)"),
                lambda s: (
                    f"{_fmt_stat((s or {}).get('min'), 2)} - {_fmt_stat((s or {}).get('max'), 2)}"
                    if ((s or {}).get("min") is not None and (s or {}).get("max") is not None)
                    else "-"
                ),
            ),
            (
                ("Нормальность (Шапиро p)" if is_ru else "Normality (Shapiro p)"),
                lambda s: (
                    (_fmt_p((s or {}).get("shapiro_p")) + (" (!)" if (isinstance((s or {}).get("shapiro_p"), (int, float)) and float((s or {}).get("shapiro_p")) < 0.05) else ""))
                    if (s or {}).get("shapiro_p") is not None
                    else "-"
                ),
            ),
        ]
        
        for name, formatter in metrics:
            row = f"<tr><td>{name}</td>"
            for g in groups:
                 row += f"<td>{formatter(stats[g])}</td>"
            row += f"<td>{formatter(stats['overall'])}</td></tr>"
            html += row
            
        html += """
                </tbody>
            </table>
        """

        img_b64 = self._generate_plot_image(res)
        if img_b64:
            html += f'<div class="plot-container"><img src="data:image/png;base64,{img_b64}" alt="Table 1 Plot" /></div>'

        html += """
        </div>
        """
        self.html_parts.append(html)

    def _add_analysis_section(self, res: Dict, step_id: str, dup_count: int = 1, step_meta: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        sig_val = res.get("significant")
        sig_class = "sig-yes" if sig_val is True else "sig-no"
        sig_text = (
            ("Статистически значимо" if is_ru else "SIGNIFICANT")
            if sig_val is True
            else (("Статистически незначимо" if is_ru else "Not Significant") if sig_val is False else "—")
        )

        dup_html = ""
        if isinstance(dup_count, int) and dup_count > 1:
            dup_html = f"<div style=\"margin-top: 8px; color: #64748b; font-size: 12px;\">{('Повтор шага свернут: ×' if is_ru else 'Duplicate collapsed: ×')}{dup_count}</div>"
        
        method_obj = res.get("method") if isinstance(res, dict) else None
        method_default = "Статистический тест" if is_ru else "Statistical Test"
        method_id = ""
        if hasattr(method_obj, "name"):
            method_name = str(getattr(method_obj, "name") or "") or method_default
            try:
                method_id = str(getattr(method_obj, "id") or "").strip().lower()
            except Exception:
                method_id = ""
        elif isinstance(method_obj, dict):
            method_name = str(method_obj.get("name") or method_obj.get("id") or "") or method_default
            method_id = str(method_obj.get("id") or method_obj.get("name") or "").strip().lower()
        elif method_obj is None:
            method_name = method_default
        else:
            method_name = str(method_obj) or method_default
            method_id = str(method_obj or "").strip().lower()
        if not method_id:
            method_id = str(res.get("method_id") or "").strip().lower()
        method_label = _method_label_from_id(method_id, is_ru) if method_id else ""
        if method_label:
            method_name = method_label
        display_title = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        p_raw = res.get('p_value')
        p_val = float(p_raw) if isinstance(p_raw, (int, float)) and np.isfinite(float(p_raw)) else None
        p_display = "< 0.001" if (p_val is not None and p_val < 0.001) else (f"{p_val:.4f}" if p_val is not None else "-")

        stat_raw = res.get('stat_value', res.get('stats'))
        stat_val = float(stat_raw) if isinstance(stat_raw, (int, float)) and np.isfinite(float(stat_raw)) else None
        
        error_text = res.get("error") if isinstance(res, dict) else None
        suggestion_text = res.get("suggestion") if isinstance(res, dict) else None
        message_text = res.get("message") if isinstance(res, dict) else None

        alpha_raw = res.get("alpha")
        if alpha_raw is None and isinstance(self.data, dict):
            alpha_raw = self.data.get("alpha")
        try:
            alpha_val = float(alpha_raw) if alpha_raw is not None else None
            if alpha_val is not None and not np.isfinite(alpha_val):
                alpha_val = None
        except Exception:
            alpha_val = None

        target = (
            res.get("target")
            or res.get("outcome")
            or _extract_step_context_value(step_meta, res if isinstance(res, dict) else {}, ["target", "outcome", "endpoint", "y"])
        )
        group_col = (
            res.get("group_label")
            or res.get("group")
            or res.get("group_column")
            or _extract_step_context_value(step_meta, res if isinstance(res, dict) else {}, ["group", "group_col", "predictor", "x"])
        )
        groups = None
        plot_stats = res.get("plot_stats")
        if isinstance(plot_stats, dict) and plot_stats:
            groups = [str(k) for k in plot_stats.keys()]
        elif isinstance(res.get("groups"), list):
            groups = [str(g) for g in (res.get("groups") or [])]
        groups_s = ", ".join(groups) if groups else None

        rationale_ru = _method_selection_rationale_ru(res) if is_ru else None

        bf10_text = _interpret_bf10_ru(res.get("bf10")) if is_ru else None

        decision = None
        if p_val is not None and alpha_val is not None:
            if p_val < alpha_val:
                decision = "p-value < α → отклоняем H0; данные поддерживают H1 (различия есть)." if is_ru else "p-value < α → reject H0; evidence for H1 (difference)."
            else:
                decision = "p-value ≥ α → нет оснований отклонять H0; данные не подтверждают различия." if is_ru else "p-value ≥ α → fail to reject H0; no evidence of difference."

        hypothesis_h0 = ""
        hypothesis_h1 = ""
        if method_id in {"pearson", "spearman", "kendall", "partial_correlation"}:
            hypothesis_h0 = "H0: ρ = 0 (связи нет)." if is_ru else "H0: ρ = 0 (no association)."
            hypothesis_h1 = "H1: ρ ≠ 0 (связь есть)." if is_ru else "H1: ρ ≠ 0 (association exists)."
        elif method_id in {"shapiro_wilk", "dagostino_pearson", "anderson_darling", "kolmogorov_smirnov"}:
            hypothesis_h0 = "H0: распределение нормальное." if is_ru else "H0: distribution is normal."
            hypothesis_h1 = "H1: распределение не нормальное." if is_ru else "H1: distribution is not normal."
        elif method_id in {"levene", "bartlett", "fligner"}:
            hypothesis_h0 = "H0: дисперсии однородны." if is_ru else "H0: variances are equal."
            hypothesis_h1 = "H1: дисперсии различаются." if is_ru else "H1: variances differ."
        elif method_id in {"roc_analysis", "pca", "efa", "kmeans", "hierarchical_clustering"}:
            hypothesis_h0 = "Эксплораторный анализ: явная H0 не задается." if is_ru else "Exploratory analysis: no explicit null hypothesis."
            hypothesis_h1 = "Цель: выявить структуру/дискриминацию в данных." if is_ru else "Goal: identify latent structure/discrimination."
        else:
            hypothesis_h0 = "H0: эффекта/различий нет." if is_ru else "H0: no effect/difference."
            hypothesis_h1 = "H1: эффект/различия есть." if is_ru else "H1: effect/difference exists."

        section_html = f"""
        <div class="card" id="step-{step_id}">
            <h2>{'Шаг анализа' if is_ru else 'Analysis Step'}: {html.escape(display_title)}</h2>
            <div style="margin-top:-8px;color:#64748b;font-size:12px;">ID: {html.escape(step_id)}</div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h3>{method_name}</h3>
                    {dup_html}
                    {(
                        f'<div style="margin-top: 6px; color: #111; font-size: 12px;">'
                        + (f"<strong>{'Сравнение' if is_ru else 'Comparison'}:</strong> {html.escape(str(target))} " if target else "")
                        + (f"<strong>{'по' if is_ru else 'by'}:</strong> {html.escape(str(group_col))} " if group_col else "")
                        + (f"<strong>{'Группы' if is_ru else 'Groups'}:</strong> {html.escape(groups_s)}" if groups_s else "")
                        + "</div>"
                        if (target or group_col or groups_s)
                        else ""
                    )}
                    {(
                        f'<div class="ai-box" style="margin-top: 10px;"><strong>Ошибка:</strong> {error_text}'
                        + (f'<br><strong>Детали:</strong> {message_text}' if message_text else '')
                        + (f'<br><strong>Подсказка:</strong> {suggestion_text}' if suggestion_text else '')
                        + '</div>'
                        if error_text
                        else ''
                    )}
                    <table style="width: auto; margin-top: 10px;">
                        <tr>
                            <td><strong>p-value:</strong></td>
                            <td><span class="stat-val {sig_class}">{p_display}</span></td>
                        </tr>
                        <tr>
                            <td><strong>{'Статистика' if is_ru else 'Statistic'}:</strong></td>
                            <td>{(f"{stat_val:.3f}" if stat_val is not None else "-")}</td>
                        </tr>
                        <tr>
                            <td><strong>{'Размер эффекта' if is_ru else 'Effect size'}:</strong></td>
                            <td>
                                {(
                                    f"{res.get('effect_size_name') or 'effect'} = {float(res.get('effect_size')):.2f}"
                                    if res.get('effect_size') is not None
                                    else "-"
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td><strong>{'95% ДИ (эффект)' if is_ru else 'CI (effect)'}:</strong></td>
                            <td>
                                {(
                                    f"[{float(res.get('effect_size_ci_lower')):.2f}, {float(res.get('effect_size_ci_upper')):.2f}]"
                                    if (res.get('effect_size_ci_lower') is not None and res.get('effect_size_ci_upper') is not None)
                                    else "-"
                                )}
                            </td>
                        </tr>
                        <tr>
                            <td><strong>{'Мощность' if is_ru else 'Power'}:</strong></td>
                            <td>{(f"{float(res.get('power')):.2f}" if res.get('power') is not None else "-")}</td>
                        </tr>
                        <tr>
                            <td><strong>BF10:</strong></td>
                            <td>{(str(res.get('bf10')) if res.get('bf10') is not None else "-")}</td>
                        </tr>
                        {(
                            f"<tr><td><strong>{'Интерпретация BF10' if is_ru else 'BF10 interpretation'}:</strong></td><td>{html.escape(str(bf10_text))}</td></tr>"
                            if bf10_text
                            else ""
                        )}
                        <tr>
                            <td><strong>α:</strong></td>
                            <td>{(f"{alpha_val:.3f}" if alpha_val is not None else "-")}</td>
                        </tr>
                        {(
                            f"<tr><td><strong>{'Решение' if is_ru else 'Decision'}:</strong></td><td>{html.escape(decision)}</td></tr>"
                            if decision
                            else ""
                        )}
                        <tr>
                            <td><strong>{'Вывод' if is_ru else 'Result'}:</strong></td>
                            <td>{sig_text}</td>
                        </tr>
                    </table>
                    <div style="margin-top:10px; color:#111; font-size:12px;">
                        <div><strong>{'Гипотезы' if is_ru else 'Hypotheses'}:</strong></div>
                        <div>{html.escape(hypothesis_h0)}</div>
                        <div>{html.escape(hypothesis_h1)}</div>
                        {(
                            f"<div style='margin-top:4px;'><strong>{'Решение' if is_ru else 'Decision'}:</strong> {html.escape(decision)}</div>"
                            if decision
                            else ""
                        )}
                    </div>
                </div>
            </div>
        """

        assumptions = res.get("assumptions") if isinstance(res, dict) else None
        assumptions_badges = self._render_assumptions_badge(
            assumptions if isinstance(assumptions, dict) else {},
            is_ru,
        )
        if assumptions_badges:
            section_html += assumptions_badges

        power_badge = self._render_power_badge(res if isinstance(res, dict) else {}, is_ru)
        if power_badge:
            section_html += power_badge

        if res.get("type") == "mixed_effects":
            n_obs = res.get("n_observations")
            n_subjects = res.get("n_subjects")
            outcome = res.get("outcome")
            formula = res.get("formula")
            section_html += f"""
                <div style=\"margin-top: 12px; color: #475569; font-size: 12px;\">
                    <div><strong>{'Показатель' if is_ru else 'Outcome'}:</strong> {outcome or '-'} </div>
                    <div><strong>{'Формула' if is_ru else 'Formula'}:</strong> {formula or '-'} </div>
                    <div><strong>N:</strong> {n_obs if isinstance(n_obs, (int, float)) else '-'} • <strong>{'Субъекты' if is_ru else 'Subjects'}:</strong> {n_subjects if isinstance(n_subjects, (int, float)) else '-'} </div>
                </div>
            """

            interaction_p = res.get("interaction_p_value")
            if interaction_p is not None:
                try:
                    ip = float(interaction_p)
                    ip_s = "< 0.001" if (np.isfinite(ip) and ip < 0.001) else (f"{ip:.4f}" if np.isfinite(ip) else "-")
                except Exception:
                    ip_s = "-"
                section_html += f"""<div style=\"margin-top: 6px; color: #111; font-size: 12px;\"><strong>{'Визит×Группа' if is_ru else 'Time×Group'}:</strong> p = <span class=\"stat-val\">{ip_s}</span></div>"""

            est = res.get("estimated_means")
            if isinstance(est, dict) and est:
                rows = []
                for g, tmap in est.items():
                    if not isinstance(tmap, dict):
                        continue
                    for t, item in tmap.items():
                        if not isinstance(item, dict):
                            continue
                        e = item.get("estimate")
                        lo = item.get("ci_lower")
                        hi = item.get("ci_upper")
                        n = item.get("n")
                        rows.append(
                            f"<tr><td>{g}</td><td>{t}</td><td>{_fmt_stat(e, 2)}</td><td>[{_fmt_stat(lo, 2)}, {_fmt_stat(hi, 2)}]</td><td>{str(int(n)) if isinstance(n,(int,float)) else '-'}</td></tr>"
                        )
                if rows:
                    section_html += f"""
                    <h3>{'Оценённые средние' if is_ru else 'Estimated Means'}</h3>
                    <table>
                        <thead><tr><th>{'Группа' if is_ru else 'Group'}</th><th>{'Время' if is_ru else 'Time'}</th><th>{'Оценка' if is_ru else 'Estimate'}</th><th>{'95% ДИ' if is_ru else '95% CI'}</th><th>n</th></tr></thead>
                        <tbody>
                            {''.join(rows)}
                        </tbody>
                    </table>
                    """

            coefs = res.get("coefficients")
            if isinstance(coefs, list) and coefs:
                rows = []
                for c in coefs[:60]:
                    if not isinstance(c, dict):
                        continue
                    term = str(c.get("term") or "-")
                    coef = c.get("coefficient")
                    se = c.get("std_error")
                    p = c.get("p_value")
                    p_s = "< 0.001" if (isinstance(p,(int,float)) and float(p) < 0.001) else _fmt_stat(p, 4)
                    rows.append(f"<tr><td>{term}</td><td class=\"stat-val\">{_fmt_stat(coef)}</td><td>{_fmt_stat(se)}</td><td class=\"stat-val\">{p_s}</td></tr>")
                if rows:
                    section_html += f"""
                    <h3>{'Коэффициенты' if is_ru else 'Coefficients'}</h3>
                    <table>
                        <thead><tr><th>{'Параметр' if is_ru else 'Term'}</th><th>{'Оценка' if is_ru else 'Coef'}</th><th>SE</th><th>p</th></tr></thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                    """

        if res.get("type") == "clustered_correlation":
            n_obs = res.get("n_observations")
            n_vars = res.get("n_variables")
            n_clusters = res.get("n_clusters")
            method = res.get("method")
            method_label = None
            if isinstance(method, dict):
                method_label = method.get("id") or method.get("name")
            section_html += f"""
                <div style=\"margin-top: 12px; color: #475569; font-size: 12px;\">
                    <div><strong>{'Метод' if is_ru else 'Method'}:</strong> {method_label or '-'} </div>
                    <div><strong>{'Наблюдения' if is_ru else 'Observations'}:</strong> {n_obs if isinstance(n_obs, (int, float)) else '-'} </div>
                    <div><strong>{'Переменные' if is_ru else 'Variables'}:</strong> {n_vars if isinstance(n_vars, (int, float)) else '-'} • <strong>{'Кластеры' if is_ru else 'Clusters'}:</strong> {n_clusters if isinstance(n_clusters, (int, float)) else '-'} </div>
                </div>
            """

            ca = res.get("cluster_assignments")
            if isinstance(ca, dict) and ca:
                clusters: Dict[str, int] = {}
                for _, cid in ca.items():
                    k = str(cid)
                    clusters[k] = int(clusters.get(k, 0)) + 1
                rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(clusters.items(), key=lambda kv: (-kv[1], kv[0]))])
                section_html += f"""
                <h3>{'Размеры кластеров' if is_ru else 'Cluster Sizes'}</h3>
                <table>
                    <thead><tr><th>{'Кластер' if is_ru else 'Cluster'}</th><th>{'Переменных' if is_ru else 'Variables'}</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                """

        if method_id == "bland_altman" or res.get("type") == "agreement":
            section_html += f"""
            <h3>{'Показатели согласия' if is_ru else 'Agreement metrics'}</h3>
            <table>
                <thead><tr><th>{'Метрика' if is_ru else 'Metric'}</th><th>{'Значение' if is_ru else 'Value'}</th></tr></thead>
                <tbody>
                    <tr><td>{'Средняя разница (bias)' if is_ru else 'Mean difference (bias)'}</td><td class="stat-val">{_fmt_stat(res.get('mean_difference'), 3)}</td></tr>
                    <tr><td>{'LoA нижняя' if is_ru else 'LoA lower'}</td><td class="stat-val">{_fmt_stat(res.get('loa_lower'), 3)}</td></tr>
                    <tr><td>{'LoA верхняя' if is_ru else 'LoA upper'}</td><td class="stat-val">{_fmt_stat(res.get('loa_upper'), 3)}</td></tr>
                    <tr><td>{'Вне LoA' if is_ru else 'Outside LoA'}</td><td>{(
                        f"{int(res.get('outside_loa_count'))}/{int(res.get('n_observations'))} ({float(res.get('outside_loa_fraction')) * 100.0:.1f}%)"
                        if isinstance(res.get('outside_loa_count'), (int, float))
                        and isinstance(res.get('n_observations'), (int, float))
                        and isinstance(res.get('outside_loa_fraction'), (int, float))
                        else "-"
                    )}</td></tr>
                    <tr><td>{'Пропорциональное смещение (p)' if is_ru else 'Proportional bias (p)'}</td><td class="stat-val">{_fmt_p_inline((res.get('proportional_bias') or {}).get('p_value') if isinstance(res.get('proportional_bias'), dict) else None)}</td></tr>
                    <tr><td>{'Оценка согласия' if is_ru else 'Agreement rating'}</td><td>{html.escape(str((res.get('agreement_interpretation') or {}).get('label_ru') if is_ru and isinstance(res.get('agreement_interpretation'), dict) and (res.get('agreement_interpretation') or {}).get('label_ru') else ((res.get('agreement_interpretation') or {}).get('label') if isinstance(res.get('agreement_interpretation'), dict) else (res.get('agreement_rating') or '-'))))}</td></tr>
                </tbody>
            </table>
            """

        if method_id == "time_series_analysis" or res.get("type") == "time_series":
            trend = res.get("trend") if isinstance(res.get("trend"), dict) else {}
            adf = res.get("adf") if isinstance(res.get("adf"), dict) else {}
            diagnostics = res.get("diagnostics") if isinstance(res.get("diagnostics"), dict) else {}
            ljung = diagnostics.get("ljung_box") if isinstance(diagnostics.get("ljung_box"), dict) else {}
            time_quality = res.get("time_quality") if isinstance(res.get("time_quality"), dict) else {}
            if not time_quality and isinstance(diagnostics.get("time_quality"), dict):
                time_quality = diagnostics.get("time_quality")
            forecast = res.get("forecast") if isinstance(res.get("forecast"), dict) else {}
            forecast_n = len(forecast.get("points") or []) if isinstance(forecast.get("points"), list) else 0
            axis_kind_raw = str(res.get("time_axis_kind") or "").strip().lower()
            axis_kind_label = {
                "datetime": ("календарная дата/время" if is_ru else "calendar date/time"),
                "numeric": ("числовая последовательность" if is_ru else "numeric sequence"),
                "categorical": ("категориальная ось" if is_ru else "categorical axis"),
                "index": ("порядковый индекс" if is_ru else "row index"),
            }.get(axis_kind_raw, "-")
            quality_raw = str(time_quality.get("quality") or "").strip().lower()
            quality_label = {
                "ok": ("норма" if is_ru else "ok"),
                "caution": ("осторожно" if is_ru else "caution"),
                "warning": ("высокий риск" if is_ru else "high risk"),
            }.get(quality_raw, "-")
            parse_ratio_txt = "-"
            parse_ratio = time_quality.get("datetime_parse_ratio")
            try:
                parse_ratio_f = float(parse_ratio)
                if np.isfinite(parse_ratio_f):
                    parse_ratio_txt = f"{parse_ratio_f * 100.0:.1f}%"
            except Exception:
                parse_ratio_txt = "-"
            year_range_txt = "-"
            try:
                min_year = int(time_quality.get("min_year"))
                max_year = int(time_quality.get("max_year"))
                year_range_txt = f"{min_year}-{max_year}"
            except Exception:
                year_range_txt = "-"
            time_flags = time_quality.get("flags")
            if isinstance(time_flags, list):
                clean_flags = [str(v).strip() for v in time_flags if str(v).strip()]
            else:
                clean_flags = []
            flags_text = ", ".join(clean_flags) if clean_flags else "-"
            inferred_freq = str(time_quality.get("inferred_frequency") or "").strip() or "-"
            warning_items = res.get("warnings")
            warning_lines = []
            if isinstance(warning_items, list):
                for item in warning_items:
                    txt = str(item).strip()
                    if not txt:
                        continue
                    warning_lines.append(txt)
            warning_html = ""
            if warning_lines:
                label = "Предупреждения по хронологии" if is_ru else "Chronology warnings"
                warning_html = (
                    f"<h4>{label}</h4>"
                    + "<ul>"
                    + "".join(f"<li>{html.escape(msg)}</li>" for msg in warning_lines[:6])
                    + "</ul>"
                )
            section_html += f"""
            <h3>{'Диагностика ряда' if is_ru else 'Series diagnostics'}</h3>
            <table>
                <thead><tr><th>{'Метрика' if is_ru else 'Metric'}</th><th>{'Значение' if is_ru else 'Value'}</th></tr></thead>
                <tbody>
                    <tr><td>{'Тип временной оси' if is_ru else 'Time axis type'}</td><td>{axis_kind_label}</td></tr>
                    <tr><td>{'Стационарность (ADF p)' if is_ru else 'Stationarity (ADF p)'}</td><td class="stat-val">{_fmt_p_inline(adf.get('p_value') or res.get('p_value'))}</td></tr>
                    <tr><td>{'Тренд (наклон)' if is_ru else 'Trend (slope)'}</td><td class="stat-val">{(
                        f"{float(trend.get('slope')):.4f}" if isinstance(trend.get('slope'), (int, float)) and np.isfinite(float(trend.get('slope'))) else "-"
                    )}</td></tr>
                    <tr><td>{'Ljung-Box (p)' if is_ru else 'Ljung-Box (p)'}</td><td class="stat-val">{_fmt_p_inline(ljung.get('p_value'))}</td></tr>
                    <tr><td>{'Белый шум' if is_ru else 'White-noise-like'}</td><td>{(
                        'да' if bool(ljung.get('white_noise_like')) else 'нет'
                    ) if isinstance(ljung.get('white_noise_like'), bool) and is_ru else (
                        'yes' if bool(ljung.get('white_noise_like')) else 'no'
                    ) if isinstance(ljung.get('white_noise_like'), bool) else '-'}</td></tr>
                    <tr><td>{'Прогноз (точек)' if is_ru else 'Forecast (points)'}</td><td>{forecast_n if forecast_n > 0 else '-'}</td></tr>
                    <tr><td>{'Качество временной оси' if is_ru else 'Time axis quality'}</td><td>{html.escape(quality_label)}</td></tr>
                    <tr><td>{'Парсинг datetime' if is_ru else 'Datetime parse ratio'}</td><td>{html.escape(parse_ratio_txt)}</td></tr>
                    <tr><td>{'Диапазон лет' if is_ru else 'Year range'}</td><td>{html.escape(year_range_txt)}</td></tr>
                    <tr><td>{'Интервал (infer)' if is_ru else 'Inferred frequency'}</td><td>{html.escape(inferred_freq)}</td></tr>
                    <tr><td>{'Флаги качества' if is_ru else 'Quality flags'}</td><td>{html.escape(flags_text)}</td></tr>
                </tbody>
            </table>
            {warning_html}
            """

        if isinstance(res, dict):
            assumptions = res.get("assumptions")
            if isinstance(assumptions, dict) and assumptions:
                parts = []
                norm = assumptions.get("normality")
                if isinstance(norm, dict) and norm:
                    rows = []
                    for g, item in norm.items():
                        if not isinstance(item, dict):
                            continue
                        pv = item.get("p_value")
                        passed = item.get("passed")
                        pv_s = "-"
                        try:
                            pv_f = float(pv)
                            pv_s = "< 0.001" if (np.isfinite(pv_f) and pv_f < 0.001) else (f"{pv_f:.4f}" if np.isfinite(pv_f) else "-")
                        except Exception:
                            pv_s = "-"
                        rows.append(
                            f"<tr><td>{str(g)}</td><td class=\"stat-val\">{pv_s}</td><td>{('норма' if is_ru else 'ok') if passed is True else (('нарушено' if is_ru else 'fail') if passed is False else '-')}</td></tr>"
                        )
                    if rows:
                        parts.append(
                            f"""<h3>{'Проверки предпосылок: нормальность' if is_ru else 'Assumptions: Normality'}</h3><table><thead><tr><th>{'Группа' if is_ru else 'Group'}</th><th>{'p Шапиро' if is_ru else 'Shapiro p'}</th><th>{'Статус' if is_ru else 'Status'}</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"""
                        )
                homo = assumptions.get("homogeneity")
                if isinstance(homo, dict):
                    pv = homo.get("p_value")
                    passed = homo.get("passed")
                    pv_s = "-"
                    try:
                        pv_f = float(pv)
                        pv_s = "< 0.001" if (np.isfinite(pv_f) and pv_f < 0.001) else (f"{pv_f:.4f}" if np.isfinite(pv_f) else "-")
                    except Exception:
                        pv_s = "-"
                    parts.append(
                        f"""<h3>{'Проверки предпосылок: однородность дисперсий' if is_ru else 'Assumptions: Homogeneity'}</h3><table><thead><tr><th>{'p Левена' if is_ru else 'Levene p'}</th><th>{'Статус' if is_ru else 'Status'}</th></tr></thead><tbody><tr><td class=\"stat-val\">{pv_s}</td><td>{('норма' if is_ru else 'ok') if passed is True else (('нарушено' if is_ru else 'fail') if passed is False else '-')}</td></tr></tbody></table>"""
                    )
                if parts:
                    section_html += "".join(parts)

            if rationale_ru:
                section_html += f"<div style=\"margin-top: 10px; color: #111; font-size: 12px;\"><strong>Обоснование выбора теста:</strong> {html.escape(rationale_ru)}</div>"

            compare_rows = _build_pairwise_comparison_rows(res)
            if compare_rows:
                def _fmt_p(v: Any) -> str:
                    try:
                        if v is None:
                            return "-"
                        p = float(v)
                        if not np.isfinite(p):
                            return "-"
                        return "< 0.001" if p < 0.001 else f"{p:.4f}"
                    except Exception:
                        return "-"

                is_median = compare_rows[0].get("center_label") == "median"
                a_hdr = "Me [Q1; Q3]" if is_median else "M ± SD"

                rows = []
                for r in compare_rows[:80]:
                    a = html.escape(str(r.get("a") or "-"))
                    b = html.escape(str(r.get("b") or "-"))

                    a_n = r.get("a_n")
                    b_n = r.get("b_n")
                    a_n_s = f"n={int(a_n)}" if isinstance(a_n, (int, float)) else ""
                    b_n_s = f"n={int(b_n)}" if isinstance(b_n, (int, float)) else ""

                    if is_median:
                        q1a, q3a = r.get("a_spread") if isinstance(r.get("a_spread"), tuple) else (None, None)
                        q1b, q3b = r.get("b_spread") if isinstance(r.get("b_spread"), tuple) else (None, None)
                        a_s = f"{_fmt_stat(r.get('a_center'))} [{_fmt_stat(q1a)}; {_fmt_stat(q3a)}] {a_n_s}".strip()
                        b_s = f"{_fmt_stat(r.get('b_center'))} [{_fmt_stat(q1b)}; {_fmt_stat(q3b)}] {b_n_s}".strip()
                    else:
                        a_s = f"{_fmt_stat(r.get('a_center'))} ± {_fmt_stat(r.get('a_spread'))} {a_n_s}".strip()
                        b_s = f"{_fmt_stat(r.get('b_center'))} ± {_fmt_stat(r.get('b_spread'))} {b_n_s}".strip()

                    diff_s = _fmt_stat(r.get("diff"))
                    diff_pct = r.get("diff_pct")
                    diff_pct_s = (f"{_fmt_stat(diff_pct, 1)}%" if diff_pct is not None else "-")

                    eff = r.get("effect_size")
                    eff_name = r.get("effect_size_name")
                    eff_s = (f"{html.escape(str(eff_name or 'effect'))}={_fmt_stat(eff)}" if eff is not None else "-")

                    rows.append(
                        "<tr>"
                        + f"<td><strong>{a} vs {b}</strong></td>"
                        + f"<td>{html.escape(a_s)}</td>"
                        + f"<td>{html.escape(b_s)}</td>"
                        + f"<td class=\"stat-val\">{diff_s}</td>"
                        + f"<td class=\"stat-val\">{diff_pct_s}</td>"
                        + f"<td class=\"stat-val\">{_fmt_p(r.get('p_value'))}</td>"
                        + f"<td class=\"stat-val\">{_fmt_stat(r.get('bf10'), 3)}</td>"
                        + f"<td>{eff_s}</td>"
                        + "</tr>"
                    )

                if rows:
                    section_html += f"""
                    <h3>{'Сравнение групп (сводная таблица)' if is_ru else 'Group Comparison (Summary Table)'}</h3>
                    <table>
                        <thead><tr><th>{'Сравнение' if is_ru else 'Comparison'}</th><th>{a_hdr} A</th><th>{a_hdr} B</th><th>Δ (A−B)</th><th>Δ%</th><th>p</th><th>BF10</th><th>{'Эффект' if is_ru else 'Effect'}</th></tr></thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                    <div style="margin-top: 8px; color: #475569; font-size: 12px;">
                        {(
                            'Пояснения: Δ — абсолютная разница между центральными тенденциями (A−B); Δ% — относительная разница (A−B)/B. p — уровень значимости; BF10 — сила свидетельства в пользу H1 (чем больше, тем сильнее), значения <1 поддерживают H0; эффект — размер эффекта (насколько велико отличие, а не только значимость).'
                            if is_ru
                            else 'Notes: Δ is the absolute difference (A−B); Δ% is relative difference (A−B)/B. p is the p-value; BF10 quantifies evidence for H1 (larger is stronger), values <1 support H0; effect is the effect size (magnitude, not only significance).'
                        )}
                    </div>
                    """
            elif groups and len(groups) >= 3:
                section_html += f"<div style=\"margin-top: 10px; color: #475569; font-size: 12px;\">{('Есть 3+ группы: попарные сравнения (post-hoc) не выполнены или отсутствуют в результате.' if is_ru else '3+ groups: pairwise post-hoc comparisons are not available for this step.')}</div>"

            if res.get("type") == "regression":
                coef = res.get("coefficients")
                if isinstance(coef, list) and coef:
                    rows = []
                    for c in coef[:120]:
                        if not isinstance(c, dict):
                            continue
                        var = str(c.get("variable") or "-")
                        b = c.get("coefficient")
                        p = c.get("p_value")
                        se = c.get("std_err")
                        orv = c.get("odds_ratio")
                        p_s = "< 0.001" if (isinstance(p,(int,float)) and float(p) < 0.001) else _fmt_stat(p, 4)
                        rows.append(
                            f"<tr><td>{var}</td><td class=\"stat-val\">{_fmt_stat(b)}</td><td>{_fmt_stat(se)}</td><td class=\"stat-val\">{p_s}</td><td class=\"stat-val\">{_fmt_stat(orv, 3) if orv is not None else '-'}</td></tr>"
                        )
                    section_html += f"""
                    <h3>{'Коэффициенты регрессии' if is_ru else 'Regression Coefficients'}</h3>
                    <table>
                        <thead><tr><th>{'Переменная' if is_ru else 'Variable'}</th><th>{'Коэф.' if is_ru else 'Coef'}</th><th>SE</th><th>p</th><th>OR</th></tr></thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                    """

                roc = res.get("roc")
                if isinstance(roc, dict) and roc.get("auc") is not None:
                    try:
                        auc_v = float(roc.get("auc"))
                        auc_s = f"{auc_v:.3f}" if np.isfinite(auc_v) else "-"
                    except Exception:
                        auc_s = "-"
                    section_html += f"""<div style=\"margin-top: 10px; font-size: 12px; color: #111;\"><strong>ROC AUC:</strong> <span class=\"stat-val\">{auc_s}</span></div>"""

            bootstrap_lines = _bootstrap_trace_lines(res.get("bootstrap"), is_ru=is_ru)
            if bootstrap_lines:
                items = "".join([f"<li>{html.escape(str(line))}</li>" for line in bootstrap_lines])
                section_html += f"""
                <h3>{'Bootstrap-трассировка' if is_ru else 'Bootstrap trace'}</h3>
                <ul>{items}</ul>
                """

            plot_stats = res.get("plot_stats")
            if isinstance(plot_stats, dict) and plot_stats:
                rows = []
                for g, s in plot_stats.items():
                    if not isinstance(s, dict):
                        continue
                    try:
                        sd_f = float(s.get("sd")) if s.get("sd") is not None else None
                        var_s = f"{(sd_f ** 2):.2f}" if sd_f is not None and np.isfinite(sd_f) else "-"
                    except Exception:
                        var_s = "-"
                    try:
                        q1 = float(s.get("q1")) if s.get("q1") is not None else None
                        q3 = float(s.get("q3")) if s.get("q3") is not None else None
                        iqr_s = f"{(q3 - q1):.2f}" if (q1 is not None and q3 is not None and np.isfinite(q1) and np.isfinite(q3)) else "-"
                    except Exception:
                        iqr_s = "-"
                    mm = "-"
                    if s.get("min") is not None and s.get("max") is not None:
                        mm = f"{_fmt_stat(s.get('min'))} – {_fmt_stat(s.get('max'))}"
                    rows.append(
                        f"<tr><td>{str(g)}</td><td class=\"stat-val\">{str(int(s.get('count'))) if isinstance(s.get('count'), (int, float)) else '-'}</td><td>{_fmt_stat(s.get('mean'))}</td><td>{_fmt_stat(s.get('sd'))}</td><td>{var_s}</td><td>{_fmt_stat(s.get('median'))}</td><td>{_fmt_stat(s.get('q1'))}</td><td>{_fmt_stat(s.get('q3'))}</td><td>{iqr_s}</td><td>{mm}</td></tr>"
                    )
                if rows:
                    section_html += f"""
                    <h3>{'Описательная статистика по группам' if is_ru else 'Group Summary'}</h3>
                    <table>
                        <thead><tr><th>{'Группа' if is_ru else 'Group'}</th><th>n</th><th>{'Среднее' if is_ru else 'Mean'}</th><th>SD</th><th>{'Дисперсия' if is_ru else 'Variance'}</th><th>{'Медиана' if is_ru else 'Median'}</th><th>Q1</th><th>Q3</th><th>IQR</th><th>min–max</th></tr></thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                    """
        
        # Paired wide descriptive stats table (median / IQR / mean / SD)
        if method_id == "paired_wide" or res.get("plot_hint") == "paired_dot":
            descriptive = res.get("descriptive") if isinstance(res, dict) else None
            baseline_col = res.get("baseline") if isinstance(res, dict) else None
            follow_col = res.get("follow") if isinstance(res, dict) else None
            if isinstance(descriptive, dict) and descriptive:
                desc_rows = []
                labels = []
                if baseline_col and baseline_col in descriptive:
                    labels.append((baseline_col, descriptive[baseline_col], "Контроль" if is_ru else "Baseline"))
                if follow_col and follow_col in descriptive:
                    labels.append((follow_col, descriptive[follow_col], "Опыт" if is_ru else "Follow-up"))
                delta_d = descriptive.get("delta")
                if isinstance(delta_d, dict):
                    labels.append(("delta", delta_d, "Δ (разность)" if is_ru else "Δ (difference)"))

                for _, d, label in labels:
                    if not isinstance(d, dict):
                        continue
                    n_d = d.get("n")
                    iqr = None
                    try:
                        q1v = float(d.get("q1"))
                        q3v = float(d.get("q3"))
                        iqr = q3v - q1v
                    except Exception:
                        pass
                    desc_rows.append(
                        f"<tr>"
                        f"<td><strong>{html.escape(str(label))}</strong></td>"
                        f"<td class=\"stat-val\">{str(int(n_d)) if isinstance(n_d, (int, float)) else '-'}</td>"
                        f"<td>{_fmt_stat(d.get('mean'))} ± {_fmt_stat(d.get('std'))}</td>"
                        f"<td class=\"stat-val\">{_fmt_stat(d.get('median'))}</td>"
                        f"<td>{_fmt_stat(d.get('q1'))}</td>"
                        f"<td>{_fmt_stat(d.get('q3'))}</td>"
                        f"<td>{_fmt_stat(iqr)}</td>"
                        f"<td>{_fmt_stat(d.get('min'))} – {_fmt_stat(d.get('max'))}</td>"
                        f"</tr>"
                    )

                if desc_rows:
                    section_html += f"""
                    <h3>{'Описательная статистика' if is_ru else 'Descriptive Statistics'}</h3>
                    <table>
                        <thead><tr>
                            <th>{'Переменная' if is_ru else 'Variable'}</th>
                            <th>n</th>
                            <th>{'Среднее ± SD' if is_ru else 'Mean ± SD'}</th>
                            <th>{'Медиана' if is_ru else 'Median'}</th>
                            <th>Q1</th><th>Q3</th>
                            <th>IQR</th>
                            <th>min – max</th>
                        </tr></thead>
                        <tbody>{''.join(desc_rows)}</tbody>
                    </table>
                    """

        # Generate Plot

        img_b64 = self._generate_plot_image(res)
        if img_b64:
            section_html += f'<div class="plot-container"><img src="data:image/png;base64,{img_b64}" alt="Analysis Plot" /></div>'
        extra_plots = self._iter_additional_plot_payloads(res if isinstance(res, dict) else {})
        for idx, extra_res in enumerate(extra_plots, start=1):
            extra_img_b64 = self._generate_plot_image(extra_res)
            if not extra_img_b64:
                continue
            label = str(extra_res.get("plot_hint") or extra_res.get("type") or "plot")
            section_html += (
                f'<div class="plot-container"><img src="data:image/png;base64,{extra_img_b64}" '
                f'alt="Additional Analysis Plot {idx}" /></div>'
                f'<div style="text-align:center;color:#64748b;font-size:11px;">{html.escape(label)}</div>'
            )
            
        interpretation = None
        if is_ru:
            interpretation = res.get("ai_interpretation") or res.get("conclusion")
        else:
            interpretation = res.get("interpretation_en") or res.get("conclusion")
        if _is_placeholder_interpretation(interpretation):
            interpretation = _generate_fallback_interpretation(res if isinstance(res, dict) else {}, step_meta, is_ru)
        if interpretation:
            section_html += (
                f'<div class="ai-box"><strong>{"Интерпретация" if is_ru else "Interpretation"}:</strong><br>'
                + html.escape(str(interpretation))
                + "</div>"
            )
            
        section_html += "</div>"
        self.html_parts.append(section_html)

    def _add_longitudinal_section(self, res: Dict, step_id: str, step_meta: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        display_title = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        html = f"""
        <div class="card" id="step-{html.escape(step_id)}">
            <h2>{'Продольный анализ' if is_ru else 'Longitudinal Analysis'}: {html.escape(display_title)}</h2>
            <div style="margin-top:-6px;color:#64748b;font-size:12px;">ID: {html.escape(step_id)}</div>
            <p style="margin-bottom: 15px;">{('Разбиение по' if is_ru else 'Analysis split by')}: <strong>{res.get('split_by')}</strong></p>
            <table>
                <thead>
                    <tr>
                        <th>{'Временная точка / срез' if is_ru else 'Timepoint / Split'}</th>
                        <th>{'Метод' if is_ru else 'Method'}</th>
                        <th>p-value</th>
                        <th>{'Вывод' if is_ru else 'Result'}</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for slice_key, slice_res in res.get("slices", {}).items():
            is_sig = slice_res.get("significant", False)
            p_val = slice_res.get('p_value', 1.0)
            p_display = "< 0.001" if p_val < 0.001 else f"{p_val:.4f}"
            
            html += f"""
                <tr>
                    <td><strong>{slice_key}</strong></td>
                    <td>{(
                        _method_label_from_id(slice_res.get('method', {}).get('id') or slice_res.get('method', {}).get('name'), is_ru) or '-'
                        if isinstance(slice_res.get('method'), dict)
                        else (
                            _method_label_from_id(str(getattr(slice_res.get('method'), 'name')), is_ru) or '-'
                            if hasattr(slice_res.get('method'), 'name')
                            else (_method_label_from_id(slice_res.get('method'), is_ru) or '-')
                        )
                    )}</td>
                    <td><span class="stat-val { 'sig-yes' if is_sig else 'sig-no' }">{p_display}</span></td>
                    <td>{ ('Различия есть' if is_ru else 'Difference Detected') if is_sig else ('Различий нет' if is_ru else 'No Difference') }</td>
                </tr>
            """
            
        html += "</tbody></table></div>"
        self.html_parts.append(html)

    def _add_batch_section(self, res: Dict[str, Any], step_id: str, step_meta: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        alpha_val = _coerce_alpha(
            res.get("alpha") if isinstance(res, dict) else None,
            (self.data or {}).get("alpha") if isinstance(self.data, dict) else None,
        )
        group_col = (res.get("group") or res.get("group_column")) if isinstance(res, dict) else None
        multiplicity = res.get("multiplicity_correction") if isinstance(res, dict) else None
        multiplicity_trace = res.get("multiplicity_trace") if isinstance(res, dict) else None
        post_hoc = res.get("post_hoc") if isinstance(res, dict) else None
        post_hoc_correction = res.get("post_hoc_correction") if isinstance(res, dict) else None
        step_type = str(res.get("type") or "") if isinstance(res, dict) else ""
        display_title = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        correction_label = _format_correction_label(multiplicity, is_ru) if multiplicity else ""
        post_hoc_corr_label = _format_correction_label(post_hoc_correction, is_ru) if post_hoc_correction else ""

        trace_n_total = None
        trace_n_valid = None
        if isinstance(multiplicity_trace, dict):
            try:
                trace_n_total = int(multiplicity_trace.get("n_total"))
            except Exception:
                trace_n_total = None
            try:
                trace_n_valid = int(multiplicity_trace.get("n_valid"))
            except Exception:
                trace_n_valid = None

        def _fmt_p(value: Any) -> str:
            try:
                if value is None:
                    return "-"
                p = float(value)
                if not np.isfinite(p):
                    return "-"
                return "< 0.001" if p < 0.001 else f"{p:.4f}"
            except Exception:
                return "-"

        def _fmt_group_stats(group_stats: Any, label: str) -> str:
            if not isinstance(group_stats, dict):
                return "-"
            stats = group_stats.get(label)
            if not isinstance(stats, dict):
                return "-"
            mean = _fmt_stat(stats.get("mean"), 2)
            sd = _fmt_stat(stats.get("sd"), 2)
            med = _fmt_stat(stats.get("median"), 2)
            q1 = _fmt_stat(stats.get("q1"), 2)
            q3 = _fmt_stat(stats.get("q3"), 2)
            n = stats.get("count")
            n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
            return f"{mean} ± {sd}; {med} [{q1}; {q3}] {n_s}".strip()

        def _render_rows(rows_payload: Dict[str, Any], title: Optional[str] = None) -> str:
            rows = rows_payload.get("rows") if isinstance(rows_payload, dict) else []
            rows = rows if isinstance(rows, list) else []
            sig_count = int(rows_payload.get("sig_count") or 0) if isinstance(rows_payload, dict) else 0
            group_labels = rows_payload.get("group_labels") if isinstance(rows_payload, dict) else None
            has_group_stats = isinstance(group_labels, list) and len(group_labels) == 2

            if not rows:
                return (
                    f"<h3>{html.escape(title)}</h3><p>{'Нет данных для табличного вывода.' if is_ru else 'No tabular data available.'}</p>"
                    if title
                    else f"<p>{'Нет данных для табличного вывода.' if is_ru else 'No tabular data available.'}</p>"
                )

            header = (
                f"<h3>{html.escape(title)}</h3>" if title else ""
            ) + f"""
            <div style=\"margin-top: 6px; color: #475569; font-size: 12px;\">
                {('Показателей' if is_ru else 'Targets')}: <strong>{len(rows)}</strong> •
                {('Значимых' if is_ru else 'Significant')}: <strong>{sig_count}</strong>
            </div>
            """

            body_rows: List[str] = []
            for row in rows[:240]:
                target = html.escape(str(row.get("target") or "-"))
                p_raw = _fmt_p(row.get("p_raw"))
                p_adj = _fmt_p(row.get("p_adj"))
                sig_s = ("да" if is_ru else "yes") if row.get("sig") else ("нет" if is_ru else "no")
                method = html.escape(_method_label_from_id(row.get("method"), is_ru) or str(row.get("method") or "-"))
                group_stats = row.get("group_stats")
                if has_group_stats:
                    a = html.escape(_fmt_group_stats(group_stats, str(group_labels[0])))
                    b = html.escape(_fmt_group_stats(group_stats, str(group_labels[1])))
                    body_rows.append(
                        "<tr>"
                        + f"<td>{target}</td>"
                        + f"<td>{a}</td>"
                        + f"<td>{b}</td>"
                        + f"<td class=\"stat-val\">{p_raw}</td>"
                        + f"<td class=\"stat-val\">{p_adj}</td>"
                        + f"<td>{sig_s}</td>"
                        + f"<td>{method}</td>"
                        + "</tr>"
                    )
                else:
                    body_rows.append(
                        "<tr>"
                        + f"<td>{target}</td>"
                        + f"<td class=\"stat-val\">{p_raw}</td>"
                        + f"<td class=\"stat-val\">{p_adj}</td>"
                        + f"<td>{sig_s}</td>"
                        + f"<td>{method}</td>"
                        + "</tr>"
                    )

            if has_group_stats:
                g1 = html.escape(str(group_labels[0]))
                g2 = html.escape(str(group_labels[1]))
                table = f"""
                <table>
                    <thead>
                        <tr>
                            <th>{'Показатель' if is_ru else 'Target'}</th>
                            <th>{g1}: M±SD; Me[Q1;Q3]</th>
                            <th>{g2}: M±SD; Me[Q1;Q3]</th>
                            <th>p</th>
                            <th>p(adj)</th>
                            <th>{'Значимо' if is_ru else 'Sig'}</th>
                            <th>{'Тест' if is_ru else 'Test'}</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(body_rows)}</tbody>
                </table>
                """
            else:
                table = f"""
                <table>
                    <thead>
                        <tr>
                            <th>{'Показатель' if is_ru else 'Target'}</th>
                            <th>p</th>
                            <th>p(adj)</th>
                            <th>{'Значимо' if is_ru else 'Sig'}</th>
                            <th>{'Тест' if is_ru else 'Test'}</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(body_rows)}</tbody>
                </table>
                """
            return header + table

        title = "Пакетный анализ" if is_ru else "Batch analysis"
        if str(res.get("mode") or "").strip().lower() == "delta":
            title = "Пакетный Δ-анализ" if is_ru else "Batch delta analysis"
        if step_type == "timepoint_batch_analysis":
            title = "Пакетный анализ по срезам" if is_ru else "Timepoint batch analysis"

        section_html = f"""
        <div class=\"card\" id=\"step-{html.escape(step_id)}\">
            <h2>{title}: {html.escape(display_title)}</h2>
            <div style="margin-top:-6px;color:#64748b;font-size:12px;">ID: {html.escape(step_id)}</div>
            {(
                f"<div style='margin-top: -4px; color: #475569; font-size: 12px;'><strong>{'Группировка' if is_ru else 'Group'}:</strong> {html.escape(str(group_col))}</div>"
                if group_col else ""
            )}
            <div style=\"margin-top: 4px; color: #475569; font-size: 12px;\">
                <strong>{'Альфа' if is_ru else 'Alpha'}:</strong> {_fmt_stat(alpha_val, 3)}
                {(
                    f" • <strong>{'Поправка' if is_ru else 'Correction'}:</strong> {html.escape(str(correction_label or multiplicity))}"
                    if multiplicity
                    else ""
                )}
                {(
                    f" • <strong>{'Скорректировано тестов' if is_ru else 'Corrected tests'}:</strong> {trace_n_valid}/{trace_n_total}"
                    if isinstance(trace_n_valid, int) and isinstance(trace_n_total, int)
                    else ""
                )}
                {(
                    f" • <strong>{'Post-hoc' if not is_ru else 'Пост-хок'}:</strong> "
                    + html.escape(str(post_hoc))
                    + (
                        f" ({html.escape(str(post_hoc_corr_label or post_hoc_correction))})"
                        if post_hoc_correction and str(post_hoc_correction).strip().lower() != "none"
                        else ""
                    )
                    if post_hoc and str(post_hoc).strip().lower() != "none"
                    else ""
                )}
            </div>
            <div style="margin-top: 8px; color: #334155; font-size: 12px;">
                {(
                    "Для каждого теста приведены описательные статистики групп (M±SD и Me[Q1;Q3]) рядом с p и p(adj)."
                    if is_ru
                    else "Each test is linked with group descriptives (M±SD and Me[Q1;Q3]) alongside p and p(adj)."
                )}
            </div>
        """
        rationale = _batch_method_selection_rationale(step_meta, res if isinstance(res, dict) else {}, is_ru)
        if rationale:
            section_html += (
                "<div style=\"margin-top: 8px; color: #111; font-size: 12px;\">"
                + f"<strong>{'Обоснование выбора теста' if is_ru else 'Test-selection rationale'}:</strong> "
                + html.escape(str(rationale))
                + "</div>"
            )

        if step_type == "batch_analysis":
            rows_payload = _collect_batch_inferential_rows(res.get("items"), alpha_val)
            section_html += _render_rows(rows_payload)
        else:
            split_by = res.get("split_by")
            if split_by:
                section_html += (
                    f"<div style='margin-top: 8px; color: #475569; font-size: 12px;'><strong>{'Разбиение' if is_ru else 'Split by'}:</strong> "
                    + html.escape(str(split_by))
                    + "</div>"
                )

            slices = res.get("slices")
            slices = slices if isinstance(slices, dict) else {}

            def _slice_sort(value: Any) -> Any:
                try:
                    return float(value)
                except Exception:
                    return str(value)

            for slice_key in sorted(slices.keys(), key=_slice_sort):
                slice_res = slices.get(slice_key)
                if not isinstance(slice_res, dict):
                    continue
                rows_payload = _collect_batch_inferential_rows(slice_res.get("items"), alpha_val)
                trace_by_slice = res.get("multiplicity_trace_by_slice") if isinstance(res.get("multiplicity_trace_by_slice"), dict) else {}
                slice_trace = trace_by_slice.get(slice_key)
                if not isinstance(slice_trace, dict):
                    slice_trace = slice_res.get("multiplicity_trace") if isinstance(slice_res.get("multiplicity_trace"), dict) else None
                slice_n_total = None
                slice_n_valid = None
                if isinstance(slice_trace, dict):
                    try:
                        slice_n_total = int(slice_trace.get("n_total"))
                    except Exception:
                        slice_n_total = None
                    try:
                        slice_n_valid = int(slice_trace.get("n_valid"))
                    except Exception:
                        slice_n_valid = None
                slice_title = ("Точка" if is_ru else "Slice") + f": {slice_key}"
                if isinstance(slice_n_valid, int) and isinstance(slice_n_total, int):
                    slice_title += (
                        f" ({'corr' if not is_ru else 'корр'}: {slice_n_valid}/{slice_n_total})"
                    )
                section_html += _render_rows(
                    rows_payload,
                    title=slice_title,
                )

        section_html += "</div>"
        self.html_parts.append(section_html)

    def _add_responder_section(self, res: Dict, step_id: str, step_meta: Optional[Dict[str, Any]] = None):
        is_ru = bool(getattr(self, "is_ru", False))
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        display_title = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        if not isinstance(res, dict):
            return
        by_visit = res.get("by_visit")
        if not isinstance(by_visit, dict) or not by_visit:
            return

        outcome = res.get("outcome")
        baseline = res.get("baseline")
        baseline_time = baseline.get("time") if isinstance(baseline, dict) else None
        threshold = res.get("threshold")
        direction = res.get("direction")

        def _fmt_p(value: Any) -> str:
            try:
                if value is None:
                    return "-"
                p = float(value)
                if not np.isfinite(p):
                    return "-"
                return "< 0.001" if p < 0.001 else f"{p:.4f}"
            except Exception:
                return "-"

        def _sort_key(v: Any) -> Any:
            try:
                return float(v)
            except Exception:
                return str(v)

        header_bits = []
        if baseline_time is not None:
            header_bits.append(("база" if is_ru else "baseline") + f"={baseline_time}")
        if threshold is not None:
            header_bits.append(("порог" if is_ru else "threshold") + f"={threshold}")
        if direction:
            header_bits.append(("направление" if is_ru else "direction") + f"={direction}")

        html = f"""
        <div class=\"card\" id=\"step-{step_id}\">
            <h2>{'Анализ респондеров' if is_ru else 'Responder Analysis'}: {html.escape(display_title)}</h2>
            <div style="margin-top:-6px;color:#64748b;font-size:12px;">ID: {html.escape(step_id)}</div>
            <div style=\"margin-top: -6px; color: #64748b; font-size: 12px;\">{str(outcome) if outcome else ''}</div>
            <div style=\"margin-top: 8px; color: #111; font-size: 12px;\"><strong>{' • '.join(header_bits)}</strong></div>
        """

        for visit_key in sorted(by_visit.keys(), key=_sort_key):
            v = by_visit.get(visit_key)
            if not isinstance(v, dict):
                continue
            groups = v.get("groups")
            if not isinstance(groups, dict) or not groups:
                continue

            test = v.get("test")
            test_p = test.get("p_value") if isinstance(test, dict) else None
            test_method = test.get("method") if isinstance(test, dict) else None
            method_s = str(test_method) if test_method else "chi_square"

            rows = []
            for g in sorted(groups.keys(), key=_sort_key):
                st = groups.get(g)
                if not isinstance(st, dict):
                    continue
                total = st.get("total")
                responders = st.get("responders")
                rate = st.get("rate")
                try:
                    rate_pct = f"{float(rate) * 100.0:.1f}%" if rate is not None and np.isfinite(float(rate)) else "-"
                except Exception:
                    rate_pct = "-"
                rows.append(f"<tr><td>{str(g)}</td><td class=\"stat-val\">{str(responders) if responders is not None else '-'}</td><td>{str(total) if total is not None else '-'}</td><td class=\"stat-val\">{rate_pct}</td></tr>")

            if not rows:
                continue

            html += f"""
            <h3 style=\"margin-top: 18px;\">{('Визит' if is_ru else 'Visit')} {visit_key}</h3>
            <div style=\"margin-top: -6px; color: #64748b; font-size: 12px;\">{method_s} p={_fmt_p(test_p)}</div>
            <table>
                <thead><tr><th>{'Группа' if is_ru else 'Group'}</th><th>{'Респондеры' if is_ru else 'Responders'}</th><th>{'Всего' if is_ru else 'Total'}</th><th>{'Доля' if is_ru else 'Rate'}</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
            """

        html += "</div>"
        self.html_parts.append(html)

    def _add_global_descriptive_section(self) -> None:
        """Render a 'Table 0' global descriptive statistics for all numeric variables."""
        import html as _html_mod
        is_ru = bool(getattr(self, "is_ru", False))

        col_stats: dict = {}
        analysis_set = self.data.get("analysis_set") if isinstance(self.data, dict) else None
        descriptive = analysis_set.get("descriptive") if isinstance(analysis_set, dict) else None
        if isinstance(descriptive, dict):
            for col_name, d in descriptive.items():
                if not isinstance(d, dict):
                    continue
                try:
                    q1_raw = d.get("q1")
                    q3_raw = d.get("q3")
                    q1 = float(q1_raw) if q1_raw is not None else None
                    q3 = float(q3_raw) if q3_raw is not None else None
                    iqr_raw = d.get("iqr")
                    iqr = float(iqr_raw) if iqr_raw is not None else ((q3 - q1) if q1 is not None and q3 is not None else None)
                    col_stats[str(col_name)] = {
                        "n": d.get("n"),
                        "mean": d.get("mean"),
                        "std": d.get("std"),
                        "median": d.get("median"),
                        "q1": q1,
                        "q3": q3,
                        "iqr": iqr,
                        "min": d.get("min"),
                        "max": d.get("max"),
                    }
                except Exception:
                    continue

        if not col_stats:
            # Fallback: try to load source parquet and compute descriptive stats.
            df = None
            try:
                analysis_dataset = self.data.get("analysis_dataset") if isinstance(self.data, dict) else None
                if isinstance(analysis_dataset, dict):
                    parquet_path = analysis_dataset.get("parquet")
                    if isinstance(parquet_path, str) and parquet_path.endswith(".parquet"):
                        import os as _os
                        import pandas as _pd

                        if _os.path.exists(parquet_path):
                            df = _pd.read_parquet(parquet_path)
            except Exception:
                df = None

            if df is not None:
                import pandas as _pd

                numeric_cols = [c for c in df.columns if _pd.api.types.is_numeric_dtype(df[c])]
                for col in numeric_cols[:60]:
                    s = df[col].dropna()
                    if s.empty:
                        continue
                    try:
                        q1 = float(s.quantile(0.25))
                        q3 = float(s.quantile(0.75))
                        col_stats[str(col)] = {
                            "n": int(len(s)),
                            "mean": float(s.mean()),
                            "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
                            "median": float(s.median()),
                            "q1": q1,
                            "q3": q3,
                            "iqr": q3 - q1,
                            "min": float(s.min()),
                            "max": float(s.max()),
                        }
                    except Exception:
                        continue
            else:
                # Last fallback: derive from per-step descriptive payloads.
                results = self.data.get("results") if isinstance(self.data, dict) else {}
                if isinstance(results, dict):
                    for step_id, res in results.items():
                        if not isinstance(res, dict):
                            continue
                        desc = res.get("descriptive")
                        if not isinstance(desc, dict):
                            continue
                        for col_name, d in desc.items():
                            if col_name == "delta" or not isinstance(d, dict):
                                continue
                            if col_name not in col_stats:
                                try:
                                    q1_raw = d.get("q1")
                                    q3_raw = d.get("q3")
                                    q1 = float(q1_raw) if q1_raw is not None else None
                                    q3 = float(q3_raw) if q3_raw is not None else None
                                    iqr = (q3 - q1) if q1 is not None and q3 is not None else None
                                    col_stats[col_name] = {
                                        "n": d.get("n"),
                                        "mean": d.get("mean"),
                                        "std": d.get("std"),
                                        "median": d.get("median"),
                                        "q1": q1,
                                        "q3": q3,
                                        "iqr": iqr,
                                        "min": d.get("min"),
                                        "max": d.get("max"),
                                    }
                                except Exception:
                                    continue

        if not col_stats:
            return

        rows_html = []
        for col_name, s in col_stats.items():
            rows_html.append(
                f"<tr>"
                f"<td>{_html_mod.escape(str(col_name))}</td>"
                f"<td class='stat-val'>{s.get('n', '-')}</td>"
                f"<td>{_fmt_stat(s.get('mean'))} ± {_fmt_stat(s.get('std'))}</td>"
                f"<td class='stat-val'>{_fmt_stat(s.get('median'))}</td>"
                f"<td>{_fmt_stat(s.get('q1'))}</td>"
                f"<td>{_fmt_stat(s.get('q3'))}</td>"
                f"<td>{_fmt_stat(s.get('iqr'))}</td>"
                f"<td>{_fmt_stat(s.get('min'))} – {_fmt_stat(s.get('max'))}</td>"
                f"</tr>"
            )

        n_vars = len(col_stats)
        title = "Описательная статистика (Таблица 0)" if is_ru else "Descriptive Statistics (Table 0)"
        subtitle = (
            f"Числовых переменных: {n_vars}. Значения: медиана (Ме), квартили (Q1, Q3), межквартильный размах (IQR)."
            if is_ru
            else f"{n_vars} numeric variables. Values: median (Me), quartiles (Q1, Q3), interquartile range (IQR)."
        )

        section = f"""
        <div class=\"card\" id=\"global-descriptive\">
            <h2>{title}</h2>
            <p style=\"color: #475569; font-size: 12px; margin-top: -10px;\">{subtitle}</p>
            <table>
                <thead><tr>
                    <th>{'Переменная' if is_ru else 'Variable'}</th>
                    <th>n</th>
                    <th>{'Среднее ± SD' if is_ru else 'Mean ± SD'}</th>
                    <th>{'Медиана' if is_ru else 'Median'}</th>
                    <th>Q1</th><th>Q3</th>
                    <th>IQR</th>
                    <th>min – max</th>
                </tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
        </div>
        """
        self.html_parts.append(section)

    def _add_footer(self):

        is_ru = bool(getattr(self, "is_ru", False))
        self.html_parts.append(f"""
        <div style="margin-top: 50px; color: #888; text-align: center; font-size: 0.8em; border-top: 1px solid #eee; padding-top: 20px;">
            {('Сформировано платформой AI-биостатистики' if is_ru else 'Generated by AI Biostatistics Platform')}
        </div>
        </body></html>
        """)

    def _iter_additional_plot_payloads(self, res: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(res, dict) or not res:
            return []

        def _has_plot_payload(payload: Any) -> bool:
            if not isinstance(payload, dict):
                return False
            plot_hint = payload.get("plot_hint")
            if isinstance(plot_hint, str) and plot_hint.strip():
                return True
            plot_data = payload.get("plot_data")
            if isinstance(plot_data, list) and plot_data:
                return True
            roc = payload.get("roc")
            if isinstance(roc, dict):
                roc_plot = roc.get("plot_data")
                if isinstance(roc_plot, list) and roc_plot:
                    return True
            return False

        def _fingerprint(payload: Dict[str, Any]) -> str:
            try:
                return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            except Exception:
                return str(id(payload))

        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def _add_candidate(payload: Any) -> None:
            if not _has_plot_payload(payload):
                return
            fp = _fingerprint(payload)
            if fp in seen:
                return
            seen.add(fp)
            out.append(payload)

        sub_results = res.get("sub_results")
        if isinstance(sub_results, list):
            for item in sub_results:
                _add_candidate(item)

        for key, value in res.items():
            if key == "sub_results":
                continue
            if isinstance(value, dict) and key.endswith("_result"):
                _add_candidate(value)
            elif isinstance(value, list) and key.endswith("_results"):
                for item in value:
                    _add_candidate(item)

        return out

    def _generate_plot_image(self, res: Dict) -> str:
        """
        Uses matplotlib/seaborn to render the plot stats into a base64 string.
        """
        try:
            png_bytes = _render_plot_png_bytes(res, is_ru=bool(getattr(self, "is_ru", False)))
            if not png_bytes:
                return ""
            return base64.b64encode(png_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"Plotting failed: {e}", exc_info=True)
            return ""
