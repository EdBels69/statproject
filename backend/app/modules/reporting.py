import os
import json
import html
import hashlib
import pandas as pd
import numpy as np
import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List, Optional
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.schemas.analysis import AnalysisResult
from app.core.logging import logger
from app.core.paths import get_workspace_dir
from app.stats.engine import _bf10_from_p_value_bound
from app.modules.analysis_result_v2 import normalize_analysis_result_v2, normalize_run_data_results

from app.modules.plot_with_brackets import add_significance_bracket, normalize_comparisons
from app.modules.plot_config import apply_publication_config, get_group_colors, COLORS

from fpdf import FPDF

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _result_fingerprint(res: Any) -> Optional[str]:
    if not isinstance(res, dict):
        return None
    try:
        payload = json.dumps(res, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
    except Exception:
        return None


def _dedupe_step_payloads(step_items: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    for item in step_items:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        step_id, res = item
        if not isinstance(step_id, str) or not isinstance(res, dict):
            continue
        fp = _result_fingerprint(res) or step_id
        prev = seen.get(fp)
        if prev is None:
            cur = {"step_id": step_id, "res": res, "dup_ids": [], "dup_count": 1}
            seen[fp] = cur
            out.append(cur)
            continue
        prev["dup_count"] = int(prev.get("dup_count") or 1) + 1
        prev.setdefault("dup_ids", []).append(step_id)
    return out


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        num = float(value)
        if not np.isfinite(num):
            return None
        return num
    except Exception:
        return None


def _method_id_from_payload(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    method_id = str(payload.get("method_id") or "").strip().lower()
    if method_id:
        return method_id
    method = payload.get("method")
    if isinstance(method, dict):
        method_id = str(method.get("id") or method.get("method_id") or method.get("name") or "").strip().lower()
        if method_id:
            return method_id
    if isinstance(method, str):
        method_id = str(method).strip().lower()
        if method_id:
            return method_id
    return ""


def _fmt_p_inline(value: Any) -> str:
    p = _safe_float(value)
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _extract_interpretation_contract(payload: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("interpretation_contract")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
        text = str(raw.get(key) or "").strip()
        if text:
            out[key] = text
    return out


def _render_interpretation_html(payload: Dict[str, Any], *, is_ru: bool) -> str:
    contract = _extract_interpretation_contract(payload if isinstance(payload, dict) else {})
    labels = {
        "claim": "Статистический вывод" if is_ru else "Statistical claim",
        "evidence": "Доказательная база" if is_ru else "Evidence",
        "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
        "limitations": "Ограничения" if is_ru else "Limitations",
        "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
    }
    if contract:
        rows = "".join(
            [
                f"<p><strong>{labels[k]}:</strong> {html.escape(v)}</p>"
                for k, v in contract.items()
                if isinstance(v, str) and v.strip()
            ]
        )
        if rows:
            return f'<div class="ai-box"><strong>{"Интерпретация" if is_ru else "Interpretation"}:</strong>{rows}</div>'

    fallback = payload.get("ai_interpretation") if is_ru else payload.get("conclusion")
    if not isinstance(fallback, str) or not fallback.strip():
        fallback = payload.get("conclusion") or payload.get("ai_interpretation")
    if isinstance(fallback, str) and fallback.strip():
        return (
            f'<div class="ai-box"><strong>{"Интерпретация" if is_ru else "Interpretation"}:</strong><br>'
            + html.escape(fallback.strip())
            + "</div>"
        )
    return ""


def _infer_sample_size(payload: Dict[str, Any]) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    for key in ["n", "n_observations", "n_subjects", "total_pairs"]:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            try:
                n = int(value)
                if n > 0:
                    return n
            except Exception:
                pass

    plot_stats = payload.get("plot_stats")
    if isinstance(plot_stats, dict) and plot_stats:
        total = 0
        found = False
        for stats in plot_stats.values():
            if not isinstance(stats, dict):
                continue
            count = stats.get("count")
            if isinstance(count, (int, float)):
                try:
                    c = int(count)
                    if c >= 0:
                        total += c
                        found = True
                except Exception:
                    pass
        if found and total > 0:
            return total

    plot_data = payload.get("plot_data")
    if isinstance(plot_data, list) and plot_data:
        return int(len(plot_data))
    return None


def _build_plot_caption(payload: Dict[str, Any], *, is_ru: bool) -> str:
    if not isinstance(payload, dict):
        return ""

    bits: List[str] = []
    n = _infer_sample_size(payload)
    if isinstance(n, int) and n > 0:
        bits.append(f"N={n}")

    p_value = payload.get("p_value")
    if p_value is None:
        p_value = payload.get("interaction_p_value")
    p_s = _fmt_p_inline(p_value)
    if p_s != "-":
        bits.append(f"p={p_s}")

    effect = _safe_float(payload.get("effect_size"))
    if effect is not None:
        effect_name = str(payload.get("effect_size_name") or "effect").strip()
        bits.append(f"{effect_name}={effect:.3f}")

    roc = payload.get("roc")
    if isinstance(roc, dict):
        auc = _safe_float(roc.get("auc"))
        if auc is not None:
            bits.append(f"AUC={auc:.3f}")

    silhouette = _safe_float(payload.get("silhouette_score"))
    if silhouette is not None:
        bits.append((f"silhouette={silhouette:.3f}" if not is_ru else f"силуэт={silhouette:.3f}"))

    calibration = payload.get("calibration")
    if isinstance(calibration, dict):
        brier = _safe_float(calibration.get("brier_score"))
        if brier is not None:
            bits.append(f"Brier={brier:.3f}")

    bootstrap = payload.get("bootstrap")
    if isinstance(bootstrap, dict):
        n_boot = bootstrap.get("n_resamples")
        if isinstance(n_boot, (int, float)):
            bits.append((f"bootstrap={int(n_boot)}" if not is_ru else f"bootstrap={int(n_boot)}"))

    ext_metrics = payload.get("external_metrics")
    if isinstance(ext_metrics, dict):
        auc_ext = _safe_float(ext_metrics.get("auc"))
        if auc_ext is not None:
            bits.append((f"external AUC={auc_ext:.3f}" if not is_ru else f"AUC внешн.={auc_ext:.3f}"))
        r2_ext = _safe_float(ext_metrics.get("r_squared"))
        if r2_ext is not None:
            bits.append(f"external R2={r2_ext:.3f}")

    items = payload.get("items")
    if isinstance(items, list) and items:
        sig_count = 0
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            if bool(item.get("sig")) or bool(item.get("significant")):
                sig_count += 1
        if total > 0:
            bits.append((f"значимых {sig_count}/{total}" if is_ru else f"significant {sig_count}/{total}"))

    if not bits:
        return "Диагностический график для текущего шага анализа." if is_ru else "Diagnostic figure for the current analysis step."

    prefix = "Подпись графика" if is_ru else "Figure caption"
    return f"{prefix}: " + "; ".join(bits) + "."


def _extract_protocol_findings(run_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return {"items": [], "total_steps": 0, "unique_steps": 0, "significant_steps": 0, "alpha": None}
    run_data = normalize_run_data_results(run_data)

    ai_summary = None
    for key in ("report_summary", "ai_summary"):
        candidate = run_data.get(key)
        if isinstance(candidate, dict):
            ai_summary = candidate
            break

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

    alpha_default = _safe_float(run_data.get("alpha"))
    if alpha_default is None:
        globals_in = run_data.get("globals") if isinstance(run_data.get("globals"), dict) else None
        alpha_default = _safe_float(globals_in.get("alpha") if isinstance(globals_in, dict) else None)
    if alpha_default is None:
        protocol = run_data.get("protocol") if isinstance(run_data.get("protocol"), dict) else None
        if isinstance(protocol, dict):
            alpha_default = _safe_float(protocol.get("alpha"))

    def _extract_meta_value(meta: Dict[str, Any], res: Dict[str, Any], keys: List[str]) -> Optional[str]:
        if isinstance(meta, dict):
            cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
            for k in keys:
                v = cfg.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in keys:
                v = meta.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        for k in keys:
            v = res.get(k) if isinstance(res, dict) else None
            if isinstance(v, str) and v.strip():
                return v.strip()
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
    deduped = _dedupe_step_payloads(raw_steps)

    items: List[Dict[str, Any]] = []
    significant_steps = 0

    for entry in deduped:
        if not isinstance(entry, dict):
            continue
        step_id = entry.get("step_id")
        res = entry.get("res")
        if not isinstance(step_id, str) or not isinstance(res, dict):
            continue
        meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
        meta = meta if isinstance(meta, dict) else {}

        method_hint = meta.get("method")
        cfg_hint = meta.get("config") if isinstance(meta.get("config"), dict) else {}
        res = normalize_analysis_result_v2(res, method_id=method_hint, config=cfg_hint)

        method = res.get("method")
        method_name = None
        if isinstance(method, dict):
            method_name = method.get("name") or method.get("id")
        elif isinstance(method, str):
            method_name = method
        if not isinstance(method_name, str) or not method_name.strip():
            method_name = str(res.get("method_id") or "").strip() or None

        p_value = _safe_float(res.get("p_value"))
        alpha = _safe_float(res.get("alpha")) or alpha_default
        sig = res.get("significant")
        if not isinstance(sig, bool) and p_value is not None and alpha is not None:
            sig = p_value < alpha
        if isinstance(sig, bool) and sig:
            significant_steps += 1

        conclusion = res.get("ai_interpretation") or res.get("conclusion")
        if not isinstance(conclusion, str):
            conclusion = None

        target = _extract_meta_value(meta, res, ["target", "outcome", "endpoint", "y"])
        group = _extract_meta_value(meta, res, ["group", "group_col", "predictor", "x"])
        visit = _extract_meta_value(meta, res, ["visit", "time", "timepoint", "visit_label", "time_label"])
        task = _extract_meta_value(meta, res, ["task", "analysis_task", "objective", "goal", "section"])

        items.append(
            {
                "step_id": step_id,
                "type": res.get("type"),
                "method": method_name,
                "p_value": p_value,
                "alpha": alpha,
                "significant": sig,
                "effect_size": _safe_float(res.get("effect_size")),
                "conclusion": conclusion,
                "target": target,
                "group": group,
                "visit": visit,
                "task": task,
            }
        )

    return {
        "items": items,
        "total_steps": len(raw_steps),
        "unique_steps": len(deduped),
        "significant_steps": significant_steps,
        "alpha": alpha_default,
        "ai_summary": ai_summary,
    }


def _build_discussion_conclusion(findings: Dict[str, Any], is_ru: bool) -> Dict[str, List[str]]:
    if isinstance(findings, dict):
        ai_summary = findings.get("ai_summary")
        if isinstance(ai_summary, dict):
            discussion = ai_summary.get("discussion")
            conclusion = ai_summary.get("conclusion") or ai_summary.get("conclusions")

            def _norm(value: Any) -> List[str]:
                if isinstance(value, list):
                    return [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
                if isinstance(value, (str, int, float)):
                    s = str(value).strip()
                    return [s] if s else []
                return []

            discussion_out = _norm(discussion)
            conclusion_out = _norm(conclusion)
            if discussion_out or conclusion_out:
                return {
                    "discussion": discussion_out,
                    "conclusion": conclusion_out,
                }

    total_steps = int(findings.get("unique_steps") or findings.get("total_steps") or 0)
    significant_steps = int(findings.get("significant_steps") or 0)
    alpha_val = _safe_float(findings.get("alpha"))

    items = findings.get("items") if isinstance(findings.get("items"), list) else []

    def _shorten(text: str, max_len: int = 220) -> str:
        s = str(text or "").strip()
        if len(s) <= max_len:
            return s
        return s[: max_len - 1].rstrip() + "…"

    def _item_label(item: Dict[str, Any]) -> str:
        parts: List[str] = []
        target = item.get("target")
        group = item.get("group")
        visit = item.get("visit")
        if target:
            parts.append(str(target))
        if group:
            parts.append(str(group))
        if visit:
            parts.append(str(visit))
        if parts:
            return " / ".join(parts)
        return str(item.get("step_id") or "")

    def _format_item(item: Dict[str, Any]) -> str:
        label = _item_label(item)
        p = item.get("p_value")
        sig = item.get("significant")
        conclusion = item.get("conclusion")
        method_name = item.get("method")

        prefix = label or (item.get("method") or item.get("type") or "Step")
        if method_name and method_name not in prefix:
            prefix = f"{prefix} · {method_name}"

        if isinstance(conclusion, str) and conclusion.strip():
            return f"{prefix}: {_shorten(conclusion)}"

        if isinstance(sig, bool):
            if sig:
                return f"{prefix}: {('значимый эффект' if is_ru else 'significant effect')} (p={_fmt_p_inline(p)})"
            return f"{prefix}: {('значимых различий не выявлено' if is_ru else 'no significant difference')} (p={_fmt_p_inline(p)})"

        return f"{prefix}: p={_fmt_p_inline(p)}"

    # Rank items: significant first, then lowest p-value
    def _rank_key(item: Dict[str, Any]) -> tuple:
        sig = item.get("significant")
        p = item.get("p_value")
        p_val = p if isinstance(p, (int, float)) else 1.0
        return (0 if sig else 1, p_val)

    ranked = sorted([i for i in items if isinstance(i, dict)], key=_rank_key)
    top_items = ranked[:6]

    discussion: List[str] = []
    conclusion: List[str] = []

    if total_steps <= 0:
        discussion.append("Нет результатов для обсуждения." if is_ru else "No results available for discussion.")
        conclusion.append("Требуется запуск анализа." if is_ru else "Run the analysis to generate conclusions.")
        return {"discussion": discussion, "conclusion": conclusion}

    if alpha_val is None:
        alpha_val = 0.05

    if significant_steps > 0:
        discussion.append(
            (f"При α={alpha_val:.3f} значимые эффекты получены в {significant_steps} из {total_steps} шагов."
             if is_ru else
             f"At α={alpha_val:.3f}, significant effects were observed in {significant_steps} of {total_steps} steps.")
        )
    else:
        discussion.append(
            (f"При α={alpha_val:.3f} статистически значимых результатов не выявлено."
             if is_ru else
             f"At α={alpha_val:.3f}, no statistically significant results were detected.")
        )

    if top_items:
        discussion.append(
            ("Ключевые наблюдения сведены из автоматических интерпретаций шагов протокола."
             if is_ru else
             "Key observations were derived from automated step interpretations.")
        )
    else:
        discussion.append(
            ("Автоматических интерпретаций недостаточно для выводов."
             if is_ru else
             "Automated interpretations are insufficient for conclusions.")
        )

    for item in top_items:
        line = _format_item(item)
        if line:
            conclusion.append(line)

    if not conclusion:
        conclusion.append("Добавьте интерпретацию шагов, чтобы сформировать выводы." if is_ru else "Provide step interpretations to form conclusions.")

    return {"discussion": discussion, "conclusion": conclusion}


def _method_label_from_type(result_type: Any, is_ru: bool) -> str:
    t = str(result_type or "").strip().lower()
    mapping_ru = {
        "table_1": "Описательная статистика (Table 1)",
        "descriptive": "Описательная статистика",
        "batch_compare_by_factor": "Сравнение по факторам/визитам",
        "batch_analysis": "Пакетный инференциальный анализ",
        "timepoint_batch_analysis": "Пакетный анализ по временным точкам",
        "delta_batch_analysis": "Пакетный анализ изменений (delta)",
        "responders": "Responder-анализ",
        "bootstrap_pipeline": "Bootstrap-пайплайн устойчивости",
        "cluster_profiles": "Профили кластеров",
        "external_validation": "Внешняя валидация",
    }
    mapping_en = {
        "table_1": "Descriptive statistics (Table 1)",
        "descriptive": "Descriptive statistics",
        "batch_compare_by_factor": "Longitudinal factor-wise comparison",
        "batch_analysis": "Batch inferential analysis",
        "timepoint_batch_analysis": "Timepoint batch analysis",
        "delta_batch_analysis": "Delta batch analysis",
        "responders": "Responder analysis",
        "bootstrap_pipeline": "Bootstrap stability pipeline",
        "cluster_profiles": "Cluster profiles",
        "external_validation": "External validation",
    }
    mapping = mapping_ru if is_ru else mapping_en
    return str(mapping.get(t) or "")


def _extract_report_methods(run_data: Dict[str, Any], is_ru: bool) -> Dict[str, Any]:
    findings = _extract_protocol_findings(run_data if isinstance(run_data, dict) else {})
    items = findings.get("items") if isinstance(findings.get("items"), list) else []

    method_rows: Dict[str, Dict[str, Any]] = {}
    missing_inferential: List[str] = []
    inferential_types = {
        "compare",
        "hypothesis_test",
        "correlation",
        "regression",
        "survival",
        "mixed_effects",
        "clustered_correlation",
        "batch_analysis",
        "timepoint_batch_analysis",
        "delta_batch_analysis",
        "responders",
        "bootstrap_pipeline",
        "cluster_profiles",
        "external_validation",
    }

    for item in items:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or "").strip() or "unknown_step"
        target = str(item.get("target") or "").strip()
        result_type = str(item.get("type") or "").strip().lower()
        method_label = str(item.get("method") or "").strip()
        if not method_label:
            method_label = _method_label_from_type(result_type, is_ru)

        p_value = _safe_float(item.get("p_value"))
        is_inferential = result_type in inferential_types or p_value is not None
        if not method_label:
            if is_inferential:
                missing_inferential.append(step_id)
            continue

        key = method_label.lower()
        bucket = method_rows.get(key)
        if bucket is None:
            bucket = {
                "method": method_label,
                "steps": [],
                "targets": [],
                "count": 0,
            }
            method_rows[key] = bucket
        bucket["count"] = int(bucket.get("count") or 0) + 1
        bucket["steps"].append(step_id)
        if target:
            bucket["targets"].append(target)

    rows = []
    for row in method_rows.values():
        steps = list(dict.fromkeys([str(x) for x in row.get("steps", []) if str(x).strip()]))
        targets = list(dict.fromkeys([str(x) for x in row.get("targets", []) if str(x).strip()]))
        rows.append(
            {
                "method": str(row.get("method") or "").strip(),
                "count": int(row.get("count") or 0),
                "steps": steps,
                "targets": targets,
            }
        )
    rows = sorted(rows, key=lambda r: (-int(r.get("count") or 0), str(r.get("method") or "")))

    return {
        "rows": rows,
        "missing_inferential_steps": list(dict.fromkeys(missing_inferential)),
        "total_items": len(items),
    }


def _build_report_limitations(findings: Dict[str, Any], methods_summary: Dict[str, Any], is_ru: bool) -> List[str]:
    items = findings.get("items") if isinstance(findings.get("items"), list) else []
    missing_methods = methods_summary.get("missing_inferential_steps") if isinstance(methods_summary, dict) else []
    missing_methods = missing_methods if isinstance(missing_methods, list) else []

    inferential_with_missing_p = []
    inferential_without_effect = 0
    inferential_total = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        p_value = _safe_float(item.get("p_value"))
        effect = _safe_float(item.get("effect_size"))
        item_type = str(item.get("type") or "").strip().lower()
        is_inferential = p_value is not None or item_type in {
            "compare",
            "hypothesis_test",
            "correlation",
            "regression",
            "survival",
            "mixed_effects",
            "clustered_correlation",
            "batch_analysis",
            "timepoint_batch_analysis",
            "delta_batch_analysis",
            "responders",
            "bootstrap_pipeline",
            "cluster_profiles",
            "external_validation",
        }
        if not is_inferential:
            continue
        inferential_total += 1
        if p_value is None:
            inferential_with_missing_p.append(str(item.get("step_id") or "unknown_step"))
        if effect is None:
            inferential_without_effect += 1

    limitations: List[str] = []
    if not items:
        limitations.append(
            "В отчёте нет исполнимых аналитических шагов."
            if is_ru
            else "The report contains no analyzable execution steps."
        )
    if missing_methods:
        preview = ", ".join([str(x) for x in missing_methods[:6]])
        if len(missing_methods) > 6:
            preview += ", ..."
        limitations.append(
            f"Для части инференциальных шагов отсутствует metadata по методу: {preview}."
            if is_ru
            else f"Method metadata is missing for some inferential steps: {preview}."
        )
    if inferential_with_missing_p:
        limitations.append(
            "Часть инференциальных шагов не содержит p-value; интерпретация ограничена."
            if is_ru
            else "Some inferential steps do not contain p-values; interpretation is limited."
        )
    if inferential_total > 0 and inferential_without_effect > 0:
        limitations.append(
            "Не для всех инференциальных шагов рассчитан размер эффекта."
            if is_ru
            else "Effect sizes are not available for all inferential steps."
        )

    significant_steps = int(findings.get("significant_steps") or 0)
    if inferential_total > 0 and significant_steps == 0:
        limitations.append(
            "Статистически значимые эффекты не выявлены при текущем уровне α."
            if is_ru
            else "No statistically significant effects were detected at the current alpha level."
        )

    if not limitations:
        limitations.append(
            "Существенных методологических ограничений, выявляемых автоматически, не найдено."
            if is_ru
            else "No major automatically-detected methodological limitations were found."
        )
    return limitations


def _interpret_bf10_ru(value: Any) -> Optional[str]:
    try:
        if value is None:
            return None
        bf10 = float(value)
        if not np.isfinite(bf10) or bf10 <= 0:
            return None
    except Exception:
        return None

    def _label(strength: float) -> str:
        if strength < 1:
            return "нет данных"
        if strength < 3:
            return "слабое"
        if strength < 10:
            return "умеренное"
        if strength < 30:
            return "сильное"
        if strength < 100:
            return "очень сильное"
        return "экстремально сильное"

    if bf10 >= 1:
        return f"BF10={bf10:.3g}: {_label(bf10)} свидетельство в пользу H1 (различия есть)."

    bf01 = 1.0 / bf10
    return f"BF10={bf10:.3g} (BF01={bf01:.3g}): {_label(bf01)} свидетельство в пользу H0 (различий нет)."


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


def _coerce_alpha(primary: Any, fallback: Any = None, default: float = 0.05) -> float:
    alpha = _safe_float(primary)
    if alpha is None:
        alpha = _safe_float(fallback)
    if alpha is None:
        alpha = float(default)
    return alpha


def _normalize_method_text(value: Any) -> str:
    if isinstance(value, dict):
        method = value.get("id") or value.get("name")
        return str(method or "").strip()
    if value is None:
        return ""
    return str(value).strip()


def _batch_target_label(item: Dict[str, Any]) -> str:
    target = item.get("target") or item.get("outcome")
    label = item.get("label")
    baseline = item.get("baseline")
    follow = item.get("follow")

    if label:
        if baseline and follow:
            return f"{label} (Delta {baseline}->{follow})"
        return str(label)
    if baseline and follow:
        return f"Delta {baseline}->{follow}"
    if target:
        return str(target)
    return ""


def _collect_batch_inferential_rows(items: Any, alpha_val: float) -> Dict[str, Any]:
    local_items = items if isinstance(items, list) else []
    rows: List[Dict[str, Any]] = []
    label_pairs: List[tuple[str, str]] = []

    for item in local_items:
        if not isinstance(item, dict):
            continue
        target = _batch_target_label(item)
        if not target:
            continue

        p_raw = _safe_float(item.get("p_value"))
        p_adj = _safe_float(item.get("p_value_adj"))
        if p_adj is None:
            p_adj = _safe_float(item.get("adjusted_p_value"))
        p_used = p_adj if p_adj is not None else p_raw
        significant = bool(p_used < alpha_val) if p_used is not None else False
        method = _normalize_method_text(item.get("method"))

        group_stats: Dict[str, Dict[str, Any]] = {}
        ps = item.get("plot_stats")
        if isinstance(ps, dict):
            for key, value in ps.items():
                if isinstance(value, dict):
                    group_stats[str(key)] = value
            if len(group_stats) >= 2:
                labels = list(group_stats.keys())[:2]
                label_pairs.append((labels[0], labels[1]))

        rows.append(
            {
                "target": str(target),
                "p_raw": p_raw,
                "p_adj": p_adj,
                "p_used": p_used,
                "sig": significant,
                "method": method,
                "group_stats": group_stats,
            }
        )

    rows = sorted(rows, key=lambda row: row["p_used"] if isinstance(row.get("p_used"), (int, float)) else 1.0)
    sig_count = len([row for row in rows if row.get("sig")])
    has_adj = any(row.get("p_adj") is not None for row in rows)

    group_labels: Optional[List[str]] = None
    if label_pairs:
        first = label_pairs[0]
        if all(pair == first for pair in label_pairs):
            group_labels = [first[0], first[1]]

    return {
        "rows": rows,
        "sig_count": sig_count,
        "has_adj": has_adj,
        "group_labels": group_labels,
    }


def _build_pairwise_comparison_rows(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(res, dict):
        return []

    plot_stats = res.get("plot_stats")
    if not isinstance(plot_stats, dict) or not plot_stats:
        return []

    method_obj = res.get("method")
    method_id = None
    if hasattr(method_obj, "id"):
        method_id = getattr(method_obj, "id")
    elif isinstance(method_obj, dict):
        method_id = method_obj.get("id")
    elif isinstance(method_obj, str):
        method_id = method_obj
    method_id = str(method_id or "").strip().lower()

    use_median = method_id in {"mann_whitney", "wilcoxon", "kruskal"}

    comps = normalize_comparisons(res.get("comparisons") or res.get("plot_comparisons") or res.get("post_hoc"))
    if not comps:
        groups = res.get("groups")
        p_val = res.get("p_value")
        if isinstance(groups, list) and len(groups) == 2 and p_val is not None:
            try:
                comps = normalize_comparisons([{"a": str(groups[0]), "b": str(groups[1]), "p_value": float(p_val)}])
            except Exception:
                comps = []

    if not comps:
        return []

    bf10_single = res.get("bf10") if len(comps) == 1 else None
    eff_single = res.get("effect_size") if len(comps) == 1 else None
    eff_name_single = res.get("effect_size_name") if len(comps) == 1 else None

    plot_data = res.get("plot_data")
    values_by_group: Dict[str, np.ndarray] = {}
    if isinstance(plot_data, list):
        buckets: Dict[str, List[float]] = {}
        for row in plot_data:
            if not isinstance(row, dict):
                continue
            g = row.get("group")
            v = row.get("value")
            if g is None or v is None:
                continue
            try:
                f = float(v)
                if not np.isfinite(f):
                    continue
            except Exception:
                continue
            key = str(g)
            buckets.setdefault(key, []).append(f)
        for k, vals in buckets.items():
            if vals:
                values_by_group[k] = np.asarray(vals, dtype=float)

    def _cohen_d_ind(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        try:
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            n1 = int(x.size)
            n2 = int(y.size)
            if n1 < 2 or n2 < 2:
                return None
            m1 = float(np.mean(x))
            m2 = float(np.mean(y))
            s1 = float(np.std(x, ddof=1))
            s2 = float(np.std(y, ddof=1))
            if not (np.isfinite(s1) and np.isfinite(s2)):
                return None
            denom = (n1 + n2 - 2)
            if denom <= 0:
                return None
            sp2 = (((n1 - 1) * (s1 ** 2)) + ((n2 - 1) * (s2 ** 2))) / float(denom)
            if sp2 <= 0 or not np.isfinite(sp2):
                return None
            sp = float(np.sqrt(sp2))
            if sp == 0 or not np.isfinite(sp):
                return None
            return (m1 - m2) / sp
        except Exception:
            return None

    def _cohen_d_paired(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        try:
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            if x.size != y.size or x.size < 2:
                return None
            d = x - y
            d = d[np.isfinite(d)]
            if d.size < 2:
                return None
            md = float(np.mean(d))
            sd = float(np.std(d, ddof=1))
            if sd == 0 or not np.isfinite(sd):
                return None
            return md / sd
        except Exception:
            return None

    def _rank_biserial_from_samples(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        try:
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            n1 = int(x.size)
            n2 = int(y.size)
            if n1 == 0 or n2 == 0:
                return None
            y_sorted = np.sort(y)
            less = 0
            greater = 0
            for xv in x:
                li = int(np.searchsorted(y_sorted, xv, side="left"))
                ri = int(np.searchsorted(y_sorted, xv, side="right"))
                less += li
                greater += (n2 - ri)
            denom = n1 * n2
            if denom <= 0:
                return None
            return (greater - less) / float(denom)
        except Exception:
            return None

    out: List[Dict[str, Any]] = []
    for c in comps:
        a = c.a
        b = c.b
        sa = plot_stats.get(a, {}) if isinstance(plot_stats.get(a), dict) else {}
        sb = plot_stats.get(b, {}) if isinstance(plot_stats.get(b), dict) else {}

        def _num(v: Any) -> Optional[float]:
            try:
                if v is None:
                    return None
                f = float(v)
                return f if np.isfinite(f) else None
            except Exception:
                return None

        if use_median:
            ca = _num(sa.get("median"))
            cb = _num(sb.get("median"))
            spread_a = (_num(sa.get("q1")), _num(sa.get("q3")))
            spread_b = (_num(sb.get("q1")), _num(sb.get("q3")))
            center_label = "median"
        else:
            ca = _num(sa.get("mean"))
            cb = _num(sb.get("mean"))
            spread_a = _num(sa.get("sd"))
            spread_b = _num(sb.get("sd"))
            center_label = "mean"

        diff = (ca - cb) if (ca is not None and cb is not None) else None
        diff_pct = None
        if diff is not None and cb is not None and cb != 0:
            try:
                diff_pct = float(diff) / float(cb) * 100.0
            except Exception:
                diff_pct = None

        x = values_by_group.get(a)
        y = values_by_group.get(b)
        eff_pair = None
        eff_name_pair = None
        if x is not None and y is not None:
            if method_id in {"t_test_rel"}:
                eff_pair = _cohen_d_paired(x, y)
                eff_name_pair = "cohen-d" if eff_pair is not None else None
            elif use_median:
                eff_pair = _rank_biserial_from_samples(x, y)
                eff_name_pair = "rbc" if eff_pair is not None else None
            else:
                eff_pair = _cohen_d_ind(x, y)
                eff_name_pair = "cohen-d" if eff_pair is not None else None

        bf10_pair = bf10_single
        if bf10_pair is None:
            bf10_pair = _bf10_from_p_value_bound(c.p_value)

        out.append(
            {
                "a": a,
                "b": b,
                "p_value": float(c.p_value),
                "center_label": center_label,
                "a_center": ca,
                "b_center": cb,
                "a_spread": spread_a,
                "b_spread": spread_b,
                "a_n": sa.get("count"),
                "b_n": sb.get("count"),
                "diff": diff,
                "diff_pct": diff_pct,
                "effect_size": eff_single if eff_single is not None else eff_pair,
                "effect_size_name": eff_name_single if eff_single is not None else eff_name_pair,
                "bf10": bf10_pair,
            }
        )

    return out


def _format_axis_label(res: Dict[str, Any], is_ru: bool) -> str:
    if not isinstance(res, dict):
        return "Показатель" if is_ru else "Value"

    label = res.get("target_label") or res.get("outcome_label") or res.get("target") or res.get("outcome")
    label_s = str(label).strip() if label is not None else ""
    unit = res.get("unit") or res.get("units")
    unit_s = str(unit).strip() if unit is not None else ""

    if label_s and unit_s and (unit_s not in label_s):
        return f"{label_s} ({unit_s})"
    if label_s:
        return label_s
    return "Показатель" if is_ru else "Value"


def _format_group_axis_label(res: Dict[str, Any], is_ru: bool) -> str:
    if not isinstance(res, dict):
        return "Группа" if is_ru else "Group"
    label = res.get("group_label") or res.get("group_column_label") or res.get("group") or res.get("group_column")
    s = str(label).strip() if label is not None else ""
    return s or ("Группа" if is_ru else "Group")


def _method_selection_rationale_ru(res: Dict[str, Any]) -> Optional[str]:
    if not isinstance(res, dict):
        return None

    method_obj = res.get("method")
    method_id = None
    if hasattr(method_obj, "id"):
        method_id = getattr(method_obj, "id")
    elif isinstance(method_obj, dict):
        method_id = method_obj.get("id")
    elif isinstance(method_obj, str):
        method_id = method_obj
    method_id = str(method_id or "").strip().lower()

    plot_stats = res.get("plot_stats")
    if isinstance(plot_stats, dict) and plot_stats:
        group_count = len(plot_stats)
    else:
        g = res.get("groups")
        group_count = len(g) if isinstance(g, list) else 0

    assumptions = res.get("assumptions")
    if not isinstance(assumptions, dict):
        assumptions = {}

    norm = assumptions.get("normality")
    normality_ok = None
    if isinstance(norm, dict) and norm:
        passed_vals = [v.get("passed") for v in norm.values() if isinstance(v, dict) and v.get("passed") is not None]
        if passed_vals:
            normality_ok = all(bool(x) for x in passed_vals)

    homo = assumptions.get("homogeneity")
    homogeneity_ok = homo.get("passed") if isinstance(homo, dict) else None

    paired = method_id in {"t_test_rel", "wilcoxon"}

    if group_count >= 3:
        if method_id in {"anova", "anova_welch"}:
            if method_id == "anova_welch" or homogeneity_ok is False:
                return "Выбран Welch ANOVA: есть 3+ группы, а предпосылка равенства дисперсий нарушена (или не гарантирована)."
            return "Выбрана ANOVA: есть 3+ группы, и данные близки к нормальным; сравниваем средние между группами."
        if method_id == "kruskal":
            return "Выбран Kruskal–Wallis: есть 3+ группы, а нормальность нарушена/сомнительна; сравниваем распределения по рангам."
        return "Есть 3+ группы: сначала проверяется общий межгрупповой тест, затем (при необходимости) выполняются попарные post‑hoc сравнения."

    if group_count == 2:
        if method_id in {"t_test_ind", "t_test_rel", "t_test_welch"}:
            if paired:
                return "Выбран парный t‑тест: сравниваются две связанные выборки (повторные измерения/пары), нормальность различий приемлема."
            if method_id == "t_test_welch" or homogeneity_ok is False:
                return "Выбран t‑тест Уэлча: сравниваются две независимые группы, нормальность приемлема, но дисперсии неравны."
            return "Выбран t‑тест Стьюдента: сравниваются две независимые группы, нормальность и гомогенность дисперсий приемлемы."
        if method_id in {"mann_whitney", "wilcoxon"}:
            if paired:
                return "Выбран Wilcoxon: две связанные выборки, нормальность нарушена/сомнительна; сравнение по рангам."
            return "Выбран Mann–Whitney: две независимые группы, нормальность нарушена/сомнительна; сравнение по рангам."
        return "Сравниваются две группы: выбор теста определяется предпосылками (нормальность/дисперсии) и связанностью данных."

    return None


def _parse_accent_rgb(value: Any) -> Optional[tuple[int, int, int]]:
    css = _parse_accent_css(value)
    if not css:
        return None
    s = css[1:]
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except Exception:
        return None


def _report_plot_theme() -> Dict[str, Any]:
    palette = get_group_colors(8)
    primary = COLORS.get("primary", "#0f172a")
    secondary = COLORS.get("secondary", "#64748b")
    accent = COLORS.get("accent", "#8b5cf6")
    neutral = COLORS.get("neutral", "#f1f5f9")
    if not palette:
        palette = [primary, accent]

    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "neutral": neutral,
        "palette": palette,
        "bar_fill": palette[0],
        "box_fill": neutral,
        "diag_line": secondary,
        "hexbin_cmap": "viridis",
        "contingency_cmap": "Blues",
        "correlation_heatmap_cmap": "vlag",
    }


def _render_plot_png_bytes(res: Dict[str, Any], is_ru: bool = False) -> bytes:
    try:
        plot_b64 = res.get("plot_image_b64") if isinstance(res, dict) else None
        if isinstance(plot_b64, str) and plot_b64.strip():
            try:
                return base64.b64decode(plot_b64)
            except Exception:
                pass
        apply_publication_config()
        theme = _report_plot_theme()
        palette = list(theme.get("palette") or [])
        if not palette:
            palette = [str(theme.get("primary") or "#0f172a"), str(theme.get("accent") or "#8b5cf6")]

        base_type = res.get("type") if isinstance(res, dict) else None

        if base_type == "table_1":
            stats = res.get("data") if isinstance(res, dict) else None
            if isinstance(stats, dict) and stats:
                groups = [k for k in stats.keys() if k != "overall"]
                xs = []
                ys = []
                yerr_low = []
                yerr_high = []
                for g in groups:
                    s = stats.get(g)
                    if not isinstance(s, dict):
                        continue
                    mean = s.get("mean")
                    try:
                        mean_f = float(mean)
                        if not np.isfinite(mean_f):
                            continue
                    except Exception:
                        continue

                    lo = s.get("ci_95_low")
                    hi = s.get("ci_95_high")
                    n = s.get("count")
                    std = s.get("std")

                    lo_f = None
                    hi_f = None
                    try:
                        lo_f = float(lo) if lo is not None else None
                        if lo_f is not None and not np.isfinite(lo_f):
                            lo_f = None
                    except Exception:
                        lo_f = None
                    try:
                        hi_f = float(hi) if hi is not None else None
                        if hi_f is not None and not np.isfinite(hi_f):
                            hi_f = None
                    except Exception:
                        hi_f = None

                    if lo_f is None or hi_f is None:
                        try:
                            n_f = float(n) if n is not None else None
                            std_f = float(std) if std is not None else None
                            if n_f is not None and std_f is not None and np.isfinite(n_f) and np.isfinite(std_f) and n_f > 1:
                                sem = std_f / float(np.sqrt(n_f))
                                lo_f = mean_f - 1.96 * sem
                                hi_f = mean_f + 1.96 * sem
                        except Exception:
                            lo_f = None
                            hi_f = None

                    xs.append(str(g) + (f"\n(n={int(n)})" if isinstance(n, (int, float)) else ""))
                    ys.append(mean_f)
                    if lo_f is not None and hi_f is not None:
                        yerr_low.append(max(0.0, mean_f - lo_f))
                        yerr_high.append(max(0.0, hi_f - mean_f))
                    else:
                        yerr_low.append(0.0)
                        yerr_high.append(0.0)

                if xs and ys:
                    plt.figure(figsize=(7.6, 4.4))
                    x_pos = np.arange(len(xs))
                    yerr = np.array([yerr_low, yerr_high])
                    bar_color = str(theme.get("bar_fill") or palette[0])
                    edge_color = str(theme.get("primary") or "#0f172a")
                    plt.bar(x_pos, ys, color=bar_color, edgecolor=edge_color, linewidth=1.0, alpha=0.85)
                    if yerr.size and np.any(yerr > 0):
                        plt.errorbar(x_pos, ys, yerr=yerr, fmt="none", ecolor=edge_color, elinewidth=1.2, capsize=4)
                    plot_data = res.get("plot_data") if isinstance(res, dict) else None
                    if isinstance(plot_data, list) and plot_data:
                        group_order = []
                        for label in xs:
                            name = str(label).split("\n", 1)[0]
                            group_order.append(name)
                        group_index = {g: i for i, g in enumerate(group_order)}
                        rng = np.random.default_rng(42)
                        xs_scatter = []
                        ys_scatter = []
                        for row in plot_data:
                            if not isinstance(row, dict):
                                continue
                            g = row.get("group")
                            v = row.get("value")
                            if g is None or v is None:
                                continue
                            try:
                                yv = float(v)
                            except Exception:
                                continue
                            gi = group_index.get(str(g))
                            if gi is None:
                                continue
                            xs_scatter.append(float(gi) + float(rng.uniform(-0.12, 0.12)))
                            ys_scatter.append(yv)
                        if xs_scatter:
                            plt.scatter(xs_scatter, ys_scatter, s=14, alpha=0.45, color=edge_color, zorder=3)
                    plt.xticks(x_pos, xs)
                    plt.title("Описательная статистика (среднее ± 95% ДИ)" if is_ru else "Descriptives (mean ± 95% CI)")
                    plt.xlabel("Группа" if is_ru else "Group")
                    plt.ylabel(_format_axis_label(res, is_ru))
                    plt.grid(True, axis="y", alpha=0.25)
                    buf = io.BytesIO()
                    plt.tight_layout()
                    plt.savefig(buf, format="png")
                    plt.close()
                    return bytes(buf.getvalue())

        cont = res.get("contingency") if isinstance(res, dict) else None
        if isinstance(cont, dict) and isinstance(cont.get("counts"), list) and cont.get("counts"):
            try:
                counts = np.array(cont.get("counts"))
                if counts.size:
                    plt.figure(figsize=(7.6, 4.6))
                    rows = cont.get("rows") if isinstance(cont.get("rows"), list) else None
                    cols = cont.get("cols") if isinstance(cont.get("cols"), list) else None
                    rlab = [str(x) for x in rows] if rows else None
                    clab = [str(x) for x in cols] if cols else None
                    sns.heatmap(
                        counts,
                        annot=True,
                        fmt="g",
                        cmap=str(theme.get("contingency_cmap") or "Blues"),
                        cbar=False,
                        xticklabels=clab if clab else True,
                        yticklabels=rlab if rlab else True,
                    )
                    plt.title("Таблица сопряжённости")
                    plt.xlabel("Группа")
                    plt.ylabel("Категория")
                    buf = io.BytesIO()
                    plt.tight_layout()
                    plt.savefig(buf, format="png")
                    plt.close()
                    return bytes(buf.getvalue())
            except Exception:
                try:
                    plt.close()
                except Exception:
                    pass

        if base_type == "mixed_effects":
            estimated_means = res.get("estimated_means") if isinstance(res, dict) else None
            if isinstance(estimated_means, dict) and estimated_means:
                groups = list(estimated_means.keys())
                time_labels = []
                for g in groups:
                    tps = estimated_means.get(g)
                    if isinstance(tps, dict):
                        time_labels.extend(list(tps.keys()))
                time_labels = [str(x) for x in dict.fromkeys(time_labels).keys()]
                try:
                    time_labels_sorted = sorted(time_labels, key=lambda x: float(x))
                except Exception:
                    time_labels_sorted = time_labels

                w = 7.5
                h = 4.8
                plt.figure(figsize=(w, h))
                xs = list(range(len(time_labels_sorted)))
                for idx, g in enumerate(groups):
                    points = estimated_means.get(g)
                    if not isinstance(points, dict):
                        continue
                    ys = []
                    yerr = []
                    for t in time_labels_sorted:
                        cell = points.get(t)
                        if not isinstance(cell, dict):
                            ys.append(np.nan)
                            yerr.append((0.0, 0.0))
                            continue
                        est = cell.get("estimate")
                        lo = cell.get("ci_lower")
                        hi = cell.get("ci_upper")
                        y = float(est) if isinstance(est, (int, float)) else np.nan
                        ys.append(y)
                        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and np.isfinite(y):
                            yerr.append((max(0.0, y - float(lo)), max(0.0, float(hi) - y)))
                        else:
                            yerr.append((0.0, 0.0))

                    yerr_arr = np.array(yerr).T if yerr else None
                    color = palette[idx % len(palette)]
                    plt.errorbar(
                        xs,
                        ys,
                        yerr=yerr_arr,
                        marker="o",
                        linewidth=2,
                        capsize=3,
                        color=color,
                        markerfacecolor=color,
                        markeredgecolor=str(theme.get("primary") or "#0f172a"),
                        label=str(g),
                    )

                plt.xticks(xs, time_labels_sorted, rotation=0)
                plt.title("Время × Группа" if is_ru else "Time × Group")
                plt.xlabel("Время" if is_ru else "Time")
                plt.ylabel(_format_axis_label(res, is_ru))
                plt.legend(frameon=False)
                plt.grid(True, axis="y", alpha=0.25)
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                plt.close()
                return bytes(buf.getvalue())

        if base_type == "clustered_correlation":
            corr = res.get("correlation_matrix") if isinstance(res, dict) else None
            if isinstance(corr, dict) and isinstance(corr.get("values"), list) and isinstance(corr.get("variables"), list):
                vars_ = [str(v) for v in corr.get("variables")]
                vals = np.array(corr.get("values"), dtype=float)
                n = max(2, len(vars_))
                size = min(11.5, max(6.0, 0.35 * n))
                plt.figure(figsize=(size, size))
                ax = sns.heatmap(
                    vals,
                    vmin=-1,
                    vmax=1,
                    cmap=str(theme.get("correlation_heatmap_cmap") or "vlag"),
                    center=0,
                    square=True,
                    cbar=True,
                    xticklabels=vars_,
                    yticklabels=vars_,
                )
                ax.tick_params(axis="x", labelrotation=60, labelsize=8)
                ax.tick_params(axis="y", labelrotation=0, labelsize=8)
                plt.title("Кластерная корреляция" if is_ru else "Clustered Correlation")
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                plt.close()
                return bytes(buf.getvalue())

        if base_type == "cluster_profiles":
            embedding = res.get("embedding") if isinstance(res, dict) else None
            if isinstance(embedding, list) and embedding:
                df_embed = pd.DataFrame(embedding)
                if {"x", "y", "cluster"}.issubset(df_embed.columns):
                    x_num = pd.to_numeric(df_embed["x"], errors="coerce")
                    y_num = pd.to_numeric(df_embed["y"], errors="coerce")
                    df_embed = df_embed.assign(x=x_num, y=y_num)
                    df_embed = df_embed[np.isfinite(df_embed["x"]) & np.isfinite(df_embed["y"])]
                    if not df_embed.empty:
                        plt.figure(figsize=(7.8, 5.0))
                        cluster_ids = sorted([str(v) for v in df_embed["cluster"].astype(str).unique()], key=lambda x: str(x))
                        for idx, cluster_id in enumerate(cluster_ids):
                            sub = df_embed[df_embed["cluster"].astype(str) == cluster_id]
                            if sub.empty:
                                continue
                            plt.scatter(
                                sub["x"],
                                sub["y"],
                                s=18,
                                alpha=0.72,
                                color=palette[idx % len(palette)],
                                label=(f"Кластер {cluster_id}" if is_ru else f"Cluster {cluster_id}"),
                            )
                        plt.title("Профили кластеров (2D embedding)" if is_ru else "Cluster Profiles (2D embedding)")
                        plt.xlabel("PC1")
                        plt.ylabel("PC2")
                        if len(cluster_ids) <= 12:
                            plt.legend(frameon=False, ncol=2)
                        plt.grid(True, alpha=0.2)
                        buf = io.BytesIO()
                        plt.tight_layout()
                        plt.savefig(buf, format="png")
                        plt.close()
                        return bytes(buf.getvalue())

        if base_type == "external_validation":
            task = str(res.get("task") or "").strip().lower() if isinstance(res, dict) else ""
            roc = res.get("roc") if isinstance(res, dict) else None
            has_roc_plot = bool(
                isinstance(roc, dict)
                and isinstance(roc.get("plot_data"), list)
                and len(roc.get("plot_data")) > 0
            )
            if task == "classification" and not has_roc_plot:
                calibration = res.get("calibration") if isinstance(res, dict) else None
                curve = calibration.get("curve") if isinstance(calibration, dict) else None
                if isinstance(curve, list) and curve:
                    df_curve = pd.DataFrame(curve)
                    if {"x", "y"}.issubset(df_curve.columns):
                        x_num = pd.to_numeric(df_curve["x"], errors="coerce")
                        y_num = pd.to_numeric(df_curve["y"], errors="coerce")
                        mask = np.isfinite(x_num) & np.isfinite(y_num)
                        if int(mask.sum()) >= 2:
                            x_vals = x_num[mask].astype(float).tolist()
                            y_vals = y_num[mask].astype(float).tolist()
                            plt.figure(figsize=(7.6, 4.8))
                            plt.plot(
                                [0, 1],
                                [0, 1],
                                linestyle="--",
                                color=str(theme.get("diag_line") or "#64748b"),
                                linewidth=1.0,
                                label=("Идеальная калибровка" if is_ru else "Perfect calibration"),
                            )
                            plt.plot(
                                x_vals,
                                y_vals,
                                marker="o",
                                color=str(theme.get("accent") or "#8b5cf6"),
                                linewidth=2.0,
                                label=("Модель" if is_ru else "Model"),
                            )
                            brier = _safe_float(calibration.get("brier_score")) if isinstance(calibration, dict) else None
                            title = ("Калибровка модели" if is_ru else "Model Calibration")
                            if brier is not None:
                                title += f" (Brier={brier:.3f})"
                            plt.title(title)
                            plt.xlabel("Predicted probability")
                            plt.ylabel("Observed event rate")
                            plt.xlim(0, 1)
                            plt.ylim(0, 1)
                            plt.legend(frameon=False)
                            plt.grid(True, alpha=0.25)
                            buf = io.BytesIO()
                            plt.tight_layout()
                            plt.savefig(buf, format="png")
                            plt.close()
                            return bytes(buf.getvalue())

        plt.figure(figsize=(8, 5))

        plot_data = []
        plot_config = {}

        if isinstance(res, dict):
            roc = res.get("roc")
            if isinstance(roc, dict) and isinstance(roc.get("plot_data"), list) and roc.get("plot_data"):
                plot_data = roc.get("plot_data")
                plot_config = roc.get("plot_config") if isinstance(roc.get("plot_config"), dict) else {}
            else:
                plot_data = res.get("plot_data", [])
                plot_config = res.get("plot_config") if isinstance(res.get("plot_config"), dict) else {}

        if plot_data:
            df_plot = pd.DataFrame(plot_data)

            if "group" in df_plot.columns and "value" in df_plot.columns:
                sns.boxplot(
                    x="group",
                    y="value",
                    data=df_plot,
                    showfliers=False,
                    color=str(theme.get("box_fill") or "#f1f5f9"),
                    width=0.5,
                )
                sns.stripplot(
                    x="group",
                    y="value",
                    data=df_plot,
                    size=4,
                    alpha=0.6,
                    color=str(theme.get("primary") or "#0f172a"),
                )
                plt.title("Сравнение групп" if is_ru else "Group Comparison")
                plt.xlabel(_format_group_axis_label(res, is_ru))
                plt.ylabel(_format_axis_label(res, is_ru))

                comparisons_raw = None
                if isinstance(res, dict):
                    comparisons_raw = res.get("comparisons") or res.get("plot_comparisons") or res.get("post_hoc")

                comparisons = normalize_comparisons(comparisons_raw)
                if comparisons:
                    group_order = [str(g) for g in (df_plot["group"].dropna().unique().tolist() or [])]
                    group_index = {g: i for i, g in enumerate(group_order)}

                    values = df_plot["value"].dropna().astype(float)
                    if len(values) > 0:
                        min_val = float(values.min())
                        max_val = float(values.max())
                        y_range = (max_val - min_val) or 1.0
                        base_pad = y_range * 0.08
                        step_pad = y_range * 0.08
                        y_base = max_val + base_pad

                        ranges = []
                        placed = []
                        for c in comparisons:
                            ia = group_index.get(c.a)
                            ib = group_index.get(c.b)
                            if ia is None or ib is None:
                                continue
                            start = min(ia, ib)
                            end = max(ia, ib)

                            level = 0
                            while True:
                                taken = ranges[level] if level < len(ranges) else []
                                overlaps = any(not (end < r[0] or start > r[1]) for r in taken)
                                if not overlaps:
                                    break
                                level += 1
                            while level >= len(ranges):
                                ranges.append([])
                            ranges[level].append((start, end))
                            placed.append((start, end, level, c.p_value))

                        ax = plt.gca()
                        max_level = max((lvl for _, _, lvl, _ in placed), default=-1)
                        try:
                            y0, y1_lim = ax.get_ylim()
                            extra = (max_level + 2) * step_pad
                            ax.set_ylim(y0, max(y1_lim, max_val + base_pad + extra))
                        except Exception:
                            pass
                        for start, end, level, p_value in placed:
                            add_significance_bracket(
                                ax,
                                float(start),
                                float(end),
                                y_base + level * step_pad,
                                p_value,
                                h=0.02,
                                lw=1.2,
                                color=str(theme.get("primary") or "#0f172a"),
                            )

            elif "x" in df_plot.columns and "y" in df_plot.columns:
                if plot_config.get("type") == "line":
                    df_sorted = df_plot.sort_values("x")
                    plt.plot(df_sorted["x"], df_sorted["y"], color=str(theme.get("accent") or "#8b5cf6"), linewidth=2)
                    plt.plot([0, 1], [0, 1], linestyle="--", color=str(theme.get("diag_line") or "#64748b"), linewidth=1)
                    plt.xlim(0, 1)
                    plt.ylim(0, 1)
                    plt.title("ROC-кривая" if is_ru else "ROC Curve")
                    plt.xlabel("1 − специфичность" if is_ru else "1 − Specificity")
                    plt.ylabel("Чувствительность" if is_ru else "Sensitivity")
                else:
                    x_num = pd.to_numeric(df_plot["x"], errors="coerce")
                    y_num = pd.to_numeric(df_plot["y"], errors="coerce")
                    mask = np.isfinite(x_num) & np.isfinite(y_num)
                    x_vals = x_num[mask]
                    y_vals = y_num[mask]
                    if len(x_vals) > 800:
                        hb = plt.hexbin(
                            x_vals,
                            y_vals,
                            gridsize=45,
                            cmap=str(theme.get("hexbin_cmap") or "viridis"),
                            mincnt=1,
                        )
                        try:
                            plt.colorbar(hb)
                        except Exception:
                            pass
                    else:
                        scatter_color = palette[0]
                        sns.scatterplot(x=x_vals, y=y_vals, s=18, alpha=0.7, color=scatter_color)

                    try:
                        reg_color = palette[1] if len(palette) > 1 else palette[0]
                        sns.regplot(x=x_vals, y=y_vals, scatter=False, color=reg_color, line_kws={"linewidth": 2})
                    except Exception:
                        pass
                    plt.title("Корреляция" if is_ru else "Correlation Analysis")
                    plt.xlabel(str(res.get("x_label") or "X"))
                    plt.ylabel(str(res.get("y_label") or "Y"))

            elif "probability" in df_plot.columns and "time" in df_plot.columns and "group" in df_plot.columns:
                groups = df_plot["group"].unique()
                for idx, g in enumerate(groups):
                    sub = df_plot[df_plot["group"] == g]
                    plt.step(
                        sub["time"],
                        sub["probability"],
                        where="post",
                        color=palette[idx % len(palette)],
                        label=f"{('Группа' if is_ru else 'Group')} {g}",
                    )
                plt.ylim(0, 1.05)
                plt.legend()
                plt.title("Кривая Каплана — Мейера" if is_ru else "Kaplan-Meier Survival Curve")
                plt.xlabel("Время" if is_ru else "Time")
                plt.ylabel("Вероятность выживания" if is_ru else "Survival probability")

        else:
            plot_stats = res.get("plot_stats", {}) if isinstance(res, dict) else {}
            if plot_stats:
                groups = []
                means = []
                sems = []
                for g, s in plot_stats.items():
                    if not isinstance(s, dict):
                        continue
                    m = s.get("mean")
                    try:
                        m_f = float(m)
                        if not np.isfinite(m_f):
                            continue
                    except Exception:
                        continue
                    sem = s.get("sem")
                    if sem is None:
                        sd = s.get("sd")
                        n = s.get("count")
                        try:
                            if sd is not None and n is not None and float(n) > 1:
                                sem = float(sd) / float(np.sqrt(float(n)))
                        except Exception:
                            sem = None
                    try:
                        sem_f = float(sem) if sem is not None else 0.0
                        if not np.isfinite(sem_f):
                            sem_f = 0.0
                    except Exception:
                        sem_f = 0.0
                    groups.append(str(g))
                    means.append(m_f)
                    sems.append(sem_f)

                if groups:
                    bar_color = str(theme.get("bar_fill") or palette[0])
                    edge_color = str(theme.get("primary") or "#0f172a")
                    plt.bar(groups, means, yerr=sems, capsize=5, color=bar_color, edgecolor=edge_color, alpha=0.8)
                    plot_data = res.get("plot_data") if isinstance(res, dict) else None
                    if isinstance(plot_data, list) and plot_data:
                        group_index = {str(g): i for i, g in enumerate(groups)}
                        rng = np.random.default_rng(42)
                        xs_scatter = []
                        ys_scatter = []
                        for row in plot_data:
                            if not isinstance(row, dict):
                                continue
                            g = row.get("group")
                            v = row.get("value")
                            if g is None or v is None:
                                continue
                            try:
                                yv = float(v)
                            except Exception:
                                continue
                            gi = group_index.get(str(g))
                            if gi is None:
                                continue
                            xs_scatter.append(float(gi) + float(rng.uniform(-0.12, 0.12)))
                            ys_scatter.append(yv)
                        if xs_scatter:
                            plt.scatter(xs_scatter, ys_scatter, s=14, alpha=0.45, color=edge_color, zorder=3)
                plt.title("Сравнение средних (±SEM)" if is_ru else "Mean comparison (±SEM)")
            else:
                plt.text(
                    0.5,
                    0.5,
                    "Нет визуализации" if is_ru else "No Visualization Available",
                    ha="center",
                    va="center",
                    transform=plt.gca().transAxes,
                )

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close()
        return bytes(buf.getvalue())
    except Exception as e:
        logger.error(f"Plotting failed: {e}", exc_info=True)
        try:
            plt.close()
        except Exception:
            pass
        return b""

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

        self._add_overview()
        self._add_study_design()
        self._add_methods()

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
        deduped = _dedupe_step_payloads(raw_steps)

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
            self._add_editorial_index(grouped, ordered_targets)

        toc_map = {e["step_id"]: e["res"] for e in ordered_deduped if isinstance(e, dict) and isinstance(e.get("step_id"), str) and isinstance(e.get("res"), dict)}
        self._add_toc(toc_map)

        self._skip_table1_steps = self._add_table1_multi(ordered_deduped, step_meta_map)

        total_steps = len(raw_steps)
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
                "bootstrap_pipeline",
                "cluster_profiles",
                "external_validation",
            ]:
                self._add_analysis_section(res, step_id, dup_count=dup_count)
            elif rtype == "batch_compare_by_factor":
                self._add_longitudinal_section(res, step_id)
            elif rtype in {"batch_analysis", "timepoint_batch_analysis"}:
                self._add_batch_section(res, step_id)
            elif rtype == "responders":
                self._add_responder_section(res, step_id)
            elif rtype != "table_1":
                self._add_unknown_section(res, step_id)

        self._add_discussion_conclusion()
        self._add_limitations()
        self._add_run_log()

        self._add_footer()
        return "\n".join(self.html_parts)

    def _resolve_dataset_dir(self, dataset_id: str) -> Optional[str]:
        if not dataset_id:
            return None
        base = get_workspace_dir()
        ds_dir = os.path.join(base, "datasets", dataset_id)
        return ds_dir if os.path.isdir(ds_dir) else None

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r") as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

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

        design_html = f"""
        <div class="card" id="design">
            <h2>{'Дизайн исследования' if is_ru else 'Study Design'}</h2>
            <table>
                <tbody>
                    <tr><td><strong>{'Тип дизайна' if is_ru else 'Design type'}</strong></td><td>{html.escape(str(design.get('design_type') or '-'))}</td></tr>
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
            design_html += f"""
            <h3>{'Политика анализа' if is_ru else 'Analysis policy'}</h3>
            <table>
                <tbody>
                    <tr><td><strong>α</strong></td><td>{html.escape(str(policy.get('alpha') or '-'))}</td></tr>
                    <tr><td><strong>{'Поправка' if is_ru else 'Correction'}</strong></td><td>{html.escape(str(policy.get('multiplicity_correction') or '-'))}</td></tr>
                    <tr><td><strong>Post-hoc</strong></td><td>{html.escape(str(policy.get('post_hoc') or '-'))}</td></tr>
                </tbody>
            </table>
            """

        design_html += "</div>"
        self.html_parts.append(design_html)

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

        def _fmt_num(value: Any, digits: int = 2) -> str:
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
                return "<0.001" if p < 0.001 else f"{p:.3f}"
            except Exception:
                return "-"

        def _summary(stats: Dict[str, Any], use_mean: bool) -> str:
            n = stats.get("count")
            n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
            if use_mean:
                return f"{_fmt_num(stats.get('mean'))} ± {_fmt_num(stats.get('std'))} {n_s}".strip()
            return f"{_fmt_num(stats.get('median'))} [{_fmt_num(stats.get('q1'))}; {_fmt_num(stats.get('q3'))}] {n_s}".strip()

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

    def _add_toc(self, results: Dict[str, Any]):
        is_ru = bool(getattr(self, "is_ru", False))
        if not results:
            return
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
                items.append(f'<li><a href="#step-{step_id}">{step_id}</a> <span style="color:#64748b;">({rtype})</span></li>')
        elif isinstance(results, dict):
            for step_id, res in results.items():
                if not isinstance(step_id, str):
                    continue
                rtype = (res.get("type") if isinstance(res, dict) else None) or "result"
                items.append(f'<li><a href="#step-{step_id}">{step_id}</a> <span style="color:#64748b;">({rtype})</span></li>')
        html = f"""
        <div class="card" id="toc">
            <h2>{'Содержание' if is_ru else 'Contents'}</h2>
            <ol style="margin: 0; padding-left: 18px;">
                {''.join(items)}
            </ol>
        </div>
        """
        self.html_parts.append(html)

    def _add_editorial_index(self, grouped: Dict[str, Dict[str, List[Dict[str, Any]]]], ordered_targets: List[str]):
        is_ru = bool(getattr(self, "is_ru", False))
        if not isinstance(grouped, dict) or not grouped:
            return

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
                    if not isinstance(sid, str) or not sid:
                        continue
                    t = f"{html.escape(sid)}"
                    if isinstance(rtype, str) and rtype:
                        t += f" <span style=\"color:#64748b;\">({html.escape(rtype)})</span>"
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

    def _add_unknown_section(self, res: Dict[str, Any], step_id: str):
        is_ru = bool(getattr(self, "is_ru", False))
        rtype = (res.get("type") if isinstance(res, dict) else None) or "result"
        error = res.get("error") if isinstance(res, dict) else None
        title = f"{step_id} ({rtype})"
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

        def _fmt_num(value: Any, digits: int = 2) -> str:
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
            (("Среднее (SD)" if is_ru else "Mean (SD)"), lambda s: f"{_fmt_num((s or {}).get('mean'), 2)} ({_fmt_num((s or {}).get('std'), 2)})"),
            (
                ("95% ДИ (среднего)" if is_ru else "95% CI (Mean)"),
                lambda s: (
                    f"[{_fmt_num((s or {}).get('ci_95_low'), 2)}, {_fmt_num((s or {}).get('ci_95_high'), 2)}]"
                    if ((s or {}).get("ci_95_low") is not None and (s or {}).get("ci_95_high") is not None)
                    else "-"
                ),
            ),
            (
                ("Медиана [Q1, Q3]" if is_ru else "Median [Q1, Q3]"),
                lambda s: (
                    f"{_fmt_num((s or {}).get('median'), 2)} [{_fmt_num((s or {}).get('q1'), 2)}, {_fmt_num((s or {}).get('q3'), 2)}]"
                    if ((s or {}).get("median") is not None and (s or {}).get("q1") is not None and (s or {}).get("q3") is not None)
                    else "-"
                ),
            ),
            ("IQR", lambda s: _fmt_num((s or {}).get("iqr"), 2) if (s or {}).get("iqr") is not None else "-"),
            (
                ("Диапазон (min–max)" if is_ru else "Range (Min-Max)"),
                lambda s: (
                    f"{_fmt_num((s or {}).get('min'), 2)} - {_fmt_num((s or {}).get('max'), 2)}"
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

    def _add_analysis_section(self, res: Dict, step_id: str, dup_count: int = 1):
        is_ru = bool(getattr(self, "is_ru", False))
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
        if hasattr(method_obj, "name"):
            method_name = str(getattr(method_obj, "name") or "") or method_default
        elif isinstance(method_obj, dict):
            method_name = str(method_obj.get("name") or method_obj.get("id") or "") or method_default
        elif method_obj is None:
            method_name = method_default
        else:
            method_name = str(method_obj) or method_default
        method_id = _method_id_from_payload(res)
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

        target = res.get("target") or res.get("outcome")
        group_col = res.get("group_label") or res.get("group") or res.get("group_column")
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

        section_html = f"""
        <div class="card" id="step-{step_id}">
            <h2>{'Шаг анализа' if is_ru else 'Analysis Step'}: {step_id}</h2>
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
                </div>
            </div>
        """

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
                        def _fmt(v):
                            try:
                                if v is None:
                                    return "-"
                                f = float(v)
                                return f"{f:.2f}" if np.isfinite(f) else "-"
                            except Exception:
                                return "-"
                        rows.append(f"<tr><td>{g}</td><td>{t}</td><td>{_fmt(e)}</td><td>[{_fmt(lo)}, {_fmt(hi)}]</td><td>{str(int(n)) if isinstance(n,(int,float)) else '-'}</td></tr>")
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
                    def _fmt(v, d=3):
                        try:
                            if v is None:
                                return "-"
                            f = float(v)
                            return f"{f:.{d}f}" if np.isfinite(f) else "-"
                        except Exception:
                            return "-"
                    p_s = "< 0.001" if (isinstance(p,(int,float)) and float(p) < 0.001) else _fmt(p, 4)
                    rows.append(f"<tr><td>{term}</td><td class=\"stat-val\">{_fmt(coef)}</td><td>{_fmt(se)}</td><td class=\"stat-val\">{p_s}</td></tr>")
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

        if method_id == "bootstrap_pipeline":
            bootstrap = res.get("bootstrap") if isinstance(res.get("bootstrap"), dict) else {}
            mode = str(res.get("mode") or "").strip() or "-"
            statistic = str(res.get("statistic") or "").strip() or "-"
            ci_level = _safe_float(bootstrap.get("ci_level"))
            n_resamples = bootstrap.get("n_resamples")
            observed_effect = _safe_float(bootstrap.get("observed_effect"))
            ci_lo = _safe_float(res.get("effect_size_ci_lower"))
            ci_hi = _safe_float(res.get("effect_size_ci_upper"))
            dist_mean = _safe_float(bootstrap.get("distribution_mean"))
            dist_std = _safe_float(bootstrap.get("distribution_std"))
            groups = res.get("groups") if isinstance(res.get("groups"), list) else []
            n_left = res.get("n_left")
            n_right = res.get("n_right")

            section_html += f"""
                <h3>{'Bootstrap-устойчивость эффекта' if is_ru else 'Bootstrap Effect Stability'}</h3>
                <table>
                    <thead>
                        <tr><th>{'Параметр' if is_ru else 'Parameter'}</th><th>{'Значение' if is_ru else 'Value'}</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>{'Режим' if is_ru else 'Mode'}</td><td>{html.escape(mode)}</td></tr>
                        <tr><td>{'Статистика' if is_ru else 'Statistic'}</td><td>{html.escape(statistic)}</td></tr>
                        <tr><td>{'Bootstrap resamples'}</td><td>{int(n_resamples) if isinstance(n_resamples, (int, float)) else '-'}</td></tr>
                        <tr><td>{'CI уровень' if is_ru else 'CI level'}</td><td>{f"{ci_level:.3f}" if ci_level is not None else '-'}</td></tr>
                        <tr><td>{'Наблюдаемый эффект' if is_ru else 'Observed effect'}</td><td class="stat-val">{f"{observed_effect:.3f}" if observed_effect is not None else '-'}</td></tr>
                        <tr><td>{'CI эффекта' if is_ru else 'Effect CI'}</td><td>{f"[{ci_lo:.3f}, {ci_hi:.3f}]" if (ci_lo is not None and ci_hi is not None) else '-'}</td></tr>
                        <tr><td>{'Среднее bootstrap-распределения' if is_ru else 'Bootstrap distribution mean'}</td><td>{f"{dist_mean:.3f}" if dist_mean is not None else '-'}</td></tr>
                        <tr><td>{'SD bootstrap-распределения' if is_ru else 'Bootstrap distribution SD'}</td><td>{f"{dist_std:.3f}" if dist_std is not None else '-'}</td></tr>
                    </tbody>
                </table>
            """
            if len(groups) == 2:
                left = html.escape(str(groups[0]))
                right = html.escape(str(groups[1]))
                section_html += f"""
                <div style="margin-top: 8px; color: #475569; font-size: 12px;">
                    <strong>{'Сравниваемые группы' if is_ru else 'Compared groups'}:</strong>
                    {left} (n={int(n_left) if isinstance(n_left, (int, float)) else '-'}) vs
                    {right} (n={int(n_right) if isinstance(n_right, (int, float)) else '-'})
                </div>
                """

        if method_id == "cluster_profiles":
            n_obs = res.get("n_observations")
            n_vars = res.get("n_variables")
            n_clusters = res.get("n_clusters")
            silhouette = _safe_float(res.get("silhouette_score"))
            clusters_payload = res.get("clusters") if isinstance(res.get("clusters"), list) else []
            rows = []
            for row in clusters_payload[:24]:
                if not isinstance(row, dict):
                    continue
                cid = row.get("cluster")
                size = row.get("size")
                prop = _safe_float(row.get("proportion"))
                rows.append(
                    f"<tr><td>{html.escape(str(cid))}</td><td>{int(size) if isinstance(size, (int, float)) else '-'}</td><td>{f'{prop * 100.0:.1f}%' if prop is not None else '-'}</td></tr>"
                )

            section_html += f"""
                <h3>{'Профили кластеров' if is_ru else 'Cluster Profiles'}</h3>
                <div style="margin-top: 8px; color: #475569; font-size: 12px;">
                    <strong>N:</strong> {int(n_obs) if isinstance(n_obs, (int, float)) else '-'} •
                    <strong>{'Переменных' if is_ru else 'Variables'}:</strong> {int(n_vars) if isinstance(n_vars, (int, float)) else '-'} •
                    <strong>{'Кластеров' if is_ru else 'Clusters'}:</strong> {int(n_clusters) if isinstance(n_clusters, (int, float)) else '-'} •
                    <strong>Silhouette:</strong> {f"{silhouette:.3f}" if silhouette is not None else '-'}
                </div>
            """
            if rows:
                section_html += f"""
                <table>
                    <thead><tr><th>{'Кластер' if is_ru else 'Cluster'}</th><th>{'Размер' if is_ru else 'Size'}</th><th>{'Доля' if is_ru else 'Proportion'}</th></tr></thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
                """

        if method_id == "external_validation":
            internal_metrics = res.get("internal_metrics") if isinstance(res.get("internal_metrics"), dict) else {}
            external_metrics = res.get("external_metrics") if isinstance(res.get("external_metrics"), dict) else {}
            gap = res.get("generalization_gap") if isinstance(res.get("generalization_gap"), dict) else {}
            ext_ds = str(res.get("external_dataset_id") or "").strip()
            n_train = res.get("n_train")
            n_internal = res.get("n_internal_test")
            n_external = res.get("n_external")

            def _metric_row(label: str, key: str) -> str:
                i_val = _safe_float(internal_metrics.get(key))
                e_val = _safe_float(external_metrics.get(key))
                return (
                    "<tr>"
                    + f"<td>{html.escape(label)}</td>"
                    + f"<td class=\"stat-val\">{f'{i_val:.3f}' if i_val is not None else '-'}</td>"
                    + f"<td class=\"stat-val\">{f'{e_val:.3f}' if e_val is not None else '-'}</td>"
                    + "</tr>"
                )

            task = str(res.get("task") or "").strip().lower()
            metric_rows = ""
            if task == "classification":
                metric_rows = "".join(
                    [
                        _metric_row("AUC", "auc"),
                        _metric_row("Accuracy", "accuracy"),
                        _metric_row("Precision", "precision"),
                        _metric_row("Recall", "recall"),
                        _metric_row("F1", "f1"),
                    ]
                )
            else:
                metric_rows = "".join(
                    [
                        _metric_row("R2", "r_squared"),
                        _metric_row("RMSE", "rmse"),
                        _metric_row("MAE", "mae"),
                    ]
                )

            section_html += f"""
                <h3>{'Внешняя валидация' if is_ru else 'External Validation'}</h3>
                <div style="margin-top: 8px; color: #475569; font-size: 12px;">
                    <strong>{'Внешний датасет' if is_ru else 'External dataset'}:</strong> {html.escape(ext_ds or '-')} •
                    <strong>N train:</strong> {int(n_train) if isinstance(n_train, (int, float)) else '-'} •
                    <strong>N internal:</strong> {int(n_internal) if isinstance(n_internal, (int, float)) else '-'} •
                    <strong>N external:</strong> {int(n_external) if isinstance(n_external, (int, float)) else '-'}
                </div>
                <table>
                    <thead><tr><th>{'Метрика' if is_ru else 'Metric'}</th><th>{'Internal'}</th><th>{'External'}</th></tr></thead>
                    <tbody>{metric_rows}</tbody>
                </table>
            """

            if gap:
                gap_rows = []
                for k, v in list(gap.items())[:8]:
                    val = _safe_float(v)
                    gap_rows.append(
                        f"<tr><td>{html.escape(str(k))}</td><td class=\"stat-val\">{f'{val:.3f}' if val is not None else html.escape(str(v))}</td></tr>"
                    )
                if gap_rows:
                    section_html += f"""
                    <table>
                        <thead><tr><th>{'Generalization gap'}</th><th>{'Value'}</th></tr></thead>
                        <tbody>{''.join(gap_rows)}</tbody>
                    </table>
                    """

            cm = res.get("confusion_matrix") if isinstance(res.get("confusion_matrix"), dict) else {}
            cm_values = cm.get("values") if isinstance(cm.get("values"), list) else []
            cm_labels = cm.get("labels") if isinstance(cm.get("labels"), list) else []
            if len(cm_values) == 2 and all(isinstance(r, list) and len(r) == 2 for r in cm_values):
                l0 = html.escape(str(cm_labels[0])) if len(cm_labels) > 0 else "0"
                l1 = html.escape(str(cm_labels[1])) if len(cm_labels) > 1 else "1"
                section_html += f"""
                <h3>{'Матрица ошибок (external)' if is_ru else 'Confusion Matrix (external)'}</h3>
                <table>
                    <thead><tr><th></th><th>{l0}</th><th>{l1}</th></tr></thead>
                    <tbody>
                        <tr><td>{l0}</td><td>{html.escape(str(cm_values[0][0]))}</td><td>{html.escape(str(cm_values[0][1]))}</td></tr>
                        <tr><td>{l1}</td><td>{html.escape(str(cm_values[1][0]))}</td><td>{html.escape(str(cm_values[1][1]))}</td></tr>
                    </tbody>
                </table>
                """

            calibration = res.get("calibration") if isinstance(res.get("calibration"), dict) else {}
            brier = _safe_float(calibration.get("brier_score"))
            if brier is not None:
                section_html += (
                    f"<div style=\"margin-top: 8px; color: #475569; font-size: 12px;\"><strong>Brier score:</strong> {brier:.3f}</div>"
                )

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
                def _fmt(v: Any, d: int = 2) -> str:
                    try:
                        if v is None:
                            return "-"
                        f = float(v)
                        return f"{f:.{d}f}" if np.isfinite(f) else "-"
                    except Exception:
                        return "-"

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
                        a_s = f"{_fmt(r.get('a_center'))} [{_fmt(q1a)}; {_fmt(q3a)}] {a_n_s}".strip()
                        b_s = f"{_fmt(r.get('b_center'))} [{_fmt(q1b)}; {_fmt(q3b)}] {b_n_s}".strip()
                    else:
                        a_s = f"{_fmt(r.get('a_center'))} ± {_fmt(r.get('a_spread'))} {a_n_s}".strip()
                        b_s = f"{_fmt(r.get('b_center'))} ± {_fmt(r.get('b_spread'))} {b_n_s}".strip()

                    diff_s = _fmt(r.get("diff"))
                    diff_pct = r.get("diff_pct")
                    diff_pct_s = (f"{_fmt(diff_pct, 1)}%" if diff_pct is not None else "-")

                    eff = r.get("effect_size")
                    eff_name = r.get("effect_size_name")
                    eff_s = (f"{html.escape(str(eff_name or 'effect'))}={_fmt(eff)}" if eff is not None else "-")

                    rows.append(
                        "<tr>"
                        + f"<td><strong>{a} vs {b}</strong></td>"
                        + f"<td>{html.escape(a_s)}</td>"
                        + f"<td>{html.escape(b_s)}</td>"
                        + f"<td class=\"stat-val\">{diff_s}</td>"
                        + f"<td class=\"stat-val\">{diff_pct_s}</td>"
                        + f"<td class=\"stat-val\">{_fmt_p(r.get('p_value'))}</td>"
                        + f"<td class=\"stat-val\">{_fmt(r.get('bf10'), 3)}</td>"
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
                        def _fmt(v, d=3):
                            try:
                                if v is None:
                                    return "-"
                                f = float(v)
                                return f"{f:.{d}f}" if np.isfinite(f) else "-"
                            except Exception:
                                return "-"
                        p_s = "< 0.001" if (isinstance(p,(int,float)) and float(p) < 0.001) else _fmt(p, 4)
                        rows.append(f"<tr><td>{var}</td><td class=\"stat-val\">{_fmt(b)}</td><td>{_fmt(se)}</td><td class=\"stat-val\">{p_s}</td><td class=\"stat-val\">{_fmt(orv, 3) if orv is not None else '-'}</td></tr>")
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

            plot_stats = res.get("plot_stats")
            if isinstance(plot_stats, dict) and plot_stats:
                rows = []
                for g, s in plot_stats.items():
                    if not isinstance(s, dict):
                        continue
                    def _fmt(v):
                        try:
                            if v is None:
                                return "-"
                            f = float(v)
                            return f"{f:.2f}" if np.isfinite(f) else "-"
                        except Exception:
                            return "-"
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
                        mm = f"{_fmt(s.get('min'))} – {_fmt(s.get('max'))}"
                    rows.append(
                        f"<tr><td>{str(g)}</td><td class=\"stat-val\">{str(int(s.get('count'))) if isinstance(s.get('count'), (int, float)) else '-'}</td><td>{_fmt(s.get('mean'))}</td><td>{_fmt(s.get('sd'))}</td><td>{var_s}</td><td>{_fmt(s.get('median'))}</td><td>{_fmt(s.get('q1'))}</td><td>{_fmt(s.get('q3'))}</td><td>{iqr_s}</td><td>{mm}</td></tr>"
                    )
                if rows:
                    section_html += f"""
                    <h3>{'Описательная статистика по группам' if is_ru else 'Group Summary'}</h3>
                    <table>
                        <thead><tr><th>{'Группа' if is_ru else 'Group'}</th><th>n</th><th>{'Среднее' if is_ru else 'Mean'}</th><th>SD</th><th>{'Дисперсия' if is_ru else 'Variance'}</th><th>{'Медиана' if is_ru else 'Median'}</th><th>Q1</th><th>Q3</th><th>IQR</th><th>min–max</th></tr></thead>
                        <tbody>{''.join(rows)}</tbody>
                    </table>
                    """
        
        # Generate Plot
        img_b64 = self._generate_plot_image(res)
        if img_b64:
            section_html += f'<div class="plot-container"><img src="data:image/png;base64,{img_b64}" alt="Analysis Plot" /></div>'
            caption = _build_plot_caption(res if isinstance(res, dict) else {}, is_ru=is_ru)
            if caption:
                section_html += f'<div style="margin-top: 6px; color: #475569; font-size: 12px;">{html.escape(caption)}</div>'

        interpretation_html = _render_interpretation_html(res if isinstance(res, dict) else {}, is_ru=is_ru)
        if interpretation_html:
            section_html += interpretation_html
            
        section_html += "</div>"
        self.html_parts.append(section_html)

    def _add_longitudinal_section(self, res: Dict, step_id: str):
        is_ru = bool(getattr(self, "is_ru", False))
        html = f"""
        <div class="card">
            <h2>{'Продольный анализ' if is_ru else 'Longitudinal Analysis'}: {step_id}</h2>
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
                        slice_res.get('method', {}).get('name', '-')
                        if isinstance(slice_res.get('method'), dict)
                        else (str(getattr(slice_res.get('method'), 'name')) if hasattr(slice_res.get('method'), 'name') else str(slice_res.get('method') or '-'))
                    )}</td>
                    <td><span class="stat-val { 'sig-yes' if is_sig else 'sig-no' }">{p_display}</span></td>
                    <td>{ ('Различия есть' if is_ru else 'Difference Detected') if is_sig else ('Различий нет' if is_ru else 'No Difference') }</td>
                </tr>
            """
            
        html += "</tbody></table>"
        interpretation_html = _render_interpretation_html(res if isinstance(res, dict) else {}, is_ru=is_ru)
        if interpretation_html:
            html += interpretation_html
        html += "</div>"
        self.html_parts.append(html)

    def _add_batch_section(self, res: Dict[str, Any], step_id: str):
        is_ru = bool(getattr(self, "is_ru", False))
        alpha_val = _coerce_alpha(
            res.get("alpha") if isinstance(res, dict) else None,
            (self.data or {}).get("alpha") if isinstance(self.data, dict) else None,
        )
        group_col = (res.get("group") or res.get("group_column")) if isinstance(res, dict) else None
        multiplicity = res.get("multiplicity_correction") if isinstance(res, dict) else None
        post_hoc = res.get("post_hoc") if isinstance(res, dict) else None
        post_hoc_correction = res.get("post_hoc_correction") if isinstance(res, dict) else None
        step_type = str(res.get("type") or "") if isinstance(res, dict) else ""

        def _fmt_num(value: Any, digits: int = 3) -> str:
            try:
                if value is None:
                    return "-"
                f = float(value)
                return f"{f:.{digits}f}" if np.isfinite(f) else "-"
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

        def _fmt_group_stats(group_stats: Any, label: str) -> str:
            if not isinstance(group_stats, dict):
                return "-"
            stats = group_stats.get(label)
            if not isinstance(stats, dict):
                return "-"
            mean = _fmt_num(stats.get("mean"), 2)
            sd = _fmt_num(stats.get("sd"), 2)
            med = _fmt_num(stats.get("median"), 2)
            q1 = _fmt_num(stats.get("q1"), 2)
            q3 = _fmt_num(stats.get("q3"), 2)
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
                method = html.escape(str(row.get("method") or "-"))
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
            <h2>{title}: {html.escape(step_id)}</h2>
            {(
                f"<div style='margin-top: -4px; color: #475569; font-size: 12px;'><strong>{'Группировка' if is_ru else 'Group'}:</strong> {html.escape(str(group_col))}</div>"
                if group_col else ""
            )}
            <div style=\"margin-top: 4px; color: #475569; font-size: 12px;\">
                <strong>{'Альфа' if is_ru else 'Alpha'}:</strong> {_fmt_num(alpha_val, 3)}
                {(
                    f" • <strong>{'Поправка' if is_ru else 'Correction'}:</strong> {html.escape(str(multiplicity))}"
                    if multiplicity else ""
                )}
                {(
                    f" • <strong>{'Post-hoc' if not is_ru else 'Пост-хок'}:</strong> "
                    + html.escape(str(post_hoc))
                    + (
                        f" ({html.escape(str(post_hoc_correction))})"
                        if post_hoc_correction and str(post_hoc_correction).strip().lower() != "none"
                        else ""
                    )
                    if post_hoc and str(post_hoc).strip().lower() != "none"
                    else ""
                )}
            </div>
        """

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
                section_html += _render_rows(
                    rows_payload,
                    title=("Точка" if is_ru else "Slice") + f": {slice_key}",
                )

        interpretation_html = _render_interpretation_html(res if isinstance(res, dict) else {}, is_ru=is_ru)
        if interpretation_html:
            section_html += interpretation_html
        section_html += "</div>"
        self.html_parts.append(section_html)

    def _add_responder_section(self, res: Dict, step_id: str):
        is_ru = bool(getattr(self, "is_ru", False))
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
            <h2>{'Анализ респондеров' if is_ru else 'Responder Analysis'}: {step_id}</h2>
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

        interpretation_html = _render_interpretation_html(res if isinstance(res, dict) else {}, is_ru=is_ru)
        if interpretation_html:
            html += interpretation_html
        html += "</div>"
        self.html_parts.append(html)

    def _add_footer(self):
        is_ru = bool(getattr(self, "is_ru", False))
        self.html_parts.append(f"""
        <div style="margin-top: 50px; color: #888; text-align: center; font-size: 0.8em; border-top: 1px solid #eee; padding-top: 20px;">
            {('Сформировано платформой AI-биостатистики' if is_ru else 'Generated by AI Biostatistics Platform')}
        </div>
        </body></html>
        """)

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

def generate_protocol_docx_report(
    run_data: Dict[str, Any],
    dataset_name: str = "Dataset",
    style: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> bytes:
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches, Pt
    import re
    run_data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})

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

    def _txt(value: Any) -> str:
        return "-" if value is None else str(value)

    style_key = str(style or "gost").strip().lower()
    is_ru = style_key in {"gost"}

    density = _normalize_report_density((options or {}).get("density"))

    font_name = "Calibri"
    base_pt = 11
    if style_key in {"gost", "apa7", "editorial"}:
        font_name = "Times New Roman"
        base_pt = 12
    if style_key == "gost":
        base_pt = 14
    if style_key == "brutal":
        font_name = "Courier New"
        base_pt = 10

    if density == "compact":
        base_pt = max(9, base_pt - 1)
    elif density == "spacious":
        base_pt = min(16, base_pt + 1)

    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = font_name
    normal.font.size = Pt(base_pt)
    normal.paragraph_format.space_after = Pt(6 if density != "compact" else 3)

    for style_name, size in [("Title", base_pt + 8), ("Heading 1", base_pt + 4), ("Heading 2", base_pt + 2), ("Heading 3", base_pt + 1)]:
        try:
            st = doc.styles[style_name]
            st.font.name = font_name
            st.font.size = Pt(size)
        except Exception:
            pass

    doc.add_heading("Результаты статистического анализа" if is_ru else "Statistical Analysis Results", level=0)
    doc.add_paragraph(("Набор данных" if is_ru else "Dataset") + f": {dataset_name}")
    protocol_name = run_data.get("protocol_name") if isinstance(run_data, dict) else None
    if protocol_name:
        doc.add_paragraph(("Протокол" if is_ru else "Protocol") + f": {protocol_name}")
    doc.add_paragraph(("Дата" if is_ru else "Date") + f": {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

    dataset_id = run_data.get("dataset_id") if isinstance(run_data, dict) else None
    study_design = None
    design_warning = None
    if dataset_id:
        try:
            base_dir = get_workspace_dir()
            ds_dir = os.path.join(base_dir, "datasets", str(dataset_id))
            study_path = os.path.join(ds_dir, "processed", "study_design.json")
            if os.path.exists(study_path):
                with open(study_path, "r", encoding="utf-8") as f:
                    study_design = json.load(f)
            else:
                design_warning = (
                    "Предупреждение: файл study_design.json не найден. Раздел Design неполный."
                    if is_ru
                    else "Warning: study_design.json not found. Design section is incomplete."
                )
        except Exception:
            study_design = None
            design_warning = (
                "Предупреждение: не удалось прочитать study_design.json. Раздел Design неполный."
                if is_ru
                else "Warning: failed to read study_design.json. Design section is incomplete."
            )
    else:
        design_warning = (
            "Предупреждение: dataset_id отсутствует. Раздел Design неполный."
            if is_ru
            else "Warning: dataset_id is missing. Design section is incomplete."
        )

    doc.add_heading("Дизайн исследования" if is_ru else "Study Design", level=1)
    design_rendered = False
    if isinstance(study_design, dict):
        design = study_design.get("design") if isinstance(study_design.get("design"), dict) else {}
        policy = study_design.get("analysis_policy") if isinstance(study_design.get("analysis_policy"), dict) else {}

        if design:
            design_rendered = True
            doc.add_paragraph(("Тип дизайна" if is_ru else "Design type") + f": {_txt(design.get('design_type'))}")
            if design.get("group_column"):
                doc.add_paragraph(("Группировка" if is_ru else "Group") + f": {_txt(design.get('group_column'))}")
            if design.get("time_column"):
                doc.add_paragraph(("Время/визит" if is_ru else "Time") + f": {_txt(design.get('time_column'))}")
            if design.get("subject_column"):
                doc.add_paragraph(("ID субъекта" if is_ru else "Subject ID") + f": {_txt(design.get('subject_column'))}")

            outcomes = design.get("outcomes")
            if isinstance(outcomes, list) and outcomes:
                doc.add_paragraph(("Числовые исходы" if is_ru else "Numeric outcomes") + f": {', '.join([_txt(o) for o in outcomes[:20]])}")

            cat_outcomes = design.get("categorical_outcomes")
            if isinstance(cat_outcomes, list) and cat_outcomes:
                doc.add_paragraph(("Категориальные исходы" if is_ru else "Categorical outcomes") + f": {', '.join([_txt(o) for o in cat_outcomes[:15]])}")

            endpoint_groups = design.get("endpoint_groups") if isinstance(design.get("endpoint_groups"), list) else []
            if endpoint_groups:
                doc.add_paragraph("Endpoint-группы по визитам:" if is_ru else "Endpoint groups by visit:")
                for item in endpoint_groups[:12]:
                    if not isinstance(item, dict):
                        continue
                    ep = _txt(item.get("endpoint") or "endpoint")
                    tps = item.get("timepoints") if isinstance(item.get("timepoints"), list) else []
                    tp_line = ", ".join([_txt(t) for t in tps]) if tps else "-"
                    doc.add_paragraph(f"• {ep}: {tp_line}")

        if policy:
            design_rendered = True
            alpha = policy.get("alpha")
            multiplicity = policy.get("multiplicity_correction")
            post_hoc = policy.get("post_hoc")
            doc.add_paragraph(("Политика анализа" if is_ru else "Analysis policy") + ":")
            if alpha is not None:
                doc.add_paragraph(f"• α={_txt(alpha)}")
            if multiplicity:
                doc.add_paragraph(f"• multiplicity={_txt(multiplicity)}")
            if post_hoc:
                doc.add_paragraph(f"• post-hoc={_txt(post_hoc)}")

    if not design_rendered:
        warning_line = design_warning or (
            "Предупреждение: раздел Design не заполнен."
            if is_ru
            else "Warning: Design section is empty."
        )
        doc.add_paragraph(warning_line)

    methods_summary = _extract_report_methods(run_data if isinstance(run_data, dict) else {}, is_ru=is_ru)
    method_rows = methods_summary.get("rows") if isinstance(methods_summary.get("rows"), list) else []
    missing_method_steps = methods_summary.get("missing_inferential_steps") if isinstance(methods_summary.get("missing_inferential_steps"), list) else []

    doc.add_heading("Методы" if is_ru else "Methods", level=1)
    if method_rows:
        methods_table = doc.add_table(rows=1, cols=4)
        m_hdr = methods_table.rows[0].cells
        m_hdr[0].text = "Метод" if is_ru else "Method"
        m_hdr[1].text = "Шагов" if is_ru else "Steps"
        m_hdr[2].text = "ID шагов" if is_ru else "Step IDs"
        m_hdr[3].text = "Показатели" if is_ru else "Targets"
        for row in method_rows:
            rr = methods_table.add_row().cells
            rr[0].text = _txt(row.get("method"))
            rr[1].text = _txt(row.get("count"))
            rr[2].text = ", ".join([_txt(x) for x in (row.get("steps") or [])[:8]]) or "-"
            rr[3].text = ", ".join([_txt(x) for x in (row.get("targets") or [])[:10]]) or "-"
    else:
        doc.add_paragraph(
            "Методы не определены: в результатах нет исполнимых аналитических шагов."
            if is_ru
            else "Methods are unavailable: no analyzable execution steps were found."
        )

    if missing_method_steps:
        preview = ", ".join([str(x) for x in missing_method_steps[:6]])
        if len(missing_method_steps) > 6:
            preview += ", ..."
        doc.add_paragraph(
            ("Предупреждение: отсутствует metadata метода для шагов: " if is_ru else "Warning: method metadata is missing for steps: ")
            + preview
        )

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

    def _extract_target(meta: Dict[str, Any], res: Dict[str, Any]) -> Optional[str]:
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
    deduped = _dedupe_step_payloads(raw_steps)
    total_steps = len(raw_steps)
    unique_steps = len(deduped)
    removed = max(0, total_steps - unique_steps)

    table1_rows: List[Dict[str, Any]] = []
    table1_groups: List[str] = []
    table1_group_col: Optional[str] = None
    table1_pmap: Dict[str, Dict[str, Any]] = {}

    for e in deduped:
        step_id = e.get("step_id") if isinstance(e, dict) else None
        res = e.get("res") if isinstance(e, dict) else None
        if not isinstance(step_id, str) or not isinstance(res, dict):
            continue
        if res.get("type") == "table_1":
            stats = res.get("data")
            if not isinstance(stats, dict) or not stats:
                continue
            meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
            meta = meta if isinstance(meta, dict) else {}
            target = _extract_target(meta, res) or step_id
            if not target:
                continue
            if not table1_groups:
                table1_groups = [k for k in stats.keys() if k != "overall"]
            if table1_group_col is None:
                cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
                table1_group_col = cfg.get("group")
            table1_rows.append({"target": target, "stats": stats})

    for e in deduped:
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
        table1_pmap.setdefault(str(g), {})
        for it in items:
            if not isinstance(it, dict):
                continue
            target = it.get("target") or it.get("outcome")
            if not target:
                continue
            table1_pmap[str(g)][str(target)] = {
                "p_raw": it.get("p_value"),
                "p_adj": it.get("p_value_adj"),
            }

    skip_table1_steps = False
    if len(table1_rows) >= 2 and table1_groups:
        skip_table1_steps = True
        doc.add_heading("Таблица 1. Описательная статистика (сводная)" if is_ru else "Table 1. Descriptive statistics (summary)", level=1)

        any_adj = False
        for g in table1_pmap.values():
            for v in g.values():
                if isinstance(v, dict) and v.get("p_adj") is not None:
                    any_adj = True
                    break

        header_cols = 2 + len(table1_groups) + 1  # variable + groups + overall + p
        table = doc.add_table(rows=1, cols=header_cols)
        hdr = table.rows[0].cells
        hdr[0].text = "Показатель" if is_ru else "Variable"
        for idx, g in enumerate(table1_groups):
            hdr[idx + 1].text = str(g)
        hdr[len(table1_groups) + 1].text = "Итого" if is_ru else "Overall"
        hdr[len(table1_groups) + 2].text = "p(adj)" if any_adj else "p"

        def _summary(stats: Dict[str, Any], use_mean: bool) -> str:
            n = stats.get("count")
            n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
            if use_mean:
                return f"{_fmt_num(stats.get('mean'), 2)} ± {_fmt_num(stats.get('std'), 2)} {n_s}".strip()
            return f"{_fmt_num(stats.get('median'), 2)} [{_fmt_num(stats.get('q1'), 2)}; {_fmt_num(stats.get('q3'), 2)}] {n_s}".strip()

        for row in table1_rows:
            stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
            all_normal = True
            for g in table1_groups:
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

            r = table.add_row().cells
            r[0].text = _txt(row.get("target"))
            for idx, g in enumerate(table1_groups):
                r[idx + 1].text = _summary(stats.get(g, {}), all_normal)
            r[len(table1_groups) + 1].text = _summary(stats.get("overall", {}), all_normal)
            p_val = None
            if table1_group_col and table1_group_col in table1_pmap:
                p_info = table1_pmap.get(table1_group_col, {}).get(str(row.get("target")))
                if isinstance(p_info, dict):
                    p_val = p_info.get("p_adj") if p_info.get("p_adj") is not None else p_info.get("p_raw")
            r[len(table1_groups) + 2].text = _fmt_p(p_val)

        # Append categorical variables (counts and %)
        try:
            if dataset_id and table1_group_col:
                base_dir = get_workspace_dir()
                ds_dir = os.path.join(base_dir, "datasets", str(dataset_id))
                study_path = os.path.join(ds_dir, "processed", "study_design.json")
                cat_cols = []
                if os.path.exists(study_path):
                    with open(study_path, "r", encoding="utf-8") as f:
                        sd = json.load(f)
                    if isinstance(sd, dict):
                        design = sd.get("design") if isinstance(sd.get("design"), dict) else {}
                        policy = sd.get("analysis_policy") if isinstance(sd.get("analysis_policy"), dict) else {}
                        cat_cols = design.get("categorical_outcomes") if isinstance(design.get("categorical_outcomes"), list) else []
                        max_cat = int(policy.get("max_table1_categorical") or 40)
                    else:
                        max_cat = 40
                else:
                    max_cat = 40

                parquet_path = os.path.join(ds_dir, "processed", f"{dataset_id}.parquet")
                use_cols = [table1_group_col] + [c for c in cat_cols if c != table1_group_col]
                use_cols = list(dict.fromkeys([c for c in use_cols if c]))
                if os.path.exists(parquet_path) and use_cols:
                    df_cat = pd.read_parquet(parquet_path, columns=use_cols)
                    df_cat = df_cat[df_cat[table1_group_col].notna()]
                    if not df_cat.empty:
                        group_series = df_cat[table1_group_col].astype(str)
                        group_vals = [str(g) for g in table1_groups]
                        group_totals = {str(g): int(df_cat[group_series == str(g)].shape[0]) for g in group_vals}
                        overall_total = int(df_cat.shape[0])

                        def _fmt_cnt_pct(count: int, total: int) -> str:
                            if total <= 0:
                                return "-"
                            pct = (float(count) / float(total)) * 100.0
                            return f"{int(count)} ({pct:.1f}%)"

                        def _bold_cell(cell):
                            try:
                                if cell.paragraphs and cell.paragraphs[0].runs:
                                    cell.paragraphs[0].runs[0].bold = True
                            except Exception:
                                pass

                        for col in cat_cols[:max_cat]:
                            if col not in df_cat.columns:
                                continue
                            series = df_cat[col].fillna("Missing").astype(str)
                            overall_counts = series.value_counts(dropna=False)
                            categories = [str(c) for c in overall_counts.index.tolist()]
                            if not categories:
                                continue

                            p_val = None
                            if table1_group_col in table1_pmap:
                                p_info = table1_pmap.get(table1_group_col, {}).get(str(col))
                                if isinstance(p_info, dict):
                                    p_val = p_info.get("p_adj") if p_info.get("p_adj") is not None else p_info.get("p_raw")

                            # Variable header row
                            r = table.add_row().cells
                            r[0].text = _txt(col)
                            _bold_cell(r[0])
                            for idx in range(len(table1_groups) + 1):
                                r[idx + 1].text = ""
                            r[len(table1_groups) + 2].text = _fmt_p(p_val)

                            for cat in categories[:30]:
                                rr = table.add_row().cells
                                rr[0].text = f"  {cat}"
                                for idx, g in enumerate(group_vals):
                                    cnt = int(df_cat[(group_series == str(g)) & (df_cat[col].fillna('Missing').astype(str) == cat)].shape[0])
                                    rr[idx + 1].text = _fmt_cnt_pct(cnt, group_totals.get(str(g), 0))
                                cnt_overall = int(overall_counts.get(cat, 0))
                                rr[len(table1_groups) + 1].text = _fmt_cnt_pct(cnt_overall, overall_total)
                                rr[len(table1_groups) + 2].text = ""
        except Exception:
            pass

        doc.add_paragraph(
            "Примечание: если нормальность нарушена, используется медиана [Q1; Q3], иначе среднее ± SD."
            if is_ru
            else "Note: non-normal variables use median [Q1; Q3], otherwise mean ± SD."
        )

    doc.add_paragraph(("Шагов (всего)" if is_ru else "Steps (total)") + f": {total_steps}")
    doc.add_paragraph(("Шагов (уникальных)" if is_ru else "Steps (unique)") + f": {unique_steps}")
    doc.add_paragraph(("Свернуто повторов" if is_ru else "Duplicates collapsed") + f": {removed}")

    by_type = Counter([str((e.get("res") or {}).get("type") or "result") for e in deduped if isinstance(e, dict)])
    if by_type:
        doc.add_paragraph(
            ("Состав по типам" if is_ru else "By type")
            + ": "
            + ", ".join(
                [
                    f"{k}={int(v)}"
                    for k, v in sorted(by_type.items(), key=lambda x: (-int(x[1]), str(x[0])))
                ]
            )
        )

    steps = deduped
    for idx, e in enumerate(steps):
        step_id = e.get("step_id") if isinstance(e, dict) else None
        res = e.get("res") if isinstance(e, dict) else None
        dup_count = int(e.get("dup_count") or 1) if isinstance(e, dict) else 1
        if not isinstance(step_id, str) or not isinstance(res, dict):
            continue

        suffix = f" (×{dup_count})" if dup_count > 1 else ""
        doc.add_heading(("Шаг" if is_ru else "Step") + f": {step_id}{suffix}", level=1)

        step_meta = step_meta_map.get(step_id) if isinstance(step_id, str) else None
        step_meta = step_meta if isinstance(step_meta, dict) else {}
        task = _extract_task(step_meta)
        visit = _extract_visit(step_id, step_meta, res if isinstance(res, dict) else {})
        group_levels = _extract_groups(res if isinstance(res, dict) else {})

        if task:
            doc.add_paragraph(("Задача" if is_ru else "Task") + f": {task}")
        if visit:
            doc.add_paragraph(("Точка" if is_ru else "Timepoint") + f": {visit}")
        if group_levels:
            if len(group_levels) == 2:
                grp_s = f"{group_levels[0]} vs {group_levels[1]}"
            else:
                grp_s = ", ".join(group_levels)
            doc.add_paragraph(("Сравниваемые группы" if is_ru else "Compared groups") + f": {grp_s}")

        if not isinstance(res, dict):
            doc.add_paragraph("Нет структурированного результата" if is_ru else "No structured result")
            continue

        if res.get("type") == "table_1":
            if skip_table1_steps:
                continue
            stats_map = res.get("data", {})
            if isinstance(stats_map, dict) and stats_map:
                groups = [k for k in stats_map.keys() if k != "overall"]
                cols = 2 + len(groups)
                table = doc.add_table(rows=1, cols=cols)
                hdr = table.rows[0].cells
                hdr[0].text = "Показатель"
                for i, g in enumerate(groups):
                    n = _txt(stats_map.get(g, {}).get("count"))
                    hdr[i + 1].text = f"{g} (n={n})"
                overall_n = _txt(stats_map.get("overall", {}).get("count"))
                hdr[-1].text = f"Итого (n={overall_n})"

                def _cell_for(metric_key: str, s: Dict[str, Any]) -> str:
                    if metric_key == "mean_sd":
                        return f"{_fmt_num(s.get('mean'), 2)} ({_fmt_num(s.get('std'), 2)})"
                    if metric_key == "ci_95":
                        return f"[{_fmt_num(s.get('ci_95_low'), 2)}, {_fmt_num(s.get('ci_95_high'), 2)}]"
                    if metric_key == "median_q1_q3":
                        return f"{_fmt_num(s.get('median'), 2)} [{_fmt_num(s.get('q1'), 2)}, {_fmt_num(s.get('q3'), 2)}]"
                    if metric_key == "iqr":
                        return _fmt_num(s.get("iqr"), 2)
                    if metric_key == "min_max":
                        return f"{_fmt_num(s.get('min'), 2)} – {_fmt_num(s.get('max'), 2)}"
                    if metric_key == "shapiro":
                        return _fmt_p(s.get("shapiro_p"))
                    return "-"

                metrics = [
                    ("Mean (SD)", "mean_sd"),
                    ("95% CI (Mean)", "ci_95"),
                    ("Median [Q1, Q3]", "median_q1_q3"),
                    ("IQR", "iqr"),
                    ("Range (Min-Max)", "min_max"),
                    ("Normality (Shapiro p)", "shapiro"),
                ]

                for label, key in metrics:
                    row = table.add_row().cells
                    row[0].text = label
                    for i, g in enumerate(groups):
                        row[i + 1].text = _cell_for(key, stats_map.get(g, {}) or {})
                    row[-1].text = _cell_for(key, stats_map.get("overall", {}) or {})
            continue

        if res.get("type") == "responders":
            outcome = res.get("outcome")
            baseline = res.get("baseline")
            baseline_time = baseline.get("time") if isinstance(baseline, dict) else None
            threshold = res.get("threshold")
            direction = res.get("direction")

            if outcome:
                doc.add_paragraph(("Показатель" if is_ru else "Outcome") + f": {_txt(outcome)}")
            head = []
            if baseline_time is not None:
                head.append(("база" if is_ru else "baseline") + f"={_txt(baseline_time)}")
            if threshold is not None:
                head.append(("порог" if is_ru else "threshold") + f"={_txt(threshold)}")
            if direction:
                head.append(("направление" if is_ru else "direction") + f"={_txt(direction)}")
            if head:
                doc.add_paragraph(" • ".join(head))

            contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
            if contract:
                labels = {
                    "claim": "Статистический вывод" if is_ru else "Statistical claim",
                    "evidence": "Доказательная база" if is_ru else "Evidence",
                    "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                    "limitations": "Ограничения" if is_ru else "Limitations",
                    "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                }
                doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                    text = str(contract.get(key) or "").strip()
                    if text:
                        doc.add_paragraph(f"{labels[key]}: {text}")
            else:
                fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                if isinstance(fallback, str) and fallback.strip():
                    doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                    doc.add_paragraph(fallback.strip())

            continue

        def _render_batch_step(batch_res: Dict[str, Any], title: Optional[str] = None) -> None:
            alpha_val = _coerce_alpha(
                batch_res.get("alpha"),
                run_data.get("alpha") if isinstance(run_data, dict) else None,
            )

            group_col = batch_res.get("group") or batch_res.get("group_column") or ""
            multiplicity = batch_res.get("multiplicity_correction")
            post_hoc = batch_res.get("post_hoc")
            post_hoc_correction = batch_res.get("post_hoc_correction")

            rows_payload = _collect_batch_inferential_rows(batch_res.get("items"), alpha_val)
            rows = rows_payload.get("rows") if isinstance(rows_payload, dict) else []
            rows = rows if isinstance(rows, list) else []
            sig_count = int(rows_payload.get("sig_count") or 0) if isinstance(rows_payload, dict) else 0
            group_labels = rows_payload.get("group_labels") if isinstance(rows_payload, dict) else None

            if title:
                doc.add_heading(title, level=2)

            if group_col:
                doc.add_paragraph(("Группировка" if is_ru else "Group") + f": {_txt(group_col)}")
            doc.add_paragraph(("Альфа" if is_ru else "Alpha") + f": {_txt(alpha_val)}")
            if multiplicity:
                doc.add_paragraph(("Поправка" if is_ru else "Correction") + f": {_txt(multiplicity)}")
            if post_hoc and post_hoc != "none":
                ph = _txt(post_hoc)
                if post_hoc_correction and post_hoc_correction != "none":
                    ph = f"{ph} ({_txt(post_hoc_correction)})"
                doc.add_paragraph(("Post-hoc" if not is_ru else "Пост-хок") + f": {ph}")
            doc.add_paragraph(("Показателей" if is_ru else "Targets") + f": {_txt(len(rows))}")
            doc.add_paragraph(("Значимых" if is_ru else "Significant") + f": {_txt(sig_count)}")

            cols = 5
            has_group_stats = bool(group_labels and len(group_labels) == 2)
            if has_group_stats:
                cols = 7
            table = doc.add_table(rows=1, cols=cols)
            hdr = table.rows[0].cells
            hdr[0].text = "Показатель" if is_ru else "Target"
            if has_group_stats:
                hdr[1].text = f"{group_labels[0]}: M±SD; Me[Q1;Q3]"
                hdr[2].text = f"{group_labels[1]}: M±SD; Me[Q1;Q3]"
                hdr[3].text = "p"
                hdr[4].text = "q" if not is_ru else "p(adj)"
                hdr[5].text = "Значимо" if is_ru else "Sig"
                hdr[6].text = "Тест" if is_ru else "Test"
            else:
                hdr[1].text = "p"
                hdr[2].text = "q" if not is_ru else "p(adj)"
                hdr[3].text = "Значимо" if is_ru else "Sig"
                hdr[4].text = "Тест" if is_ru else "Test"

            def _fmt_group_stats(stats: Any) -> str:
                if not isinstance(stats, dict):
                    return "-"
                mean = _fmt_num(stats.get("mean"), 2)
                sd = _fmt_num(stats.get("sd"), 2)
                med = _fmt_num(stats.get("median"), 2)
                q1 = _fmt_num(stats.get("q1"), 2)
                q3 = _fmt_num(stats.get("q3"), 2)
                n = stats.get("count")
                n_s = f"n={int(n)}" if isinstance(n, (int, float)) else ""
                return f"{mean} ± {sd}; {med} [{q1}; {q3}] {n_s}".strip()

            for r in rows:
                row = table.add_row().cells
                row[0].text = _txt(r.get("target"))
                if has_group_stats:
                    group_stats = r.get("group_stats") if isinstance(r, dict) else None
                    row[1].text = _fmt_group_stats(group_stats.get(group_labels[0]) if isinstance(group_stats, dict) else None)
                    row[2].text = _fmt_group_stats(group_stats.get(group_labels[1]) if isinstance(group_stats, dict) else None)
                    row[3].text = _fmt_p(r.get("p_raw"))
                    row[4].text = _fmt_p(r.get("p_adj"))
                    row[5].text = ("да" if is_ru else "yes") if r.get("sig") else ("нет" if is_ru else "no")
                    row[6].text = _txt(r.get("method"))
                else:
                    row[1].text = _fmt_p(r.get("p_raw"))
                    row[2].text = _fmt_p(r.get("p_adj"))
                    row[3].text = ("да" if is_ru else "yes") if r.get("sig") else ("нет" if is_ru else "no")
                    row[4].text = _txt(r.get("method"))

        if res.get("type") == "batch_analysis":
            _render_batch_step(res)
            contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
            if contract:
                labels = {
                    "claim": "Статистический вывод" if is_ru else "Statistical claim",
                    "evidence": "Доказательная база" if is_ru else "Evidence",
                    "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                    "limitations": "Ограничения" if is_ru else "Limitations",
                    "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                }
                doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                    text = str(contract.get(key) or "").strip()
                    if text:
                        doc.add_paragraph(f"{labels[key]}: {text}")
            else:
                fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                if isinstance(fallback, str) and fallback.strip():
                    doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                    doc.add_paragraph(fallback.strip())
            continue

        if res.get("type") == "timepoint_batch_analysis":
            split_by = res.get("split_by")
            group_col = res.get("group")
            if group_col:
                doc.add_paragraph(("Группировка" if is_ru else "Group") + f": {_txt(group_col)}")
            if split_by:
                doc.add_paragraph(("Разбиение" if is_ru else "Split by") + f": {_txt(split_by)}")

            slices = res.get("slices")
            slices = slices if isinstance(slices, dict) else {}
            for slice_key in sorted(slices.keys(), key=lambda x: str(x)):
                slice_res = slices.get(slice_key)
                if not isinstance(slice_res, dict):
                    continue
                _render_batch_step(slice_res, title=("Точка" if is_ru else "Slice") + f": {_txt(slice_key)}")

            contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
            if contract:
                labels = {
                    "claim": "Статистический вывод" if is_ru else "Statistical claim",
                    "evidence": "Доказательная база" if is_ru else "Evidence",
                    "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                    "limitations": "Ограничения" if is_ru else "Limitations",
                    "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                }
                doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                    text = str(contract.get(key) or "").strip()
                    if text:
                        doc.add_paragraph(f"{labels[key]}: {text}")
            else:
                fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                if isinstance(fallback, str) and fallback.strip():
                    doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                    doc.add_paragraph(fallback.strip())
            continue

        step_type = res.get("type")
        method_id = _method_id_from_payload(res)
        if step_type and step_type not in {
            "compare",
            "hypothesis_test",
            "correlation",
            "regression",
            "survival",
            "mixed_effects",
            "clustered_correlation",
            "batch_compare_by_factor",
            "batch_analysis",
            "timepoint_batch_analysis",
            "responders",
            "bootstrap_pipeline",
            "cluster_profiles",
            "external_validation",
        }:
            doc.add_paragraph(("Тип" if is_ru else "Type") + f": {_txt(step_type)}")
            err = res.get("error")
            if isinstance(err, str) and err.strip():
                doc.add_paragraph(("Ошибка" if is_ru else "Error") + f": {_txt(err)}")
            try:
                raw = json.dumps(res, ensure_ascii=False, indent=2, default=str)
            except Exception:
                raw = str(res)
            raw = raw[:8000]
            doc.add_paragraph(raw)
            continue

        method = res.get("method")
        method_default = "Статистический тест" if is_ru else "Statistical Test"
        method_name = method_default
        if isinstance(method, dict):
            method_name = method.get("name") or method.get("id") or method_name
        elif isinstance(method, str):
            method_name = method
        doc.add_paragraph(("Метод" if is_ru else "Method") + f": {method_name}")

        if res.get("type") == "mixed_effects" and res.get("formula"):
            doc.add_paragraph(("Формула" if is_ru else "Formula") + f": {str(res.get('formula'))}")

        summary = doc.add_table(rows=0, cols=2)
        for k, v in [
            ("p-value", _fmt_p(res.get("p_value"))),
            (("статистика" if is_ru else "stat"), _fmt_num(res.get("stat_value", res.get("stats")), 3)),
            (("эффект" if is_ru else "effect"), f"{_txt(res.get('effect_size_name') or 'effect')} {_fmt_num(res.get('effect_size'), 2)}" if res.get("effect_size") is not None else "-"),
            (("мощность" if is_ru else "power"), _fmt_num(res.get("power"), 2)),
            ("BF10", _txt(res.get("bf10"))),
        ]:
            r = summary.add_row().cells
            r[0].text = str(k)
            r[1].text = str(v)

        if method_id == "bootstrap_pipeline":
            bootstrap = res.get("bootstrap") if isinstance(res.get("bootstrap"), dict) else {}
            mode = _txt(res.get("mode"))
            statistic = _txt(res.get("statistic"))
            n_boot = bootstrap.get("n_resamples")
            ci_level = bootstrap.get("ci_level")
            observed = bootstrap.get("observed_effect")
            ci_lo = res.get("effect_size_ci_lower")
            ci_hi = res.get("effect_size_ci_upper")
            dist_mean = bootstrap.get("distribution_mean")
            dist_std = bootstrap.get("distribution_std")

            doc.add_heading("Bootstrap-устойчивость эффекта" if is_ru else "Bootstrap Effect Stability", level=2)
            table = doc.add_table(rows=1, cols=2)
            hdr = table.rows[0].cells
            hdr[0].text = "Параметр" if is_ru else "Parameter"
            hdr[1].text = "Значение" if is_ru else "Value"
            rows = [
                ("Режим" if is_ru else "Mode", mode),
                ("Статистика" if is_ru else "Statistic", statistic),
                ("Bootstrap resamples", _txt(int(n_boot)) if isinstance(n_boot, (int, float)) else "-"),
                ("CI уровень" if is_ru else "CI level", _fmt_num(ci_level, 3)),
                ("Наблюдаемый эффект" if is_ru else "Observed effect", _fmt_num(observed, 3)),
                ("CI эффекта" if is_ru else "Effect CI", f"[{_fmt_num(ci_lo, 3)}, {_fmt_num(ci_hi, 3)}]" if ci_lo is not None and ci_hi is not None else "-"),
                ("Среднее bootstrap-распределения" if is_ru else "Bootstrap distribution mean", _fmt_num(dist_mean, 3)),
                ("SD bootstrap-распределения" if is_ru else "Bootstrap distribution SD", _fmt_num(dist_std, 3)),
            ]
            for label, value in rows:
                row = table.add_row().cells
                row[0].text = str(label)
                row[1].text = str(value)

            groups = res.get("groups") if isinstance(res.get("groups"), list) else []
            if len(groups) == 2:
                left = str(groups[0])
                right = str(groups[1])
                left_n = _txt(int(res.get("n_left"))) if isinstance(res.get("n_left"), (int, float)) else "-"
                right_n = _txt(int(res.get("n_right"))) if isinstance(res.get("n_right"), (int, float)) else "-"
                doc.add_paragraph(
                    ("Сравниваемые группы" if is_ru else "Compared groups")
                    + f": {left} (n={left_n}) vs {right} (n={right_n})"
                )

        if method_id == "cluster_profiles":
            doc.add_heading("Профили кластеров" if is_ru else "Cluster Profiles", level=2)
            doc.add_paragraph(
                " • ".join(
                    [
                        f"N={_txt(res.get('n_observations'))}",
                        (("Переменных" if is_ru else "Variables") + f"={_txt(res.get('n_variables'))}"),
                        (("Кластеров" if is_ru else "Clusters") + f"={_txt(res.get('n_clusters'))}"),
                        (f"Silhouette={_fmt_num(res.get('silhouette_score'), 3)}"),
                    ]
                )
            )
            clusters_payload = res.get("clusters") if isinstance(res.get("clusters"), list) else []
            if clusters_payload:
                table = doc.add_table(rows=1, cols=3)
                hdr = table.rows[0].cells
                hdr[0].text = "Кластер" if is_ru else "Cluster"
                hdr[1].text = "Размер" if is_ru else "Size"
                hdr[2].text = "Доля" if is_ru else "Proportion"
                for row in clusters_payload[:24]:
                    if not isinstance(row, dict):
                        continue
                    r = table.add_row().cells
                    r[0].text = _txt(row.get("cluster"))
                    r[1].text = _txt(int(row.get("size"))) if isinstance(row.get("size"), (int, float)) else "-"
                    prop = row.get("proportion")
                    if isinstance(prop, (int, float)):
                        r[2].text = f"{float(prop) * 100.0:.1f}%"
                    else:
                        r[2].text = "-"

        if method_id == "external_validation":
            internal_metrics = res.get("internal_metrics") if isinstance(res.get("internal_metrics"), dict) else {}
            external_metrics = res.get("external_metrics") if isinstance(res.get("external_metrics"), dict) else {}
            gap = res.get("generalization_gap") if isinstance(res.get("generalization_gap"), dict) else {}
            task = str(res.get("task") or "").strip().lower()

            doc.add_heading("Внешняя валидация" if is_ru else "External Validation", level=2)
            doc.add_paragraph(
                " • ".join(
                    [
                        (("Внешний датасет" if is_ru else "External dataset") + f"={_txt(res.get('external_dataset_id') or '-') }"),
                        f"N train={_txt(res.get('n_train'))}",
                        f"N internal={_txt(res.get('n_internal_test'))}",
                        f"N external={_txt(res.get('n_external'))}",
                    ]
                )
            )

            metric_keys = (
                [("AUC", "auc"), ("Accuracy", "accuracy"), ("Precision", "precision"), ("Recall", "recall"), ("F1", "f1")]
                if task == "classification"
                else [("R2", "r_squared"), ("RMSE", "rmse"), ("MAE", "mae")]
            )
            metrics_table = doc.add_table(rows=1, cols=3)
            hdr = metrics_table.rows[0].cells
            hdr[0].text = "Метрика" if is_ru else "Metric"
            hdr[1].text = "Internal"
            hdr[2].text = "External"
            for label, key in metric_keys:
                row = metrics_table.add_row().cells
                row[0].text = label
                row[1].text = _fmt_num(internal_metrics.get(key), 3)
                row[2].text = _fmt_num(external_metrics.get(key), 3)

            if gap:
                gap_table = doc.add_table(rows=1, cols=2)
                hdr = gap_table.rows[0].cells
                hdr[0].text = "Generalization gap"
                hdr[1].text = "Value"
                for key, value in list(gap.items())[:10]:
                    row = gap_table.add_row().cells
                    row[0].text = _txt(key)
                    row[1].text = _fmt_num(value, 3) if isinstance(value, (int, float)) else _txt(value)

            cm = res.get("confusion_matrix") if isinstance(res.get("confusion_matrix"), dict) else {}
            cm_values = cm.get("values") if isinstance(cm.get("values"), list) else []
            cm_labels = cm.get("labels") if isinstance(cm.get("labels"), list) else []
            if len(cm_values) == 2 and all(isinstance(item, list) and len(item) == 2 for item in cm_values):
                l0 = _txt(cm_labels[0]) if len(cm_labels) > 0 else "0"
                l1 = _txt(cm_labels[1]) if len(cm_labels) > 1 else "1"
                doc.add_paragraph("Матрица ошибок (external)" if is_ru else "Confusion Matrix (external)")
                cm_table = doc.add_table(rows=3, cols=3)
                cm_table.cell(0, 0).text = ""
                cm_table.cell(0, 1).text = l0
                cm_table.cell(0, 2).text = l1
                cm_table.cell(1, 0).text = l0
                cm_table.cell(1, 1).text = _txt(cm_values[0][0])
                cm_table.cell(1, 2).text = _txt(cm_values[0][1])
                cm_table.cell(2, 0).text = l1
                cm_table.cell(2, 1).text = _txt(cm_values[1][0])
                cm_table.cell(2, 2).text = _txt(cm_values[1][1])

            calibration = res.get("calibration") if isinstance(res.get("calibration"), dict) else {}
            if calibration.get("brier_score") is not None:
                doc.add_paragraph(f"Brier score: {_fmt_num(calibration.get('brier_score'), 3)}")

        compare_rows = _build_pairwise_comparison_rows(res)
        if compare_rows:
            is_median = compare_rows[0].get("center_label") == "median"
            a_hdr = ("Me [Q1; Q3]" if is_median else "M ± SD")

            doc.add_paragraph("Сравнение групп (сводная таблица):" if is_ru else "Group Comparison (Summary Table):")
            table = doc.add_table(rows=1, cols=8)
            hdr = table.rows[0].cells
            hdr[0].text = "Сравнение" if is_ru else "Comparison"
            hdr[1].text = f"{a_hdr} A"
            hdr[2].text = f"{a_hdr} B"
            hdr[3].text = "Δ (A−B)"
            hdr[4].text = "Δ%"
            hdr[5].text = "p"
            hdr[6].text = "BF10"
            hdr[7].text = "Эффект" if is_ru else "Effect"

            def _fmt(v: Any, d: int = 2) -> str:
                try:
                    if v is None:
                        return "-"
                    f = float(v)
                    return f"{f:.{d}f}" if np.isfinite(f) else "-"
                except Exception:
                    return "-"

            for r in compare_rows[:80]:
                row = table.add_row().cells
                a = str(r.get("a") or "-")
                b = str(r.get("b") or "-")
                row[0].text = f"{a} vs {b}"

                a_n = r.get("a_n")
                b_n = r.get("b_n")
                a_n_s = f"n={int(a_n)}" if isinstance(a_n, (int, float)) else ""
                b_n_s = f"n={int(b_n)}" if isinstance(b_n, (int, float)) else ""

                if is_median:
                    q1a, q3a = r.get("a_spread") if isinstance(r.get("a_spread"), tuple) else (None, None)
                    q1b, q3b = r.get("b_spread") if isinstance(r.get("b_spread"), tuple) else (None, None)
                    row[1].text = f"{_fmt(r.get('a_center'))} [{_fmt(q1a)}; {_fmt(q3a)}] {a_n_s}".strip()
                    row[2].text = f"{_fmt(r.get('b_center'))} [{_fmt(q1b)}; {_fmt(q3b)}] {b_n_s}".strip()
                else:
                    row[1].text = f"{_fmt(r.get('a_center'))} ± {_fmt(r.get('a_spread'))} {a_n_s}".strip()
                    row[2].text = f"{_fmt(r.get('b_center'))} ± {_fmt(r.get('b_spread'))} {b_n_s}".strip()

                row[3].text = _fmt(r.get("diff"), 2)
                diff_pct = r.get("diff_pct")
                row[4].text = (f"{_fmt(diff_pct, 1)}%" if diff_pct is not None else "-")
                row[5].text = _fmt_p(r.get("p_value"))
                row[6].text = _fmt(r.get("bf10"), 3)
                eff = r.get("effect_size")
                eff_name = r.get("effect_size_name")
                row[7].text = (f"{_txt(eff_name or 'effect')}={_fmt(eff)}" if eff is not None else "-")

            doc.add_paragraph(
                "Пояснения: Δ — абсолютная разница (A−B); Δ% — (A−B)/B; p — уровень значимости; BF10 — сила свидетельства в пользу H1 (значения <1 поддерживают H0); эффект — размер эффекта." if is_ru else "Notes: Δ is (A−B); Δ% is (A−B)/B; p is the p-value; BF10 quantifies evidence for H1 (values <1 support H0); effect is effect size."
            )
        else:
            group_levels = _extract_groups(res if isinstance(res, dict) else {})
            if group_levels and len(group_levels) >= 3:
                doc.add_paragraph(
                    "Есть 3+ группы: попарные сравнения (post-hoc) не выполнены или отсутствуют в результате." if is_ru else "3+ groups: pairwise post-hoc comparisons are not available for this step."
                )

        if is_ru:
            rationale_ru = _method_selection_rationale_ru(res)
            if isinstance(rationale_ru, str) and rationale_ru.strip():
                doc.add_paragraph("Обоснование выбора теста: " + rationale_ru)

            bf10_text = _interpret_bf10_ru(res.get("bf10"))
            if isinstance(bf10_text, str) and bf10_text.strip():
                doc.add_paragraph("Интерпретация BF10: " + bf10_text)

        try:
            plot_png = _render_plot_png_bytes(res, is_ru=is_ru)
            if plot_png:
                bio = BytesIO(plot_png)
                doc.add_picture(bio, width=Inches(5.8))
                caption = _build_plot_caption(res if isinstance(res, dict) else {}, is_ru=is_ru)
                if caption:
                    doc.add_paragraph(caption)
        except Exception:
            pass

        warnings = res.get("warnings")
        if isinstance(warnings, list) and warnings:
            doc.add_paragraph("Предупреждения:" if is_ru else "Warnings:")
            for w in warnings:
                doc.add_paragraph(str(w), style="List Bullet")

        roc = res.get("roc")
        if isinstance(roc, dict) and isinstance(roc.get("plot_data"), list) and roc.get("plot_data"):
            auc_val = roc.get("auc")
            if auc_val is not None:
                doc.add_paragraph(f"AUC: {_fmt_num(auc_val, 3)}")
            roc_png = _render_plot_png_bytes(
                {"plot_data": roc.get("plot_data"), "plot_config": roc.get("plot_config")},
                is_ru=is_ru,
            )
            if roc_png:
                bio = BytesIO(roc_png)
                doc.add_picture(bio, width=Inches(5.8))
                caption = (
                    f"{'Подпись графика' if is_ru else 'Figure caption'}: "
                    + f"AUC={_fmt_num(auc_val, 3)}."
                    if auc_val is not None
                    else ("ROC-диаграмма для модели." if is_ru else "ROC curve for the model.")
                )
                doc.add_paragraph(caption)

        if res.get("type") == "mixed_effects":
            em = res.get("estimated_means")
            if isinstance(em, dict) and em:
                doc.add_heading("Оценённые средние" if is_ru else "Estimated Means", level=2)
                table = doc.add_table(rows=1, cols=5)
                hdr = table.rows[0].cells
                hdr[0].text = "Группа" if is_ru else "Group"
                hdr[1].text = "Визит" if is_ru else "Time"
                hdr[2].text = "Оценка" if is_ru else "Estimate"
                hdr[3].text = "95% ДИ" if is_ru else "95% CI"
                hdr[4].text = "n"

                def _sort_key(v: Any) -> Any:
                    try:
                        return float(v)
                    except Exception:
                        return str(v)

                for g in sorted(em.keys(), key=_sort_key):
                    times = em.get(g)
                    if not isinstance(times, dict):
                        continue
                    for t in sorted(times.keys(), key=_sort_key):
                        stats = times.get(t)
                        if not isinstance(stats, dict):
                            continue
                        r = table.add_row().cells
                        r[0].text = str(g)
                        r[1].text = str(t)
                        r[2].text = _fmt_num(stats.get("estimate"), 2)
                        r[3].text = f"[{_fmt_num(stats.get('ci_lower'), 2)}, {_fmt_num(stats.get('ci_upper'), 2)}]"
                        r[4].text = _txt(stats.get("n"))

        if res.get("type") == "regression":
            coefs = res.get("coefficients")
            if isinstance(coefs, list) and coefs:
                doc.add_heading("Коэффициенты" if is_ru else "Coefficients", level=2)
                has_or = any(isinstance(c, dict) and c.get("odds_ratio") is not None for c in coefs)
                cols = 5 + (1 if has_or else 0)
                table = doc.add_table(rows=1, cols=cols)
                hdr = table.rows[0].cells
                hdr[0].text = "Переменная" if is_ru else "Term"
                hdr[1].text = "Коэф." if is_ru else "Coef"
                hdr[2].text = "SE"
                hdr[3].text = "p"
                hdr[4].text = "95% ДИ" if is_ru else "95% CI"
                if has_or:
                    hdr[5].text = "OR"

                for c in coefs[:40]:
                    if not isinstance(c, dict):
                        continue
                    r = table.add_row().cells
                    r[0].text = _txt(c.get("variable"))
                    r[1].text = _fmt_num(c.get("coefficient"), 3)
                    r[2].text = _fmt_num(c.get("std_err"), 3)
                    r[3].text = _fmt_p(c.get("p_value"))
                    r[4].text = f"[{_fmt_num(c.get('ci_lower'), 3)}, {_fmt_num(c.get('ci_upper'), 3)}]"
                    if has_or:
                        r[5].text = _fmt_num(c.get("odds_ratio"), 3) if c.get("odds_ratio") is not None else "-"

        png_bytes = _render_plot_png_bytes(res, is_ru=is_ru)
        if png_bytes:
            try:
                section = doc.sections[-1]
                available_emu = int(section.page_width) - int(section.left_margin) - int(section.right_margin)
                available_in = max(1.0, float(available_emu) / 914400.0)
                available_h_emu = int(section.page_height) - int(section.top_margin) - int(section.bottom_margin)
                available_h_in = max(1.0, float(available_h_emu) / 914400.0)
            except Exception:
                available_in = 5.8
                available_h_in = 7.5

            doc.add_paragraph(("График" if is_ru else "Plot") + (": на следующей странице" if is_ru else ": next page"))
            doc.add_page_break()
            bio = BytesIO(png_bytes)

            try:
                from PIL import Image
                from io import BytesIO as _Bio

                with Image.open(_Bio(png_bytes)) as im:
                    img_w_px, img_h_px = im.size
                ratio = float(img_h_px) / float(img_w_px) if img_w_px else None
            except Exception:
                ratio = None

            if ratio and ratio > 0:
                if (available_in * ratio) <= available_h_in:
                    doc.add_picture(bio, width=Inches(available_in))
                else:
                    doc.add_picture(bio, height=Inches(available_h_in))
            else:
                doc.add_picture(bio, width=Inches(available_in))
            caption = _build_plot_caption(res if isinstance(res, dict) else {}, is_ru=is_ru)
            if caption:
                doc.add_paragraph(caption)
            if idx < len(steps) - 1:
                doc.add_page_break()

        contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
        if contract:
            labels = {
                "claim": "Статистический вывод" if is_ru else "Statistical claim",
                "evidence": "Доказательная база" if is_ru else "Evidence",
                "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                "limitations": "Ограничения" if is_ru else "Limitations",
                "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
            }
            doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
            for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                text = str(contract.get(key) or "").strip()
                if text:
                    doc.add_paragraph(f"{labels[key]}: {text}")
        else:
            interpretation = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else res.get("conclusion")
            if interpretation:
                doc.add_paragraph(("Интерпретация" if is_ru else "Interpretation") + ":")
                doc.add_paragraph(str(interpretation))

    summary = _extract_protocol_findings(run_data if isinstance(run_data, dict) else {})
    text = _build_discussion_conclusion(summary, is_ru=is_ru)
    discussion = text.get("discussion") if isinstance(text.get("discussion"), list) else []
    conclusion = text.get("conclusion") if isinstance(text.get("conclusion"), list) else []

    if discussion:
        doc.add_heading("Обсуждение" if is_ru else "Discussion", level=1)
        for line in discussion:
            doc.add_paragraph(str(line))

    if conclusion:
        doc.add_heading("Выводы" if is_ru else "Conclusions", level=1)
        for line in conclusion:
            doc.add_paragraph(str(line), style="List Bullet")

    limitations = _build_report_limitations(summary, methods_summary, is_ru=is_ru)
    if limitations:
        doc.add_heading("Ограничения" if is_ru else "Limitations", level=1)
        for line in limitations:
            doc.add_paragraph(str(line), style="List Bullet")

    out = BytesIO()
    doc.save(out)
    return bytes(out.getvalue())

def generate_legacy_plot_image(plot_data: List[Dict[str, Any]], method_id: str) -> str:
    """
    Legacy: Generates a matplotlib plot based on plot_data and returns base64 string.
    """
    if not plot_data:
        return ""
    
    df = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(8, 6))
    sns.set_theme(style="whitegrid")
    
    is_parametric = method_id in ["t_test_ind", "t_test_rel"]
    
    ax = sns.stripplot(
        data=df, 
        x="group", 
        y="value", 
        jitter=True, 
        alpha=0.6, 
        size=8,
        color="#0f172a"
    )
    
    sns.boxplot(
        data=df,
        x="group",
        y="value",
        showfliers=False,
        boxprops={'facecolor':'none', 'edgecolor':'grey'},
        width=0.4,
        ax=ax
    )

    plt.title(f"Distribution by Group ({method_id})")
    plt.xlabel("Group")
    plt.ylabel("Value")
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def render_report(
    analysis_result: AnalysisResult,
    target_col: str,
    group_col: str,
    dataset_name: str = "Dataset"
) -> str:
    """
    Legacy: Renders the HTML report using Jinja2 template.
    """
    
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
        "p_value_fmt": f"{analysis_result.p_value:.4f}" if analysis_result.p_value >= 0.001 else "< 0.001"
    }
    
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("report.html")
    return template.render(**context)

def render_protocol_report(run_data: Dict, dataset_name: str, style: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
    report = ProtocolReport(run_data, dataset_name, style=style or "gost", options=options)
    return report.generate_html()

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
            pdf.cell(0, 6, _safe_text(("Поправка" if is_ru else "Correction") + f": {multiplicity}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
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
                method_s = str(r.get("method") or "").strip()
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

    new_page_before_step = False
    for step_id, res in iter_steps():
        if new_page_before_step:
            pdf.add_page()
            new_page_before_step = False
        pdf.set_font(font_family, "B", body_size + 2)
        try:
            pdf.set_x(pdf.l_margin)
        except Exception:
            pass
        pdf.multi_cell(0, 6, _safe_text(("Шаг" if is_ru else "Step") + f": {step_id}", allow_unicode))

        step_meta = step_meta_map.get(step_id) if isinstance(step_id, str) else None
        step_meta = step_meta if isinstance(step_meta, dict) else {}
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
            method_name = method.get("name") or method.get("id") or method_name
        elif isinstance(method, str) and method.strip():
            method_name = method.strip()
        method_id = _method_id_from_payload(res)
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
                pdf.cell(0, 6, _safe_text(("Поправка" if is_ru else "Correction") + f": {corr}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

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
                    method_s = str(r.get("method") or "").strip()
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
                contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
                if contract:
                    labels = {
                        "claim": "Статистический вывод" if is_ru else "Statistical claim",
                        "evidence": "Доказательная база" if is_ru else "Evidence",
                        "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                        "limitations": "Ограничения" if is_ru else "Limitations",
                        "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                    }
                    pdf.ln(1)
                    for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                        text = str(contract.get(key) or "").strip()
                        if not text:
                            continue
                        try:
                            pdf.set_x(pdf.l_margin)
                        except Exception:
                            pass
                        pdf.multi_cell(0, 5, _safe_text(f"{labels[key]}: {text}", allow_unicode))
                else:
                    fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                    if isinstance(fallback, str) and fallback.strip():
                        try:
                            pdf.set_x(pdf.l_margin)
                        except Exception:
                            pass
                        pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Interpretation") + f": {fallback.strip()}", allow_unicode))
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
            contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
            if contract:
                labels = {
                    "claim": "Статистический вывод" if is_ru else "Statistical claim",
                    "evidence": "Доказательная база" if is_ru else "Evidence",
                    "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                    "limitations": "Ограничения" if is_ru else "Limitations",
                    "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                }
                pdf.ln(1)
                for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                    text = str(contract.get(key) or "").strip()
                    if not text:
                        continue
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 5, _safe_text(f"{labels[key]}: {text}", allow_unicode))
            else:
                fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                if isinstance(fallback, str) and fallback.strip():
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Interpretation") + f": {fallback.strip()}", allow_unicode))
            pdf.ln(3)
            new_page_before_step = True
            continue

        if step_type and step_type not in {
            "table_1",
            "compare",
            "hypothesis_test",
            "correlation",
            "regression",
            "survival",
            "mixed_effects",
            "clustered_correlation",
            "batch_compare_by_factor",
            "responders",
            "batch_analysis",
            "timepoint_batch_analysis",
            "bootstrap_pipeline",
            "cluster_profiles",
            "external_validation",
        }:
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

            contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
            if contract:
                labels = {
                    "claim": "Статистический вывод" if is_ru else "Statistical claim",
                    "evidence": "Доказательная база" if is_ru else "Evidence",
                    "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                    "limitations": "Ограничения" if is_ru else "Limitations",
                    "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
                }
                pdf.ln(1)
                for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                    text = str(contract.get(key) or "").strip()
                    if not text:
                        continue
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 5, _safe_text(f"{labels[key]}: {text}", allow_unicode))
            else:
                fallback = (res.get("ai_interpretation") or res.get("conclusion")) if is_ru else (res.get("conclusion") or res.get("ai_interpretation"))
                if isinstance(fallback, str) and fallback.strip():
                    try:
                        pdf.set_x(pdf.l_margin)
                    except Exception:
                        pass
                    pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Interpretation") + f": {fallback.strip()}", allow_unicode))

            pdf.ln(3)
            continue

        p_key = "p_value" if "p_value" in res else ("interaction_p_value" if "interaction_p_value" in res else None)
        if p_key:
            label = "p-value" if p_key == "p_value" else ("p (Time×Group)" if not is_ru else "p (Визит×Группа)")
            pdf.cell(0, 6, _safe_text(f"{label}: {_fmt_p(res.get(p_key))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")
        if "stat_value" in res or "stats" in res:
            pdf.cell(0, 6, _safe_text(("Статистика" if is_ru else "Statistic") + f": {_fmt_num(res.get('stat_value', res.get('stats')))}", allow_unicode), new_x="LMARGIN", new_y="NEXT")

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

        if method_id == "bootstrap_pipeline":
            bootstrap = res.get("bootstrap") if isinstance(res.get("bootstrap"), dict) else {}
            mode = str(res.get("mode") or "-")
            statistic = str(res.get("statistic") or "-")
            n_boot = bootstrap.get("n_resamples")
            ci_level = bootstrap.get("ci_level")
            observed = bootstrap.get("observed_effect")
            ci_lo = res.get("effect_size_ci_lower")
            ci_hi = res.get("effect_size_ci_upper")
            dist_mean = bootstrap.get("distribution_mean")
            dist_std = bootstrap.get("distribution_std")
            groups = res.get("groups") if isinstance(res.get("groups"), list) else []

            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(0, 6, _safe_text("Bootstrap-устойчивость эффекта" if is_ru else "Bootstrap Effect Stability", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            details = [
                ("Режим" if is_ru else "Mode", mode),
                ("Статистика" if is_ru else "Statistic", statistic),
                ("Bootstrap resamples", str(int(n_boot)) if isinstance(n_boot, (int, float)) else "-"),
                ("CI уровень" if is_ru else "CI level", _fmt_num(ci_level, 3)),
                ("Наблюдаемый эффект" if is_ru else "Observed effect", _fmt_num(observed, 3)),
                ("CI эффекта" if is_ru else "Effect CI", f"[{_fmt_num(ci_lo, 3)}, {_fmt_num(ci_hi, 3)}]" if ci_lo is not None and ci_hi is not None else "-"),
                ("Среднее bootstrap-распределения" if is_ru else "Bootstrap distribution mean", _fmt_num(dist_mean, 3)),
                ("SD bootstrap-распределения" if is_ru else "Bootstrap distribution SD", _fmt_num(dist_std, 3)),
            ]
            for label, value in details:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"{label}: {value}", allow_unicode))
            if len(groups) == 2:
                left = str(groups[0])
                right = str(groups[1])
                left_n = str(int(res.get("n_left"))) if isinstance(res.get("n_left"), (int, float)) else "-"
                right_n = str(int(res.get("n_right"))) if isinstance(res.get("n_right"), (int, float)) else "-"
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(
                    0,
                    5,
                    _safe_text(
                        ((("Сравниваемые группы" if is_ru else "Compared groups") + f": {left} (n={left_n}) vs {right} (n={right_n})")),
                        allow_unicode,
                    ),
                )

        if method_id == "cluster_profiles":
            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(0, 6, _safe_text("Профили кластеров" if is_ru else "Cluster Profiles", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            summary_line = " • ".join(
                [
                    f"N={_fmt_num(res.get('n_observations'), 0)}",
                    (("Переменных" if is_ru else "Variables") + f"={_fmt_num(res.get('n_variables'), 0)}"),
                    (("Кластеров" if is_ru else "Clusters") + f"={_fmt_num(res.get('n_clusters'), 0)}"),
                    f"Silhouette={_fmt_num(res.get('silhouette_score'), 3)}",
                ]
            )
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(summary_line, allow_unicode))

            clusters_payload = res.get("clusters") if isinstance(res.get("clusters"), list) else []
            shown = 0
            for cluster in clusters_payload:
                if not isinstance(cluster, dict):
                    continue
                cid = cluster.get("cluster")
                size = cluster.get("size")
                prop = cluster.get("proportion")
                prop_s = f"{float(prop) * 100.0:.1f}%" if isinstance(prop, (int, float)) else "-"
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(
                    0,
                    5,
                    _safe_text(
                        (f"{('Кластер' if is_ru else 'Cluster')} {cid}: {('размер' if is_ru else 'size')}={size}, {('доля' if is_ru else 'proportion')}={prop_s}"),
                        allow_unicode,
                    ),
                )
                shown += 1
                if shown >= 18:
                    break

        if method_id == "external_validation":
            internal_metrics = res.get("internal_metrics") if isinstance(res.get("internal_metrics"), dict) else {}
            external_metrics = res.get("external_metrics") if isinstance(res.get("external_metrics"), dict) else {}
            gap = res.get("generalization_gap") if isinstance(res.get("generalization_gap"), dict) else {}
            task = str(res.get("task") or "").strip().lower()

            pdf.ln(1)
            pdf.set_font(font_family, "B", body_size + 1)
            pdf.cell(0, 6, _safe_text("Внешняя валидация" if is_ru else "External Validation", allow_unicode), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_family, "", body_size)
            header_line = " • ".join(
                [
                    (("Внешний датасет" if is_ru else "External dataset") + f"={res.get('external_dataset_id') or '-'}"),
                    f"N train={_fmt_num(res.get('n_train'), 0)}",
                    f"N internal={_fmt_num(res.get('n_internal_test'), 0)}",
                    f"N external={_fmt_num(res.get('n_external'), 0)}",
                ]
            )
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(header_line, allow_unicode))

            metric_keys = (
                [("AUC", "auc"), ("Accuracy", "accuracy"), ("Precision", "precision"), ("Recall", "recall"), ("F1", "f1")]
                if task == "classification"
                else [("R2", "r_squared"), ("RMSE", "rmse"), ("MAE", "mae")]
            )
            for label, key in metric_keys:
                i_val = _fmt_num(internal_metrics.get(key), 3)
                e_val = _fmt_num(external_metrics.get(key), 3)
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"{label}: internal={i_val}, external={e_val}", allow_unicode))

            for g_key, g_val in list(gap.items())[:10]:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                g_value = _fmt_num(g_val, 3) if isinstance(g_val, (int, float)) else str(g_val)
                pdf.multi_cell(0, 5, _safe_text(f"generalization_gap[{g_key}]={g_value}", allow_unicode))

            cm = res.get("confusion_matrix") if isinstance(res.get("confusion_matrix"), dict) else {}
            cm_values = cm.get("values") if isinstance(cm.get("values"), list) else []
            cm_labels = cm.get("labels") if isinstance(cm.get("labels"), list) else []
            if len(cm_values) == 2 and all(isinstance(item, list) and len(item) == 2 for item in cm_values):
                l0 = str(cm_labels[0]) if len(cm_labels) > 0 else "0"
                l1 = str(cm_labels[1]) if len(cm_labels) > 1 else "1"
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text((("Матрица ошибок (external)" if is_ru else "Confusion matrix (external)") + f": [{l0}] {cm_values[0][0]}/{cm_values[0][1]}, [{l1}] {cm_values[1][0]}/{cm_values[1][1]}"), allow_unicode))

            calibration = res.get("calibration") if isinstance(res.get("calibration"), dict) else {}
            brier = calibration.get("brier_score")
            if brier is not None:
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"Brier score={_fmt_num(brier, 3)}", allow_unicode))

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
        contract = _extract_interpretation_contract(res if isinstance(res, dict) else {})
        plot_png = _render_plot_png_bytes(res, is_ru=is_ru)

        if plot_png:
            pdf.ln(1)
            pdf.set_font(font_family, "", body_size)
            pdf.cell(0, 6, _safe_text(("График" if is_ru else "Plot") + (": на следующей странице" if is_ru else ": next page"), allow_unicode), new_x="LMARGIN", new_y="NEXT")

        if contract:
            labels = {
                "claim": "Статистический вывод" if is_ru else "Statistical claim",
                "evidence": "Доказательная база" if is_ru else "Evidence",
                "clinical_meaning": "Клинический смысл" if is_ru else "Clinical meaning",
                "limitations": "Ограничения" if is_ru else "Limitations",
                "actionable_next_step": "Следующий шаг" if is_ru else "Actionable next step",
            }
            pdf.ln(1)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Interpretation") + ":", allow_unicode))
            for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
                text = str(contract.get(key) or "").strip()
                if not text:
                    continue
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(f"{labels[key]}: {text}", allow_unicode))
        elif interpretation:
            pdf.ln(1)
            try:
                pdf.set_x(pdf.l_margin)
            except Exception:
                pass
            pdf.multi_cell(0, 5, _safe_text(("Интерпретация" if is_ru else "Interpretation") + f": {interpretation}", allow_unicode))

        if plot_png:
            pdf.ln(3)
            pdf.add_page()
            _insert_png(pdf, plot_png)
            caption = _build_plot_caption(res if isinstance(res, dict) else {}, is_ru=is_ru)
            if caption:
                pdf.ln(2)
                try:
                    pdf.set_x(pdf.l_margin)
                except Exception:
                    pass
                pdf.multi_cell(0, 5, _safe_text(caption, allow_unicode))
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
