import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from fpdf import FPDF

from app.schemas.analysis import AnalysisResult
from app.core.logging import logger

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _normalize_report_density(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"compact", "dense", "tight"}:
        return "compact"
    if s in {"spacious", "loose"}:
        return "spacious"
    return "comfortable"


def _parse_accent_css(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.startswith("#"):
        s = s[1:]
    s = s.strip()
    if len(s) == 3 and all(c in "0123456789abcdefABCDEF" for c in s):
        s = "".join([c * 2 for c in s])
    if len(s) != 6 or not all(c in "0123456789abcdefABCDEF" for c in s):
        return None
    return f"#{s.lower()}"


def _parse_accent_rgb(value: Any) -> Optional[tuple[int, int, int]]:
    css = _parse_accent_css(value)
    if not css:
        return None
    s = css[1:]
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except Exception:
        return None


def generate_legacy_plot_image(plot_data: List[Dict[str, Any]], method_id: str) -> str:
    if not plot_data:
        return ""

    df = pd.DataFrame(plot_data)

    plt.figure(figsize=(8, 6))
    sns.set_theme(style="whitegrid")

    ax = sns.stripplot(
        data=df,
        x="group",
        y="value",
        jitter=True,
        alpha=0.6,
        size=8,
        color="#0f172a",
    )

    sns.boxplot(
        data=df,
        x="group",
        y="value",
        showfliers=False,
        boxprops={"facecolor": "none", "edgecolor": "grey"},
        width=0.4,
        ax=ax,
    )

    plt.title(f"Distribution by Group ({method_id})")
    plt.xlabel("Group")
    plt.ylabel("Value")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close()

    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def render_report(
    analysis_result: AnalysisResult,
    target_col: str,
    group_col: str,
    dataset_name: str = "Dataset",
) -> str:
    plot_img = ""
    if analysis_result.plot_data:
        try:
            plot_img = generate_legacy_plot_image(analysis_result.plot_data, analysis_result.method.id)
        except Exception as e:
            logger.error(f"Error generating plot: {e}", exc_info=True)

    context = {
        "title": "Stat Analyzer Report",
        "dataset_name": dataset_name,
        "target_col": target_col,
        "group_col": group_col,
        "result": analysis_result,
        "image_base64": plot_img,
        "method_name": analysis_result.method.name,
        "method_desc": analysis_result.method.description,
        "p_value_fmt": f"{analysis_result.p_value:.4f}" if analysis_result.p_value >= 0.001 else "< 0.001",
    }

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("report.html")
    return template.render(**context)


def _normalize_method_type(value: Any) -> str:
    allowed = {
        "parametric",
        "non-parametric",
        "correlation",
        "categorical",
        "survival",
        "diagnostic",
        "assumption",
        "agreement",
        "reliability",
        "dimension_reduction",
        "clustering",
    }
    s = str(value or "").strip().lower()
    return s if s in allowed else "parametric"


def _coerce_method(method_value: Any) -> Dict[str, Any]:
    if isinstance(method_value, dict):
        return {
            "id": str(method_value.get("id") or method_value.get("name") or "method"),
            "name": str(method_value.get("name") or method_value.get("id") or "Method"),
            "description": str(method_value.get("description") or ""),
            "type": _normalize_method_type(method_value.get("type")),
        }
    if isinstance(method_value, str) and method_value.strip():
        m = method_value.strip()
        return {"id": m, "name": m, "description": "", "type": "parametric"}
    return {"id": "method", "name": "Method", "description": "", "type": "parametric"}


def render_report_from_results(
    results: Dict[str, Any],
    variables: Dict[str, Any],
    dataset_name: str = "Dataset",
) -> str:
    vars_map = variables if isinstance(variables, dict) else {}
    target = vars_map.get("target") or vars_map.get("feature") or "-"
    group = vars_map.get("group") or "-"
    method_payload = _coerce_method(results.get("method") if isinstance(results, dict) else None)
    analysis_result = AnalysisResult(
        method=method_payload,
        p_value=results.get("p_value") if isinstance(results, dict) else None,
        effect_size=results.get("effect_size") if isinstance(results, dict) else None,
        effect_size_name=results.get("effect_size_name") if isinstance(results, dict) else None,
        effect_size_ci_lower=results.get("effect_size_ci_lower") if isinstance(results, dict) else None,
        effect_size_ci_upper=results.get("effect_size_ci_upper") if isinstance(results, dict) else None,
        power=results.get("power") if isinstance(results, dict) else None,
        bf10=results.get("bf10") if isinstance(results, dict) else None,
        stat_value=results.get("stat_value") if isinstance(results, dict) else None,
        significant=bool(results.get("significant")) if isinstance(results, dict) else False,
        groups=results.get("groups") if isinstance(results, dict) else None,
        plot_data=results.get("plot_data") if isinstance(results, dict) else None,
        plot_stats=results.get("plot_stats") if isinstance(results, dict) else None,
        conclusion=str(
            (results.get("ai_interpretation") or results.get("conclusion") or "Анализ завершён")
            if isinstance(results, dict)
            else "Анализ завершён"
        ),
    )
    return render_report(analysis_result, str(target), str(group), dataset_name=dataset_name)


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
        if interpretation:
            pdf.ln(2)
            pdf.set_font(font_family, "B", body_size + 2)
            pdf.cell(0, 7, _safe_text("Интерпретация" if is_ru else "Interpretation", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            pdf.multi_cell(0, 5, _safe_text(interpretation, allow_unicode))

    return _pdf_bytes(pdf)
