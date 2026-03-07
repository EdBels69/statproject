"""
reporting_pdf.py — PDF report generation extracted from reporting.py.

Contains generate_pdf_report() and generate_protocol_pdf_report() which create
PDF documents from analysis results.
"""
from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from fpdf import FPDF

from app.modules.analysis_result_v2 import normalize_run_data_results
from app.modules.reporting_contracts import (
    build_report_integrity_context,
    filter_step_pairs_for_report,
)
from app.modules.reporting import (
    _render_plot_png_bytes,
    _dedupe_step_payloads,
    _safe_float,
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
    _build_hypothesis_discovery_context,
    _protocol_validation_provenance_rows,
    _protocol_validation_section_context,
    _bootstrap_trace_lines,
    _is_placeholder_interpretation,
    _extract_step_context_value,
    _build_step_display,
    _generate_fallback_interpretation,
    _step_scope_summary,
    _batch_method_selection_rationale,
    _extract_report_methods,
    _build_report_limitations,
    _method_selection_rationale_ru,
    _normalize_report_density,
    _coerce_alpha,
    _batch_target_label,
    _collect_batch_inferential_rows,
    _build_pairwise_comparison_rows,
    _resolve_dataset_dir_path,
    _build_provenance_file_context,
    _parse_accent_rgb,
    _parse_accent_css,
)

logger = logging.getLogger(__name__)

def generate_pdf_report(results, variables, dataset_id, style: Optional[str] = None, options: Optional[Dict[str, Any]] = None):
    def _safe_text(value: Any, allow_unicode: bool) -> str:
        if value is None:
            return ""
        text = str(value)
        if allow_unicode:
            return text
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def _try_register_unicode_font(pdf: FPDF) -> Optional[str]:
        fonts_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
        regular = fonts_dir / "Arial.ttf"
        bold = fonts_dir / "Arial-Bold.ttf"
        italic = fonts_dir / "Arial-Italic.ttf"
        if not regular.exists():
            return None

        family = "ArialTTF"

        def _add(style_name: str, path: Path) -> None:
            if not path.exists():
                return
            try:
                pdf.add_font(family, style=style_name, fname=str(path))
            except TypeError:
                try:
                    pdf.add_font(family, style_name, str(path))
                except TypeError:
                    pdf.add_font(family, style_name, str(path))

        try:
            _add("", regular)
            _add("B", bold)
            _add("I", italic)
            return family
        except Exception:
            return None

    def _fmt_num(value: Any, digits: int = 3) -> str:
        try:
            if value is None:
                return "-"
            num = float(value)
            if not np.isfinite(num):
                return "-"
            return f"{num:.{digits}f}"
        except Exception:
            return "-"

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

    def _txt(value: Any) -> str:
        return "-" if value is None else str(value)

    def _pdf_bytes(pdf: FPDF) -> bytes:
        try:
            out = pdf.output()
        except TypeError:
            out = pdf.output(dest="S")
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return str(out).encode("latin-1", errors="replace")

    target = variables.get("target") if isinstance(variables, dict) else None
    group = variables.get("group") if isinstance(variables, dict) else None
    feature = variables.get("feature") if isinstance(variables, dict) else None

    style_key = str(style or "apa7").strip().lower()
    is_ru = style_key in {"gost"}
    density = _normalize_report_density((options or {}).get("density"))
    accent_rgb = _parse_accent_rgb((options or {}).get("accent"))
    if not accent_rgb:
        accent_rgb = (17, 17, 17) if style_key in {"gost", "simple", "editorial", "brutal"} else (52, 152, 219)

    method = None
    if isinstance(results, dict):
        method = results.get("method")
    method_name = "Статистический тест" if is_ru else "Statistical Test"
    if isinstance(method, dict):
        method_name = method.get("name") or method.get("id") or method_name
    elif isinstance(method, str):
        method_name = method

    title_size = 16
    body_size = 10
    if density == "compact":
        title_size = 15
        body_size = 9
    elif density == "spacious":
        title_size = 17
        body_size = 11

    font_family = "Helvetica"
    if style_key in {"gost", "apa7", "editorial"}:
        font_family = "Times"
    if style_key == "brutal":
        font_family = "Courier"

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    unicode_family = _try_register_unicode_font(pdf)
    allow_unicode = bool(unicode_family)
    if unicode_family:
        font_family = unicode_family

    # fpdf2 may keep X near the right margin after previous writes.
    # For width=0 multicell calls this can produce "Not enough horizontal space".
    # Wrap instance multicell to normalize X and effective width defensively.
    _orig_multi_cell = pdf.multi_cell

    def _safe_multi_cell(*args, **kwargs):
        local_args = list(args)
        local_kwargs = dict(kwargs)
        try:
            if local_args and isinstance(local_args[0], (int, float)) and float(local_args[0]) <= 0:
                local_args[0] = max(1.0, float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin))
            elif isinstance(local_kwargs.get("w"), (int, float)) and float(local_kwargs.get("w")) <= 0:
                local_kwargs["w"] = max(1.0, float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin))
        except Exception:
            pass
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        return _orig_multi_cell(*local_args, **local_kwargs)

    pdf.multi_cell = _safe_multi_cell

    pdf.set_font(font_family, "B", title_size)
    pdf.set_text_color(*accent_rgb)
    pdf.cell(0, 9, _safe_text("Отчёт по статистическому анализу" if is_ru else "Statistical Analysis Report", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(17, 17, 17)
    pdf.ln(2)

    pdf.set_font(font_family, "", body_size)
    pdf.cell(0, 6, _safe_text(("Набор данных" if is_ru else "Dataset") + f": {dataset_id}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    if target:
        pdf.cell(0, 6, _safe_text(("Показатель" if is_ru else "Target") + f": {target}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    if group:
        pdf.cell(0, 6, _safe_text(("Группа" if is_ru else "Group") + f": {group}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    if feature and not group:
        pdf.cell(0, 6, _safe_text(("Фактор" if is_ru else "Feature") + f": {feature}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if isinstance(results, dict) and results.get("type") in {"batch_analysis", "timepoint_batch_analysis"}:
        alpha_val = _coerce_alpha(
            variables.get("alpha") if isinstance(variables, dict) else None,
            results.get("alpha"),
        )

        group_label = group or results.get("group") or results.get("group_column")
        if group_label and not group:
            pdf.cell(0, 6, _safe_text(("Группа" if is_ru else "Group") + f": {group_label}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        multiplicity = results.get("multiplicity_correction") or (variables.get("multiplicity_correction") if isinstance(variables, dict) else None)
        if multiplicity:
            corr_label = _format_correction_label(multiplicity, is_ru) or str(multiplicity)
            pdf.cell(0, 6, _safe_text(("Поправка" if is_ru else "Correction") + f": {corr_label}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe_text(("Альфа" if is_ru else "Alpha") + f": {_fmt_num(alpha_val, 3)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        def _render_items(items: Any, label: Optional[str] = None) -> None:
            rows_payload = _collect_batch_inferential_rows(items, alpha_val)
            rows = rows_payload.get("rows") if isinstance(rows_payload, dict) else []
            rows = rows if isinstance(rows, list) else []
            sig_count = int(rows_payload.get("sig_count") or 0) if isinstance(rows_payload, dict) else 0

            if label:
                pdf.set_font(font_family, "B", body_size + 1)
                pdf.cell(0, 7, _safe_text(label, allow_unicode), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(font_family, "", body_size)

            pdf.cell(0, 6, _safe_text(("Показателей" if is_ru else "Targets") + f": {len(rows)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, _safe_text(("Значимых" if is_ru else "Significant") + f": {sig_count}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

            pdf.set_font(font_family, "", max(7, body_size - 1))
            for r in rows:
                line = (
                    f"{r.get('target')}: p={_fmt_p(r.get('p_raw'))}; p(adj)={_fmt_p(r.get('p_adj'))}; "
                    + (("sig=yes" if not is_ru else "sig=да") if r.get("sig") else ("sig=no" if not is_ru else "sig=нет"))
                )
                method_s = _method_label_from_id(r.get("method"), is_ru) or str(r.get("method") or "").strip()
                if method_s:
                    line += f"; test={method_s}"
                pdf.multi_cell(0, 4.6, _safe_text(line, allow_unicode))
            pdf.set_font(font_family, "", body_size)
            pdf.ln(2)

        if results.get("type") == "batch_analysis":
            _render_items(results.get("items"), label=("Пакетный анализ" if is_ru else "Batch analysis"))
            return _pdf_bytes(pdf)

        slices = results.get("slices")
        slices = slices if isinstance(slices, dict) else {}
        split_by = results.get("split_by")
        if split_by:
            pdf.cell(0, 6, _safe_text(("Разбиение" if is_ru else "Split by") + f": {split_by}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        for k in sorted(slices.keys(), key=lambda x: str(x)):
            sr = slices.get(k)
            if not isinstance(sr, dict):
                continue
            _render_items(sr.get("items"), label=("Точка" if is_ru else "Slice") + f": {k}")
        return _pdf_bytes(pdf)

    pdf.set_font(font_family, "B", body_size + 2)
    pdf.cell(0, 7, _safe_text("Результаты" if is_ru else "Results", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_family, "", body_size)
    pdf.cell(0, 6, _safe_text(("Метод" if is_ru else "Method") + f": {method_name}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

    if isinstance(results, dict):
        pdf.cell(0, 6, _safe_text(f"p-value: {_fmt_p(results.get('p_value'))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe_text(("Статистика" if is_ru else "Statistic") + f": {_fmt_num(results.get('stat_value'))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        sig = results.get("significant")
        if isinstance(sig, bool):
            pdf.cell(0, 6, _safe_text(("Значимо" if is_ru else "Significant") + f": {('ДА' if sig else 'НЕТ') if is_ru else ('YES' if sig else 'NO')}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        effect_size = results.get("effect_size")
        effect_name = results.get("effect_size_name")
        if effect_size is not None:
            label = effect_name or "effect"
            pdf.cell(0, 6, _safe_text(("Размер эффекта" if is_ru else "Effect size") + f": {label} {_fmt_num(effect_size, 2)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        ci_lo = results.get("effect_size_ci_lower")
        ci_hi = results.get("effect_size_ci_upper")
        if ci_lo is not None and ci_hi is not None:
            pdf.cell(0, 6, _safe_text(("ДИ эффекта" if is_ru else "Effect CI") + f": [{_fmt_num(ci_lo, 2)}, {_fmt_num(ci_hi, 2)}]", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        power = results.get("power")
        if power is not None:
            pdf.cell(0, 6, _safe_text(("Мощность" if is_ru else "Power") + f": {_fmt_num(power, 2)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        bf10 = results.get("bf10")
        if bf10 is not None:
            pdf.cell(0, 6, _safe_text(f"BF10: {bf10}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        interpretation = (results.get("ai_interpretation") or results.get("conclusion")) if is_ru else results.get("conclusion")
        if _is_placeholder_interpretation(interpretation):
            interpretation = _generate_fallback_interpretation(results if isinstance(results, dict) else {}, {}, is_ru)
        if interpretation:
            pdf.ln(2)
            pdf.set_font(font_family, "B", body_size + 2)
            pdf.cell(0, 7, _safe_text("Интерпретация" if is_ru else "Interpretation", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            pdf.multi_cell(0, 5, _safe_text(interpretation, allow_unicode))

    return _pdf_bytes(pdf)


def generate_protocol_pdf_report(run_data: Dict[str, Any], dataset_name: str = "Dataset", style: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> bytes:
    def _safe_text(value: Any, allow_unicode: bool) -> str:
        if value is None:
            return ""
        text = str(value)
        if allow_unicode:
            return text
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def _try_register_unicode_font(pdf: FPDF) -> Optional[str]:
        fonts_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
        regular = fonts_dir / "Arial.ttf"
        bold = fonts_dir / "Arial-Bold.ttf"
        italic = fonts_dir / "Arial-Italic.ttf"
        if not regular.exists():
            return None

        family = "ArialTTF"

        def _add(style_name: str, path: Path) -> None:
            if not path.exists():
                return
            try:
                pdf.add_font(family, style=style_name, fname=str(path))
            except TypeError:
                try:
                    pdf.add_font(family, style_name, str(path))
                except TypeError:
                    pdf.add_font(family, style_name, str(path))

        try:
            _add("", regular)
            _add("B", bold)
            _add("I", italic)
            return family
        except Exception:
            return None

    def _fmt_num(value: Any, digits: int = 3) -> str:
        try:
            if value is None:
                return "-"
            num = float(value)
            if not np.isfinite(num):
                return "-"
            return f"{num:.{digits}f}"
        except Exception:
            return "-"

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

    def _txt(value: Any) -> str:
        return "-" if value is None else str(value)

    def _pdf_bytes(pdf: FPDF) -> bytes:
        try:
            out = pdf.output()
        except TypeError:
            out = pdf.output(dest="S")
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return str(out).encode("latin-1", errors="replace")

    run_data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})

    style_key = str(style or "apa7").strip().lower()
    density = _normalize_report_density((options or {}).get("density"))
    accent_rgb = _parse_accent_rgb((options or {}).get("accent"))
    if not accent_rgb:
        accent_rgb = (17, 17, 17) if style_key in {"gost", "simple", "editorial", "brutal"} else (52, 152, 219)

    is_ru = style_key in {"gost"}

    def _insert_png(pdf: FPDF, png_bytes: bytes) -> None:
        if not png_bytes:
            return
        try:
            import tempfile
            from io import BytesIO
            try:
                from PIL import Image
            except Exception:
                Image = None

            img_w_px = None
            img_h_px = None
            if Image is not None:
                try:
                    with Image.open(BytesIO(png_bytes)) as im:
                        img_w_px, img_h_px = im.size
                except Exception:
                    img_w_px, img_h_px = None, None

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(png_bytes)
            tmp.flush()
            tmp.close()
            try:
                pdf.set_y(pdf.t_margin)
                x = pdf.l_margin
                y = pdf.get_y()
                max_w = float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin)
                max_h = float(pdf.h) - float(pdf.b_margin) - float(y)

                if img_w_px and img_h_px and img_w_px > 0 and img_h_px > 0:
                    ratio = float(img_h_px) / float(img_w_px)
                else:
                    ratio = 0.75

                w = max_w
                h = w * ratio
                if h > max_h and max_h > 0:
                    h = max_h
                    w = h / ratio if ratio > 0 else max_w
                if w <= 0 or h <= 0:
                    return

                pdf.image(tmp.name, x=x, y=y, w=w, h=h)
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception:
            return

    title_size = 16
    body_size = 10
    if density == "compact":
        title_size = 15
        body_size = 9
    elif density == "spacious":
        title_size = 17
        body_size = 11

    font_family = "Helvetica"
    if style_key in {"gost", "apa7", "editorial"}:
        font_family = "Times"
    if style_key == "brutal":
        font_family = "Courier"

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    unicode_family = _try_register_unicode_font(pdf)
    allow_unicode = bool(unicode_family)
    if unicode_family:
        font_family = unicode_family

    # fpdf2 may keep X near the right margin after previous writes.
    # For width=0 multicell calls this can produce "Not enough horizontal space".
    # Wrap instance multicell to normalize X and effective width defensively.
    _orig_multi_cell = pdf.multi_cell

    def _safe_multi_cell(*args, **kwargs):
        local_args = list(args)
        local_kwargs = dict(kwargs)
        try:
            if local_args and isinstance(local_args[0], (int, float)) and float(local_args[0]) <= 0:
                local_args[0] = max(1.0, float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin))
            elif isinstance(local_kwargs.get("w"), (int, float)) and float(local_kwargs.get("w")) <= 0:
                local_kwargs["w"] = max(1.0, float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin))
        except Exception:
            pass
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        return _orig_multi_cell(*local_args, **local_kwargs)

    pdf.multi_cell = _safe_multi_cell

    pdf.set_font(font_family, "B", title_size)
    pdf.set_text_color(*accent_rgb)
    pdf.cell(0, 9, _safe_text("Отчёт по протоколу" if is_ru else "Protocol Analysis Report", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(17, 17, 17)
    pdf.ln(2)
    pdf.set_font(font_family, "", body_size)
    pdf.cell(0, 6, _safe_text(("Набор данных" if is_ru else "Dataset") + f": {dataset_name}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    protocol_name = run_data.get("protocol_name") if isinstance(run_data, dict) else None
    if protocol_name:
        pdf.cell(0, 6, _safe_text(("Протокол" if is_ru else "Protocol") + f": {protocol_name}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if isinstance(run_data, dict) and run_data.get("dataset_id"):
        pdf.set_font(font_family, "", body_size)
        pdf.cell(0, 6, _safe_text(("ID набора" if is_ru else "Dataset ID") + f": {run_data.get('dataset_id')}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    dataset_id = run_data.get("dataset_id") if isinstance(run_data, dict) else None
    run_id = run_data.get("run_id") if isinstance(run_data, dict) else None
    ds_dir = _resolve_dataset_dir_path(dataset_id) if dataset_id else None
    source_meta: Dict[str, Any] = {}
    source_files: List[str] = []
    if ds_dir and os.path.isdir(ds_dir):
        source_dir = os.path.join(ds_dir, "source")
        source_meta_path = os.path.join(source_dir, "meta.json")
        if os.path.exists(source_meta_path):
            try:
                with open(source_meta_path, "r", encoding="utf-8") as f:
                    loaded_meta = json.load(f)
                if isinstance(loaded_meta, dict):
                    source_meta = loaded_meta
            except Exception:
                source_meta = {}
        if os.path.isdir(source_dir):
            try:
                source_files = [
                    str(name)
                    for name in sorted(os.listdir(source_dir))
                    if str(name) not in {"meta.json", ".", ".."} and os.path.isfile(os.path.join(source_dir, str(name)))
                ]
            except Exception:
                source_files = []

    reproducibility = run_data.get("reproducibility") if isinstance(run_data.get("reproducibility"), dict) else {}
    analysis_dataset = run_data.get("analysis_dataset") if isinstance(run_data.get("analysis_dataset"), dict) else {}
    if not analysis_dataset and isinstance(reproducibility.get("analysis_dataset"), dict):
        analysis_dataset = reproducibility.get("analysis_dataset")
    analysis_set = run_data.get("analysis_set") if isinstance(run_data.get("analysis_set"), dict) else {}
    integrity_ctx_pdf = build_report_integrity_context(run_data)
    verification_ctx_pdf = (
        integrity_ctx_pdf.get("verification")
        if isinstance(integrity_ctx_pdf.get("verification"), dict)
        else {}
    )
    verification_status_pdf = str(verification_ctx_pdf.get("status") or "missing").strip().lower()
    if verification_status_pdf in {"passed", "ok"}:
        verification_label_pdf = "пройдено" if is_ru else "passed"
    elif verification_status_pdf in {"failed", "error", "blocked"}:
        verification_label_pdf = "ошибка" if is_ru else "failed"
    else:
        verification_label_pdf = "отсутствует" if is_ru else "missing"
    failed_steps_pdf = verification_ctx_pdf.get("failed_steps")
    excluded_steps_pdf = (
        len([str(x) for x in failed_steps_pdf if isinstance(x, str) and str(x).strip()])
        if isinstance(failed_steps_pdf, list)
        else 0
    )

    pdf.set_font(font_family, "B", body_size + 2)
    pdf.cell(0, 7, _safe_text("Воспроизводимость и provenance" if is_ru else "Reproducibility and provenance", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_family, "", body_size)
    source_name = source_meta.get("original_filename") or source_meta.get("filename")
    source_rel = "-"
    if dataset_id and source_files:
        source_rel = os.path.join("workspace", "datasets", str(dataset_id), "source", source_files[0])
    elif source_name:
        source_rel = str(source_name)
    provenance_lines = [
        (("Run ID" if not is_ru else "Run ID") + f": {_txt(run_id)}"),
        (("Source file" if not is_ru else "Исходный файл") + f": {_txt(source_name)}"),
        (("Source path" if not is_ru else "Путь источника") + f": {_txt(source_rel)}"),
        (
            ("Import settings" if not is_ru else "Параметры импорта")
            + f": sheet={_txt(source_meta.get('sheet_name'))}; header_row={_txt(source_meta.get('header_row'))}"
        ),
        (
            ("Analysis dataset" if not is_ru else "Рабочая выборка")
            + f": rows={_txt(analysis_dataset.get('rows'))}, cols={_txt(analysis_dataset.get('columns'))}, "
            + f"xlsx={_txt(analysis_dataset.get('xlsx'))}, parquet={_txt(analysis_dataset.get('parquet'))}"
        ),
        (
            ("Frozen analysis set" if not is_ru else "Замороженная выборка")
            + f": id={_txt(analysis_set.get('analysis_set_id'))}; n_selected={_txt(analysis_set.get('n_selected'))}; "
            + f"mode={_txt(analysis_set.get('mode'))}; enforce={_txt(analysis_set.get('enforce'))}"
        ),
        (
            ("Reproducibility" if not is_ru else "Воспроизводимость")
            + f": ready={_txt(reproducibility.get('ready'))}; script={_txt(reproducibility.get('script'))}; "
            + f"payload={_txt(reproducibility.get('payload'))}; manifest={_txt(reproducibility.get('manifest'))}"
        ),
        (
            ("Bootstrap trace artifact" if not is_ru else "Артефакт bootstrap-трассировки")
            + f": {_txt(reproducibility.get('bootstrap_trace'))}"
        ),
        (
            ("Hypothesis discovery artifact" if not is_ru else "Артефакт гипотез")
            + f": {_txt(reproducibility.get('hypothesis_discovery'))}"
        ),
        (
            ("Verification status" if not is_ru else "Статус верификации")
            + f": {_txt(verification_label_pdf)}"
        ),
        (
            ("Steps excluded from report" if not is_ru else "Исключено шагов в отчёте")
            + f": {_txt(excluded_steps_pdf)}"
        ),
    ]
    validation_rows_pdf = _protocol_validation_provenance_rows(
        run_data if isinstance(run_data, dict) else {},
        is_ru=is_ru,
        dataset_id=dataset_id,
        run_id=run_id,
    )
    for key, value in validation_rows_pdf:
        provenance_lines.append(f"{_txt(key)}: {_txt(value)}")
    if dataset_id and run_id:
        provenance_lines.append(
            (("Artifacts path" if not is_ru else "Путь артефактов") + ": " + os.path.join("workspace", "datasets", str(dataset_id), "analysis", str(run_id), "artifacts"))
        )
    for line in provenance_lines:
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        pdf.multi_cell(0, 5, _safe_text(line, allow_unicode))
    pdf.ln(2)

    protocol_validation_ctx_pdf = _protocol_validation_section_context(
        run_data if isinstance(run_data, dict) else {},
        is_ru=is_ru,
    )
    if protocol_validation_ctx_pdf.get("present"):
        pdf.set_font(font_family, "B", body_size + 2)
        pdf.cell(
            0,
            7,
            _safe_text("Валидация протокола" if is_ru else "Protocol Validation", allow_unicode),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_font(font_family, "", body_size)
        for key, value in (protocol_validation_ctx_pdf.get("summary_rows") or []):
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(f"{_txt(key)}: {_txt(value)}", allow_unicode))

        global_errors_pdf = protocol_validation_ctx_pdf.get("global_errors")
        if isinstance(global_errors_pdf, list) and global_errors_pdf:
            pdf.multi_cell(
                0,
                5,
                _safe_text(
                    "Глобальные ошибки валидации:" if is_ru else "Global validation errors:",
                    allow_unicode,
                ),
            )
            for msg in global_errors_pdf:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text("• " + _txt(msg), allow_unicode))

        issues_pdf = protocol_validation_ctx_pdf.get("issues")
        if isinstance(issues_pdf, list) and issues_pdf:
            pdf.multi_cell(
                0,
                5,
                _safe_text("Проблемные шаги:" if is_ru else "Validation findings by step:", allow_unicode),
            )
            for row in issues_pdf:
                if not isinstance(row, dict):
                    continue
                line = (
                    f"{_txt(row.get('step_id'))} | "
                    f"{_txt(row.get('method'))} | "
                    f"{_txt(row.get('status'))} | "
                    f"{_txt(row.get('issues'))}"
                )
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text("• " + line, allow_unicode))
        else:
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(
                0,
                5,
                _safe_text(
                    "Критичных замечаний по шагам не найдено."
                    if is_ru
                    else "No critical step findings were detected.",
                    allow_unicode,
                ),
            )
        pdf.ln(2)

    methods_summary = _extract_report_methods(run_data if isinstance(run_data, dict) else {}, is_ru=is_ru)
    method_rows = methods_summary.get("rows") if isinstance(methods_summary.get("rows"), list) else []
    missing_method_steps = methods_summary.get("missing_inferential_steps") if isinstance(methods_summary.get("missing_inferential_steps"), list) else []

    pdf.set_font(font_family, "B", body_size + 2)
    pdf.cell(0, 7, _safe_text("Методы" if is_ru else "Methods", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_family, "", body_size)
    if method_rows:
        for row in method_rows:
            steps_s = ", ".join([str(x) for x in (row.get("steps") or [])[:8]]) or "-"
            targets_s = ", ".join([str(x) for x in (row.get("targets") or [])[:8]]) or "-"
            line = (
                f"{row.get('method')}: n_steps={row.get('count')}; "
                f"{('шаги' if is_ru else 'steps')}={steps_s}; "
                f"{('показатели' if is_ru else 'targets')}={targets_s}"
            )
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(line, allow_unicode))
    else:
        pdf.multi_cell(
            0,
            5,
            _safe_text(
                "Методы не определены: в результатах нет исполнимых аналитических шагов."
                if is_ru
                else "Methods are unavailable: no analyzable execution steps were found.",
                allow_unicode,
            ),
        )

    if missing_method_steps:
        preview = ", ".join([str(x) for x in missing_method_steps[:6]])
        if len(missing_method_steps) > 6:
            preview += ", ..."
        pdf.multi_cell(
            0,
            5,
            _safe_text(
                (f"Предупреждение: отсутствует metadata метода для шагов: {preview}" if is_ru else f"Warning: method metadata is missing for steps: {preview}"),
                allow_unicode,
            ),
        )

    hypothesis_ctx_pdf = _build_hypothesis_discovery_context(
        run_data if isinstance(run_data, dict) else {},
        is_ru=is_ru,
    )
    if hypothesis_ctx_pdf.get("present"):
        hyp_rows_pdf = hypothesis_ctx_pdf.get("rows") if isinstance(hypothesis_ctx_pdf.get("rows"), list) else []
        pdf.ln(2)
        pdf.set_font(font_family, "B", body_size + 2)
        pdf.cell(
            0,
            7,
            _safe_text("Гипотезы и их трассировка" if is_ru else "Hypothesis discovery and traceability", allow_unicode),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_font(font_family, "", body_size)
        pdf.multi_cell(
            0,
            5,
            _safe_text(
                (
                    ("Режим" if is_ru else "Mode")
                    + f": {_txt(hypothesis_ctx_pdf.get('analysis_mode'))}; "
                    + ("Дизайн" if is_ru else "Design")
                    + f": {_txt(hypothesis_ctx_pdf.get('design_type'))}; "
                    + ("Всего" if is_ru else "Total")
                    + f": {_txt(hypothesis_ctx_pdf.get('count'))}; "
                    + ("Покрыто шагами" if is_ru else "Covered by steps")
                    + f": {_txt(hypothesis_ctx_pdf.get('covered'))}"
                ),
                allow_unicode,
            ),
        )
        pdf.multi_cell(
            0,
            5,
            _safe_text(
                (
                    ("Подтверждено" if is_ru else "Supported")
                    + f": {_txt(hypothesis_ctx_pdf.get('supported'))}; "
                    + ("Не подтверждено" if is_ru else "Not supported")
                    + f": {_txt(hypothesis_ctx_pdf.get('not_supported'))}; "
                    + ("Не оценено" if is_ru else "Not evaluated")
                    + f": {_txt(hypothesis_ctx_pdf.get('not_evaluated'))}"
                ),
                allow_unicode,
            ),
        )
        pdf.set_font(font_family, "", max(7, body_size - 1))
        for row in hyp_rows_pdf[:8]:
            if not isinstance(row, dict):
                continue
            matched_steps = ", ".join([_txt(v) for v in (row.get("matched_steps") or [])]) or "-"
            pdf.multi_cell(0, 4.8, _safe_text("• " + _txt(row.get("title")), allow_unicode))
            pdf.multi_cell(0, 4.8, _safe_text("  H0: " + _txt(row.get("h0")), allow_unicode))
            pdf.multi_cell(0, 4.8, _safe_text("  H1: " + _txt(row.get("h1")), allow_unicode))
            pdf.multi_cell(
                0,
                4.8,
                _safe_text(
                    ("  Метод: " if is_ru else "  Method: ")
                    + _txt(row.get("suggested_method"))
                    + ("; шаги: " if is_ru else "; steps: ")
                    + matched_steps,
                    allow_unicode,
                ),
            )
            pdf.multi_cell(
                0,
                4.8,
                _safe_text(
                    ("  Вердикт: " if is_ru else "  Verdict: ")
                    + _txt(row.get("verdict_label"))
                    + ("; доказательства: " if is_ru else "; evidence: ")
                    + _txt(row.get("evidence")),
                    allow_unicode,
                ),
            )
    pdf.ln(2)

    pdf.set_font(font_family, "B", body_size + 2)
    pdf.cell(0, 7, _safe_text("Результаты" if is_ru else "Results", allow_unicode), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_family, "", body_size)

    try:
        from app.core.pipeline import PipelineManager

        result_ir = PipelineManager.build_result_ir(run_data)
    except Exception:
        result_ir = {}

    blocks = result_ir.get("blocks") if isinstance(result_ir, dict) else None
    if not isinstance(blocks, list):
        blocks = []

    results = run_data.get("results", {}) if isinstance(run_data, dict) else {}
    step_meta_map = run_data.get("step_meta") if isinstance(run_data, dict) else None
    if not isinstance(step_meta_map, dict):
        step_meta_map = {}
    protocol_goal = run_data.get("protocol_goal") if isinstance(run_data, dict) else None

    import re

    def _extract_visit(step_id: str, meta: Dict[str, Any], res: Dict[str, Any]) -> Optional[str]:
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

    def _extract_groups(res: Dict[str, Any]) -> List[str]:
        plot_stats = res.get("plot_stats")
        if isinstance(plot_stats, dict) and plot_stats:
            return [str(k) for k in plot_stats.keys()]
        groups = res.get("groups")
        if isinstance(groups, list) and groups:
            return [str(g) for g in groups]
        if isinstance(groups, dict) and groups:
            return [str(k) for k in groups.keys()]
        return []

    def _format_goal(goal: str) -> str:
        g = str(goal or "").strip()
        if not g:
            return ""
        if not is_ru:
            return g
        m = {
            "compare_groups": "Сравнение групп",
            "descriptive": "Описательная статистика",
            "correlation": "Корреляционный анализ",
            "regression": "Регрессионный анализ",
            "survival": "Анализ выживаемости",
            "longitudinal": "Динамика по визитам",
        }
        ru = m.get(g)
        return f"{ru} ({g})" if ru else g

    def _extract_task(meta: Dict[str, Any]) -> Optional[str]:
        for k in ["task", "analysis_task", "section", "domain", "objective", "goal"]:
            v = meta.get(k) if isinstance(meta, dict) else None
            if isinstance(v, str) and v.strip():
                return v.strip()
        if isinstance(protocol_goal, str) and protocol_goal.strip():
            formatted = _format_goal(protocol_goal)
            return formatted if formatted else protocol_goal.strip()
        return None

    def iter_steps():
        if blocks:
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                step_id = block.get("id")
                payload = block.get("payload")
                if isinstance(step_id, str) and isinstance(payload, dict):
                    yield step_id, payload
            return
        if isinstance(results, dict):
            for step_id, res in (results or {}).items():
                if isinstance(step_id, str) and isinstance(res, dict):
                    yield step_id, res

    raw_steps = list(iter_steps())
    integrity_ctx = build_report_integrity_context(run_data)
    filtered_steps, filter_meta = filter_step_pairs_for_report(raw_steps, integrity_ctx)

    new_page_before_step = False
    for step_id, res in filtered_steps:
        if new_page_before_step:
            pdf.add_page()
            new_page_before_step = False
        pdf.set_font(font_family, "B", body_size + 2)
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        step_meta = step_meta_map.get(step_id) if isinstance(step_id, str) else None
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        step_title = _build_step_display(step_id, res if isinstance(res, dict) else {}, step_meta, is_ru)
        pdf.multi_cell(0, 6, _safe_text(("Шаг" if is_ru else "Step") + f": {step_title}", allow_unicode))
        pdf.set_font(font_family, "", max(7, body_size - 1))
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        pdf.multi_cell(0, 4.5, _safe_text(f"ID: {step_id}", allow_unicode))
        pdf.set_font(font_family, "", body_size)
        task = _extract_task(step_meta)
        visit = _extract_visit(step_id, step_meta, res if isinstance(res, dict) else {})
        group_levels = _extract_groups(res if isinstance(res, dict) else {})

        if task:
            pdf.set_font(font_family, "", body_size)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Задача" if is_ru else "Task") + f": {task}", allow_unicode))
        if visit:
            pdf.set_font(font_family, "", body_size)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Точка" if is_ru else "Timepoint") + f": {visit}", allow_unicode))
        if group_levels:
            if len(group_levels) == 2:
                grp_s = f"{group_levels[0]} vs {group_levels[1]}"
            else:
                grp_s = ", ".join(group_levels)
            pdf.set_font(font_family, "", body_size)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Сравниваемые группы" if is_ru else "Compared groups") + f": {grp_s}", allow_unicode))

        if not isinstance(res, dict):
            pdf.set_font(font_family, "", body_size)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text("Нет структурированного результата" if is_ru else "No structured result", allow_unicode))
            pdf.ln(2)
            continue

        pdf.set_font(font_family, "", body_size)
        step_type = res.get("type")
        if step_type:
            pdf.cell(0, 6, _safe_text(("Тип" if is_ru else "Type") + f": {step_type}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        method = res.get("method")
        method_name = "Статистический тест" if is_ru else "Statistical Test"
        if isinstance(method, dict):
            method_name = _method_label_from_id(method.get("id") or method.get("name"), is_ru) or method.get("name") or method.get("id") or method_name
        elif isinstance(method, str):
            method_name = _method_label_from_id(method, is_ru) or method
        pdf.cell(0, 6, _safe_text(("Метод" if is_ru else "Method") + f": {method_name}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        if step_type in {"batch_analysis", "timepoint_batch_analysis"}:
            alpha_val = _coerce_alpha(
                res.get("alpha"),
                run_data.get("alpha") if isinstance(run_data, dict) else None,
            )

            group_col = res.get("group") or res.get("group_column")
            if group_col:
                pdf.cell(0, 6, _safe_text(("Группировка" if is_ru else "Group") + f": {group_col}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, _safe_text(("Альфа" if is_ru else "Alpha") + f": {_fmt_num(alpha_val, 3)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            corr = res.get("multiplicity_correction")
            if corr:
                corr_label = _format_correction_label(corr, is_ru) or str(corr)
                pdf.cell(0, 6, _safe_text(("Поправка" if is_ru else "Correction") + f": {corr_label}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

            def _render_items(items: Any, label: Optional[str] = None) -> None:
                rows_payload = _collect_batch_inferential_rows(items, alpha_val)
                rows = rows_payload.get("rows") if isinstance(rows_payload, dict) else []
                rows = rows if isinstance(rows, list) else []
                sig_count = int(rows_payload.get("sig_count") or 0) if isinstance(rows_payload, dict) else 0

                if label:
                    pdf.ln(1)
                    pdf.set_font(font_family, "B", body_size + 1)
                    pdf.cell(0, 6, _safe_text(label, allow_unicode), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(font_family, "", body_size)

                pdf.cell(0, 6, _safe_text(("Показателей" if is_ru else "Targets") + f": {len(rows)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, _safe_text(("Значимых" if is_ru else "Significant") + f": {sig_count}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
                pdf.set_font(font_family, "", max(7, body_size - 1))
                for r in rows:
                    line = (
                        f"{r.get('target')}: p={_fmt_p(r.get('p_raw'))}; p(adj)={_fmt_p(r.get('p_adj'))}; "
                        + (("sig=yes" if not is_ru else "sig=да") if r.get("sig") else ("sig=no" if not is_ru else "sig=нет"))
                    )
                    method_s = _method_label_from_id(r.get("method"), is_ru) or str(r.get("method") or "").strip()
                    if method_s:
                        line += f"; test={method_s}"
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 4.3, _safe_text(line, allow_unicode))
                pdf.set_font(font_family, "", body_size)

            if step_type == "batch_analysis":
                _render_items(res.get("items"), label=("Пакетный анализ" if is_ru else "Batch analysis"))
                pdf.ln(3)
                new_page_before_step = True
                continue

            split_by = res.get("split_by")
            if split_by:
                pdf.cell(0, 6, _safe_text(("Разбиение" if is_ru else "Split by") + f": {split_by}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            slices = res.get("slices")
            slices = slices if isinstance(slices, dict) else {}
            for k in sorted(slices.keys(), key=lambda x: str(x)):
                sr = slices.get(k)
                if not isinstance(sr, dict):
                    continue
                _render_items(sr.get("items"), label=("Точка" if is_ru else "Slice") + f": {k}")
            pdf.ln(3)
            new_page_before_step = True
            continue

        if step_type and step_type not in {"table_1", "compare", "hypothesis_test", "correlation", "regression", "survival", "mixed_effects", "clustered_correlation", "batch_compare_by_factor", "responders", "batch_analysis", "timepoint_batch_analysis", "delta_batch_analysis", "agreement", "assumption_test", "time_series"}:
            err = res.get("error")
            if isinstance(err, str) and err.strip():
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(("Ошибка" if is_ru else "Error") + f": {err}", allow_unicode))
            try:
                raw = json.dumps(res, ensure_ascii=False, indent=2, default=str)
            except Exception:
                raw = str(res)
            raw = raw[:6000]
            pdf.set_font(font_family, "", max(7, body_size - 1))
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 4.3, _safe_text(raw, allow_unicode))
            pdf.set_font(font_family, "", body_size)
            pdf.ln(2)
            continue

        if step_type == "responders":
            outcome = res.get("outcome")
            baseline = res.get("baseline")
            baseline_time = baseline.get("time") if isinstance(baseline, dict) else None
            threshold = res.get("threshold")
            direction = res.get("direction")
            if outcome:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(("Показатель" if is_ru else "Outcome") + f": {outcome}", allow_unicode))
            meta = []
            if baseline_time is not None:
                meta.append(("база" if is_ru else "baseline") + f"={baseline_time}")
            if threshold is not None:
                meta.append(("порог" if is_ru else "threshold") + f"={threshold}")
            if direction:
                meta.append(("направление" if is_ru else "direction") + f"={direction}")
            if meta:
                pdf.cell(0, 6, _safe_text(" • ".join(meta), allow_unicode), new_x="LMARGIN", new_y="NEXT")

            by_visit = res.get("by_visit")
            if isinstance(by_visit, dict) and by_visit:
                def _sort_key(v: Any) -> Any:
                    try:
                        return float(v)
                    except Exception:
                        return str(v)

                for vk in sorted(by_visit.keys(), key=_sort_key):
                    v = by_visit.get(vk)
                    if not isinstance(v, dict):
                        continue
                    groups = v.get("groups")
                    if not isinstance(groups, dict) or not groups:
                        continue

                    test = v.get("test")
                    test_method = test.get("method") if isinstance(test, dict) else None
                    test_p = test.get("p_value") if isinstance(test, dict) else None
                    pdf.ln(1)
                    pdf.set_font(font_family, "B", body_size + 1)
                    pdf.cell(0, 6, _safe_text(("Визит" if is_ru else "Visit") + f" {vk}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(font_family, "", body_size)
                    pdf.cell(0, 6, _safe_text(("Тест" if is_ru else "Test") + f": {test_method or 'chi_square'}, p={_fmt_p(test_p)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

                    for g in sorted(groups.keys(), key=_sort_key):
                        st = groups.get(g)
                        if not isinstance(st, dict):
                            continue
                        total = st.get("total")
                        responders = st.get("responders")
                        rate = st.get("rate")
                        try:
                            rate_s = f"{float(rate) * 100.0:.1f}%" if rate is not None and np.isfinite(float(rate)) else "-"
                        except Exception:
                            rate_s = "-"
                        try:
                            pdf.set_x(pdf.l_margin)
                        except Exception:
                            pass
                        prefix = "Группа" if is_ru else "G"
                        pdf.multi_cell(0, 5, _safe_text(f"{prefix}={g}: {responders}/{total} ({rate_s})", allow_unicode))

            pdf.ln(3)
            continue

        p_key = "p_value" if "p_value" in res else ("interaction_p_value" if "interaction_p_value" in res else None)
        if p_key:
            label = "p-value" if p_key == "p_value" else ("p (Time×Group)" if not is_ru else "p (Визит×Группа)")
            pdf.cell(0, 6, _safe_text(f"{label}: {_fmt_p(res.get(p_key))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        if "stat_value" in res or "stats" in res:
            pdf.cell(0, 6, _safe_text(("Статистика" if is_ru else "Statistic") + f": {_fmt_num(res.get('stat_value', res.get('stats')))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        if step_type == "time_series":
            trend = res.get("trend") if isinstance(res.get("trend"), dict) else {}
            diagnostics = res.get("diagnostics") if isinstance(res.get("diagnostics"), dict) else {}
            ljung = diagnostics.get("ljung_box") if isinstance(diagnostics.get("ljung_box"), dict) else {}
            forecast = res.get("forecast") if isinstance(res.get("forecast"), dict) else {}
            forecast_n = len(forecast.get("points") or []) if isinstance(forecast.get("points"), list) else 0
            time_quality = res.get("time_quality") if isinstance(res.get("time_quality"), dict) else {}
            if not time_quality and isinstance(diagnostics.get("time_quality"), dict):
                time_quality = diagnostics.get("time_quality")

            axis_kind_raw = str(res.get("time_axis_kind") or time_quality.get("time_axis_kind") or "").strip().lower()
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
            try:
                parse_ratio = float(time_quality.get("datetime_parse_ratio"))
                if np.isfinite(parse_ratio):
                    parse_ratio_txt = f"{parse_ratio * 100.0:.1f}%"
            except Exception:
                parse_ratio_txt = "-"

            year_range_txt = "-"
            try:
                min_year = int(time_quality.get("min_year"))
                max_year = int(time_quality.get("max_year"))
                year_range_txt = f"{min_year}-{max_year}"
            except Exception:
                year_range_txt = "-"

            flags_raw = time_quality.get("flags")
            if isinstance(flags_raw, list):
                flags = [str(v).strip() for v in flags_raw if str(v).strip()]
            else:
                flags = []
            flags_txt = ", ".join(flags) if flags else "-"
            inferred_freq = str(time_quality.get("inferred_frequency") or "").strip() or "-"

            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(
                0,
                6,
                _safe_text("Диагностика временного ряда" if is_ru else "Series diagnostics", allow_unicode),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_font(font_family, "", body_size)

            for line in [
                (("Тип временной оси" if is_ru else "Time axis type"), axis_kind_label),
                (("Качество временной оси" if is_ru else "Time axis quality"), quality_label),
                (("Парсинг datetime" if is_ru else "Datetime parse ratio"), parse_ratio_txt),
                (("Диапазон лет" if is_ru else "Year range"), year_range_txt),
                (("Интервал (infer)" if is_ru else "Inferred frequency"), inferred_freq),
                (("Флаги качества" if is_ru else "Quality flags"), flags_txt),
                (("Ljung-Box (p)" if is_ru else "Ljung-Box (p)"), _fmt_p(ljung.get("p_value"))),
                (("Белый шум" if is_ru else "White-noise-like"), ("да" if is_ru else "yes") if isinstance(ljung.get("white_noise_like"), bool) and bool(ljung.get("white_noise_like")) else (("нет" if is_ru else "no") if isinstance(ljung.get("white_noise_like"), bool) else "-")),
                (("Прогноз (точек)" if is_ru else "Forecast (points)"), str(forecast_n) if forecast_n > 0 else "-"),
                (("Тренд (наклон)" if is_ru else "Trend (slope)"), _fmt_num(trend.get("slope"), 4)),
            ]:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"{line[0]}: {line[1]}", allow_unicode))

            warning_items = res.get("warnings")
            warning_lines = []
            if isinstance(warning_items, list):
                for item in warning_items:
                    txt = str(item).strip()
                    if txt:
                        warning_lines.append(txt)
            if warning_lines:
                pdf.ln(1)
                pdf.set_font(font_family, "B", body_size + 1)
                pdf.cell(
                    0,
                    6,
                    _safe_text("Предупреждения по хронологии" if is_ru else "Chronology warnings", allow_unicode),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.set_font(font_family, "", body_size)
                for msg in warning_lines[:6]:
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 5, _safe_text(f"• {msg}", allow_unicode))

        if step_type == "mixed_effects":
            if res.get("n_subjects") is not None:
                pdf.cell(0, 6, _safe_text(("Субъектов" if is_ru else "Subjects") + f": {_fmt_num(res.get('n_subjects'), 0)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            if res.get("n_observations") is not None:
                pdf.cell(0, 6, _safe_text(("Наблюдений" if is_ru else "Observations") + f": {_fmt_num(res.get('n_observations'), 0)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            if res.get("formula"):
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(("Формула" if is_ru else "Formula") + f": {res.get('formula')}", allow_unicode))

            em = res.get("estimated_means")
            if isinstance(em, dict) and em:
                pdf.ln(1)
                pdf.set_font(font_family, "B", body_size + 1)
                pdf.cell(0, 6, _safe_text(("Оценённые средние" if is_ru else "Estimated Means"), allow_unicode), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(font_family, "", body_size)
                shown = 0
                for g, times in em.items():
                    if not isinstance(times, dict):
                        continue
                    for t, stats in times.items():
                        if not isinstance(stats, dict):
                            continue
                        est = _fmt_num(stats.get("estimate"), 2)
                        lo = _fmt_num(stats.get("ci_lower"), 2)
                        hi = _fmt_num(stats.get("ci_upper"), 2)
                        n = stats.get("n")
                        try:
                            pdf.set_x(pdf.l_margin)
                        except Exception:
                            pass
                        label_g = "Группа" if is_ru else "G"
                        label_t = "Время" if is_ru else "T"
                        pdf.multi_cell(0, 5, _safe_text(f"{label_g}={g}, {label_t}={t}: {est} [{lo}, {hi}] n={n}", allow_unicode))
                        shown += 1
                        if shown >= 18:
                            break
                    if shown >= 18:
                        break

        if step_type == "regression":
            if res.get("r_squared") is not None:
                pdf.cell(0, 6, _safe_text(f"R²: {_fmt_num(res.get('r_squared'), 3)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            if res.get("pseudo_r2") is not None:
                pdf.cell(0, 6, _safe_text(f"Pseudo R²: {_fmt_num(res.get('pseudo_r2'), 3)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            if res.get("aic") is not None:
                pdf.cell(0, 6, _safe_text(f"AIC: {_fmt_num(res.get('aic'), 2)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            coefs = res.get("coefficients")
            if isinstance(coefs, list) and coefs:
                sig = [c for c in coefs if isinstance(c, dict) and isinstance(c.get("p_value"), (int, float)) and float(c.get("p_value")) < 0.05]
                best = sig[:10] if sig else coefs[:8]
                if best:
                    pdf.ln(1)
                    pdf.set_font(font_family, "B", body_size + 1)
                    pdf.cell(0, 6, _safe_text(("Коэффициенты" if is_ru else "Coefficients"), allow_unicode), new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(font_family, "", body_size)
                    for c in best:
                        var = c.get("variable")
                        b = _fmt_num(c.get("coefficient"), 3)
                        p = _fmt_p(c.get("p_value"))
                        try:
                            pdf.set_x(pdf.l_margin)
                        except Exception:
                            pass
                        pdf.multi_cell(0, 5, _safe_text(f"{var}: b={b}, p={p}", allow_unicode))

        bootstrap_lines_pdf = _bootstrap_trace_lines(res.get("bootstrap"), is_ru=is_ru)
        if bootstrap_lines_pdf:
            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(
                0,
                6,
                _safe_text("Bootstrap-трассировка" if is_ru else "Bootstrap trace", allow_unicode),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_font(font_family, "", body_size)
            for line in bootstrap_lines_pdf:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"• {line}", allow_unicode))

        effect_size = res.get("effect_size")
        if effect_size is not None:
            label = res.get("effect_size_name") or "effect"
            pdf.cell(0, 6, _safe_text(("Эффект" if is_ru else "Effect size") + f": {label} {_fmt_num(effect_size, 2)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        ci_lo = res.get("effect_size_ci_lower")
        ci_hi = res.get("effect_size_ci_upper")
        if ci_lo is not None and ci_hi is not None:
            pdf.cell(0, 6, _safe_text(("ДИ эффекта" if is_ru else "Effect CI") + f": [{_fmt_num(ci_lo, 2)}, {_fmt_num(ci_hi, 2)}]", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        if res.get("power") is not None:
            pdf.cell(0, 6, _safe_text(("Мощность" if is_ru else "Power") + f": {_fmt_num(res.get('power'), 2)}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        if res.get("bf10") is not None:
            pdf.cell(0, 6, _safe_text(f"BF10: {res.get('bf10')}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

        if is_ru:
            rationale_ru = _method_selection_rationale_ru(res)
            if isinstance(rationale_ru, str) and rationale_ru.strip():
                pdf.ln(1)
                pdf.set_font(font_family, "", body_size)
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text("Обоснование выбора теста: " + rationale_ru, allow_unicode))

            bf10_text = _interpret_bf10_ru(res.get("bf10"))
            if isinstance(bf10_text, str) and bf10_text.strip():
                pdf.ln(1)
                pdf.set_font(font_family, "", body_size)
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text("Интерпретация BF10: " + bf10_text, allow_unicode))

        compare_rows = _build_pairwise_comparison_rows(res)
        if compare_rows:
            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(0, 6, _safe_text("Сравнение групп (сводная таблица)" if is_ru else "Group Comparison (Summary)", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)

            is_median = compare_rows[0].get("center_label") == "median"
            a_hdr = "Me [Q1; Q3]" if is_median else "M ± SD"

            def _fmt(v: Any, d: int = 2) -> str:
                try:
                    if v is None:
                        return "-"
                    f = float(v)
                    return f"{f:.{d}f}" if np.isfinite(f) else "-"
                except Exception:
                    return "-"

            shown = 0
            for r in compare_rows:
                a = str(r.get("a") or "-")
                b = str(r.get("b") or "-")
                if is_median:
                    q1a, q3a = r.get("a_spread") if isinstance(r.get("a_spread"), tuple) else (None, None)
                    q1b, q3b = r.get("b_spread") if isinstance(r.get("b_spread"), tuple) else (None, None)
                    a_s = f"{_fmt(r.get('a_center'))} [{_fmt(q1a)}; {_fmt(q3a)}]"
                    b_s = f"{_fmt(r.get('b_center'))} [{_fmt(q1b)}; {_fmt(q3b)}]"
                else:
                    a_s = f"{_fmt(r.get('a_center'))} ± {_fmt(r.get('a_spread'))}"
                    b_s = f"{_fmt(r.get('b_center'))} ± {_fmt(r.get('b_spread'))}"

                diff_s = _fmt(r.get("diff"), 2)
                diff_pct = r.get("diff_pct")
                diff_pct_s = (f"{_fmt(diff_pct, 1)}%" if diff_pct is not None else "-")
                p_s = _fmt_p(r.get("p_value"))
                bf10_s = _fmt(r.get("bf10"), 3)
                eff = r.get("effect_size")
                eff_name = r.get("effect_size_name")
                eff_s = (f"{str(eff_name or 'effect')}={_fmt(eff, 2)}" if eff is not None else "-")

                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                line = (
                    f"{a} vs {b}: {a_hdr} A={a_s}; {a_hdr} B={b_s}; Δ={diff_s}; Δ%={diff_pct_s}; p={p_s}; BF10={bf10_s}; {eff_s}"
                )
                pdf.multi_cell(0, 5, _safe_text(line, allow_unicode))
                shown += 1
                if shown >= 18:
                    break
        else:
            group_levels = _extract_groups(res if isinstance(res, dict) else {})
            if group_levels and len(group_levels) >= 3:
                pdf.ln(1)
                pdf.set_font(font_family, "", body_size)
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(
                    0,
                    5,
                    _safe_text(
                        "Есть 3+ группы: попарные сравнения (post-hoc) не выполнены или отсутствуют в результате."
                        if is_ru
                        else "3+ groups: pairwise post-hoc comparisons are not available for this step.",
                        allow_unicode,
                    ),
                )

        interpretation = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else res.get("conclusion")
        if _is_placeholder_interpretation(interpretation):
            interpretation = _generate_fallback_interpretation(res if isinstance(res, dict) else {}, step_meta, is_ru)
        plot_png = _render_plot_png_bytes(res, is_ru=is_ru)

        if plot_png:
            pdf.ln(1)
            pdf.set_font(font_family, "", body_size)
            pdf.cell(0, 6, _safe_text(("График" if is_ru else "Plot") + (": на следующей странице" if is_ru else ": next page"), allow_unicode), new_x="LMARGIN", new_y="NEXT")

        if interpretation:
            pdf.ln(1)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Conclusion") + f": {interpretation}", allow_unicode))

        if plot_png:
            pdf.ln(3)
            pdf.add_page()
            _insert_png(pdf, plot_png)
            new_page_before_step = True
        else:
            pdf.ln(3)

    summary = _extract_protocol_findings(run_data if isinstance(run_data, dict) else {})
    text = _build_discussion_conclusion(summary, is_ru=is_ru)
    discussion = text.get("discussion") if isinstance(text.get("discussion"), list) else []
    conclusion = text.get("conclusion") if isinstance(text.get("conclusion"), list) else []

    if discussion or conclusion:
        pdf.add_page()
        if discussion:
            pdf.set_font(font_family, "B", body_size + 2)
            pdf.cell(0, 7, _safe_text("Обсуждение" if is_ru else "Discussion", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            for line in discussion:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(str(line), allow_unicode))
            pdf.ln(1)

        if conclusion:
            pdf.set_font(font_family, "B", body_size + 2)
            pdf.cell(0, 7, _safe_text("Выводы" if is_ru else "Conclusions", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            for line in conclusion:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"- {line}", allow_unicode))

    limitations = _build_report_limitations(summary, methods_summary, is_ru=is_ru)
    if limitations:
        if not (discussion or conclusion):
            pdf.add_page()
        else:
            pdf.ln(2)
        pdf.set_font(font_family, "B", body_size + 2)
        pdf.cell(0, 7, _safe_text("Ограничения" if is_ru else "Limitations", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font_family, "", body_size)
        for line in limitations:
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(f"- {line}", allow_unicode))

    return _pdf_bytes(pdf)
