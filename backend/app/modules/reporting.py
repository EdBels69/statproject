import os
import json
import html
import hashlib
import re
import pandas as pd
import numpy as np
import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.schemas.analysis import AnalysisResult
from app.core.logging import logger
from app.stats.engine import _bf10_from_p_value_bound
from app.modules.analysis_result_v2 import normalize_analysis_result_v2, normalize_run_data_results
from app.modules.reporting_contracts import (
    build_report_integrity_context,
    filter_step_pairs_for_report,
)

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


def _fmt_p_inline(value: Any) -> str:
    p = _safe_float(value)
    if p is None:
        return "-"
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def _resolve_dataset_dir_path(dataset_id: Any) -> Optional[str]:
    ds_id = str(dataset_id or "").strip()
    if not ds_id:
        return None

    base = str(os.getenv("CLINIMETRIA_WORKSPACE_DIR", "workspace") or "workspace").strip() or "workspace"
    candidates: List[str] = []
    if os.path.isabs(base):
        candidates.append(base)
    else:
        candidates.append(base)
        candidates.append(os.path.join(os.getcwd(), base))
        try:
            repo_root = str(Path(__file__).resolve().parents[3])
            candidates.append(os.path.join(repo_root, base))
        except Exception:
            pass
        try:
            backend_root = str(Path(__file__).resolve().parents[2])
            candidates.append(os.path.join(backend_root, base))
        except Exception:
            pass

    seen: set = set()
    for base_dir in candidates:
        b = str(base_dir or "").strip()
        if not b or b in seen:
            continue
        seen.add(b)
        ds_dir = os.path.join(b, "datasets", ds_id)
        if os.path.isdir(ds_dir):
            return ds_dir
    return None


def _sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _build_provenance_file_context(
    *,
    dataset_id: Any,
    run_id: Any,
    ds_dir: Optional[str],
    source_meta: Dict[str, Any],
    source_files: List[str],
    reproducibility: Dict[str, Any],
) -> Dict[str, str]:
    ds_id = str(dataset_id or "").strip()
    run = str(run_id or "").strip()

    source_name = source_meta.get("original_filename") or source_meta.get("filename")
    source_rel = "-"
    source_abs: Optional[str] = None
    if ds_id and source_files:
        source_rel = os.path.join("workspace", "datasets", ds_id, "source", source_files[0])
        if isinstance(ds_dir, str) and ds_dir:
            source_abs = os.path.join(ds_dir, "source", source_files[0])
    elif source_name:
        source_rel = str(source_name)

    source_sha = _sha256_file(source_abs) if isinstance(source_abs, str) else None
    source_size: Optional[int] = None
    if isinstance(source_abs, str):
        try:
            source_size = int(os.path.getsize(source_abs))
        except Exception:
            source_size = None
    if source_sha and source_size is not None:
        source_fingerprint = f"sha256={source_sha}; bytes={source_size}"
    elif source_sha:
        source_fingerprint = f"sha256={source_sha}"
    elif source_size is not None:
        source_fingerprint = f"bytes={source_size}"
    else:
        source_fingerprint = "-"

    run_rel = "-"
    artifacts_rel = "-"
    artifacts_abs: Optional[str] = None
    if ds_id and run:
        run_rel = os.path.join("workspace", "datasets", ds_id, "analysis", run)
        artifacts_rel = os.path.join(run_rel, "artifacts")
        if isinstance(ds_dir, str) and ds_dir:
            artifacts_abs = os.path.join(ds_dir, "analysis", run, "artifacts")

    def _artifact_name(key: str) -> Optional[str]:
        value = reproducibility.get(key) if isinstance(reproducibility, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _artifact_abs(name: Optional[str]) -> Optional[str]:
        if not isinstance(name, str):
            return None
        if isinstance(artifacts_abs, str) and artifacts_abs:
            return os.path.join(artifacts_abs, name)
        return None

    script_name = _artifact_name("script")
    payload_name = _artifact_name("payload")
    protocol_name = _artifact_name("protocol")
    manifest_name = _artifact_name("manifest")

    script_abs = _artifact_abs(script_name)
    payload_abs = _artifact_abs(payload_name)
    protocol_abs = _artifact_abs(protocol_name)
    manifest_abs = _artifact_abs(manifest_name)

    repro_paths_parts = [
        f"script={(script_abs or script_name or '-')}",
        f"payload={(payload_abs or payload_name or '-')}",
        f"protocol={(protocol_abs or protocol_name or '-')}",
        f"manifest={(manifest_abs or manifest_name or '-')}",
    ]
    repro_paths = "; ".join(repro_paths_parts)

    if script_abs and payload_abs:
        repro_command = (
            f"python3 {script_abs} --base-url http://127.0.0.1:8000/api/v1/v2 --payload {payload_abs}"
        )
    elif script_name and payload_name:
        repro_command = (
            f"python3 {script_name} --base-url http://127.0.0.1:8000/api/v1/v2 --payload {payload_name}"
        )
    else:
        repro_command = "-"

    return {
        "source_name": str(source_name) if source_name else "-",
        "source_rel": source_rel,
        "source_fingerprint": source_fingerprint,
        "run_rel": run_rel,
        "artifacts_rel": artifacts_rel,
        "repro_paths": repro_paths,
        "repro_command": repro_command,
    }


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
    integrity_ctx = build_report_integrity_context(run_data)
    filtered_steps, filter_meta = filter_step_pairs_for_report(raw_steps, integrity_ctx)
    deduped = _dedupe_step_payloads(filtered_steps)

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
        p_value_adj = _safe_float(res.get("p_value_adj"))
        if p_value_adj is None:
            p_value_adj = _safe_float(res.get("adjusted_p_value"))
        alpha = _safe_float(res.get("alpha")) or alpha_default
        sig = res.get("significant")
        if not isinstance(sig, bool) and p_value is not None and alpha is not None:
            sig = p_value < alpha
        if isinstance(sig, bool) and sig:
            significant_steps += 1

        conclusion = res.get("ai_interpretation") or res.get("conclusion")
        if not isinstance(conclusion, str):
            conclusion = None
        elif _is_placeholder_interpretation(conclusion):
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
                "p_value_adj": p_value_adj,
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
        "total_steps": len(filtered_steps),
        "unique_steps": len(deduped),
        "significant_steps": significant_steps,
        "alpha": alpha_default,
        "ai_summary": ai_summary,
        "verification_status": filter_meta.get("verification_status"),
        "verification_present": bool(filter_meta.get("verification_present")),
        "excluded_unverified_steps": len(filter_meta.get("excluded_step_ids") or []),
        "excluded_unverified_step_ids": list(filter_meta.get("excluded_step_ids") or []),
        "source_total_steps": int(filter_meta.get("source_total_steps") or len(raw_steps)),
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
        "agreement": "Анализ согласия и воспроизводимости",
        "assumption_test": "Проверка статистических предпосылок",
        "time_series": "Анализ временного ряда",
    }
    mapping_en = {
        "table_1": "Descriptive statistics (Table 1)",
        "descriptive": "Descriptive statistics",
        "batch_compare_by_factor": "Longitudinal factor-wise comparison",
        "batch_analysis": "Batch inferential analysis",
        "timepoint_batch_analysis": "Timepoint batch analysis",
        "delta_batch_analysis": "Delta batch analysis",
        "responders": "Responder analysis",
        "agreement": "Agreement and reproducibility analysis",
        "assumption_test": "Assumption diagnostics",
        "time_series": "Time series analysis",
    }
    mapping = mapping_ru if is_ru else mapping_en
    return str(mapping.get(t) or "")


def _method_label_from_id(method_id: Any, is_ru: bool) -> str:
    mid = str(method_id or "").strip().lower()
    if not mid:
        return ""
    mapping_ru = {
        "t_test_ind": "t-тест (независимые выборки)",
        "t_test_rel": "t-тест (парный)",
        "t_test_welch": "t-тест Уэлча",
        "mann_whitney": "Манна-Уитни",
        "wilcoxon": "Уилкоксона",
        "anova": "ANOVA",
        "anova_welch": "ANOVA Уэлча",
        "kruskal": "Краскела-Уоллиса",
        "pearson": "Корреляция Пирсона",
        "spearman": "Корреляция Спирмена",
        "kendall": "Корреляция Кендалла",
        "partial_correlation": "Частичная корреляция",
        "chi_square": "χ²-тест",
        "fisher_exact": "Точный тест Фишера",
        "fisher": "Точный тест Фишера",
        "linear_regression": "Линейная регрессия",
        "logistic_regression": "Логистическая регрессия",
        "survival_km": "Анализ выживаемости (Kaplan-Meier)",
        "ancova": "ANCOVA",
        "roc_analysis": "ROC-анализ",
        "bland_altman": "Анализ Бланда-Альтмана",
        "time_series_analysis": "Анализ временного ряда",
        "pca": "PCA (анализ главных компонент)",
        "efa": "EFA (факторный анализ)",
        "kmeans": "K-means кластеризация",
        "hierarchical_clustering": "Иерархическая кластеризация",
        "clustered_correlation": "Кластерный корреляционный анализ",
        "shapiro_wilk": "Shapiro-Wilk (нормальность)",
        "dagostino_pearson": "D’Agostino-Pearson (нормальность)",
        "anderson_darling": "Anderson-Darling (нормальность)",
        "kolmogorov_smirnov": "Kolmogorov-Smirnov (нормальность)",
        "levene": "Levene (однородность дисперсий)",
        "bartlett": "Bartlett (однородность дисперсий)",
        "fligner": "Fligner-Killeen (однородность дисперсий)",
        "bayes_t_test_ind": "Байесовский t-тест (независимые)",
        "bayes_t_test_one": "Байесовский t-тест (одна выборка)",
        "bayes_correlation": "Байесовская корреляция",
        "bayes_anova": "Байесовская ANOVA",
        "bayes_chi_square": "Байесовский χ²-тест",
        "bayes_linear_regression": "Байесовская линейная регрессия",
    }
    mapping_en = {
        "t_test_ind": "Independent t-test",
        "t_test_rel": "Paired t-test",
        "t_test_welch": "Welch t-test",
        "mann_whitney": "Mann-Whitney U",
        "wilcoxon": "Wilcoxon signed-rank",
        "anova": "ANOVA",
        "anova_welch": "Welch ANOVA",
        "kruskal": "Kruskal-Wallis",
        "pearson": "Pearson correlation",
        "spearman": "Spearman correlation",
        "kendall": "Kendall correlation",
        "partial_correlation": "Partial correlation",
        "chi_square": "Chi-square test",
        "fisher_exact": "Fisher exact test",
        "fisher": "Fisher exact test",
        "linear_regression": "Linear regression",
        "logistic_regression": "Logistic regression",
        "survival_km": "Survival analysis (Kaplan-Meier)",
        "ancova": "ANCOVA",
        "roc_analysis": "ROC analysis",
        "bland_altman": "Bland-Altman analysis",
        "time_series_analysis": "Time series analysis",
        "pca": "PCA",
        "efa": "EFA",
        "kmeans": "K-means clustering",
        "hierarchical_clustering": "Hierarchical clustering",
        "clustered_correlation": "Clustered correlation",
        "shapiro_wilk": "Shapiro-Wilk normality test",
        "dagostino_pearson": "D’Agostino-Pearson normality test",
        "anderson_darling": "Anderson-Darling normality test",
        "kolmogorov_smirnov": "Kolmogorov-Smirnov normality test",
        "levene": "Levene homogeneity test",
        "bartlett": "Bartlett homogeneity test",
        "fligner": "Fligner-Killeen homogeneity test",
        "bayes_t_test_ind": "Bayesian independent t-test",
        "bayes_t_test_one": "Bayesian one-sample t-test",
        "bayes_correlation": "Bayesian correlation",
        "bayes_anova": "Bayesian ANOVA",
        "bayes_chi_square": "Bayesian chi-square",
        "bayes_linear_regression": "Bayesian linear regression",
    }
    mapping = mapping_ru if is_ru else mapping_en
    if mid in mapping:
        return str(mapping[mid])
    return str(mid.replace("_", " ")).strip()


def _normalize_correction_key(value: Any) -> str:
    corr = str(value or "").strip().lower().replace(" ", "_")
    if not corr:
        return ""
    aliases = {
        "bh": "fdr_bh",
        "fdr": "fdr_bh",
        "by": "fdr_by",
        "bky": "fdr_tsbky",
        "fdr_bky": "fdr_tsbky",
        "bonf": "bonferroni",
        "holm_sidak": "holm-sidak",
        "holmsidak": "holm-sidak",
    }
    return aliases.get(corr, corr)


def _format_correction_label(value: Any, is_ru: bool) -> str:
    key = _normalize_correction_key(value)
    mapping_ru = {
        "fdr_bh": "FDR (Benjamini-Hochberg)",
        "fdr_by": "FDR (Benjamini-Yekutieli)",
        "fdr_tsbky": "FDR (Benjamini-Krieger-Yekutieli, two-stage)",
        "bonferroni": "Bonferroni",
        "holm": "Holm",
        "holm-sidak": "Holm-Sidak",
        "sidak": "Sidak",
        "none": "без поправки",
    }
    mapping_en = {
        "fdr_bh": "FDR (Benjamini-Hochberg)",
        "fdr_by": "FDR (Benjamini-Yekutieli)",
        "fdr_tsbky": "FDR (Benjamini-Krieger-Yekutieli, two-stage)",
        "bonferroni": "Bonferroni",
        "holm": "Holm",
        "holm-sidak": "Holm-Sidak",
        "sidak": "Sidak",
        "none": "none",
    }
    mapping = mapping_ru if is_ru else mapping_en
    if key in mapping:
        return str(mapping[key])
    if not key:
        return ""
    return key.replace("_", " ")


def _format_boolean_label(value: Any, is_ru: bool) -> str:
    if isinstance(value, bool):
        return "да" if (is_ru and value) else ("нет" if is_ru else ("yes" if value else "no"))
    return "-"


def _format_validation_status_label(value: Any, is_ru: bool) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"passed", "ok"}:
        return "пройдена" if is_ru else "passed"
    if raw in {"failed", "error", "blocked"}:
        return "ошибка" if is_ru else "failed"
    if raw in {"skipped"}:
        return "пропущена" if is_ru else "skipped"
    return raw or "-"


def _extract_bootstrap_policy(run_data: Dict[str, Any], validation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if isinstance(validation, dict):
        direct = validation.get("bootstrap_policy")
        if isinstance(direct, dict):
            out.update(direct)
        policy = validation.get("policy") if isinstance(validation.get("policy"), dict) else {}
        if "enabled" not in out and "bootstrap_enabled" in policy:
            out["enabled"] = bool(policy.get("bootstrap_enabled"))
        if "samples" not in out and "bootstrap_samples" in policy:
            out["samples"] = policy.get("bootstrap_samples")

    top_level = run_data.get("bootstrap_policy") if isinstance(run_data.get("bootstrap_policy"), dict) else None
    if isinstance(top_level, dict):
        for key in ("enabled", "samples", "ci_level", "methods", "n_applied_steps", "n_ignored_steps"):
            if key not in out and key in top_level:
                out[key] = top_level.get(key)

    globals_in = run_data.get("globals") if isinstance(run_data.get("globals"), dict) else {}
    if "enabled" not in out and "bootstrap_ci" in globals_in:
        out["enabled"] = bool(globals_in.get("bootstrap_ci"))
    if "samples" not in out and "bootstrap_samples" in globals_in:
        out["samples"] = globals_in.get("bootstrap_samples")
    if "ci_level" not in out and "bootstrap_ci_level" in globals_in:
        out["ci_level"] = globals_in.get("bootstrap_ci_level")

    return out


def _format_bootstrap_policy_text(policy: Dict[str, Any], *, is_ru: bool) -> str:
    if not isinstance(policy, dict):
        return "-"

    enabled_raw = policy.get("enabled")
    samples_raw = policy.get("samples")
    applied_raw = policy.get("n_applied_steps")

    enabled_txt = _format_boolean_label(enabled_raw, is_ru) if isinstance(enabled_raw, bool) else "-"
    samples_txt = "-"
    try:
        if samples_raw is not None:
            samples_txt = str(int(samples_raw))
    except Exception:
        samples_txt = str(samples_raw) if samples_raw is not None else "-"
    applied_txt = "-"
    try:
        if applied_raw is not None:
            applied_txt = str(int(applied_raw))
    except Exception:
        applied_txt = str(applied_raw) if applied_raw is not None else "-"

    if is_ru:
        return f"enabled={enabled_txt}; samples={samples_txt}; applied_steps={applied_txt}"
    return f"enabled={enabled_txt}; samples={samples_txt}; applied_steps={applied_txt}"


def _extract_multiplicity_policy(run_data: Dict[str, Any], validation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if isinstance(validation, dict):
        direct = validation.get("multiplicity_policy")
        if isinstance(direct, dict):
            out.update(direct)
        policy = validation.get("policy") if isinstance(validation.get("policy"), dict) else {}
        if "correction" not in out and "multiplicity_correction" in policy:
            out["correction"] = policy.get("multiplicity_correction")
        if "post_hoc_correction" not in out and "post_hoc_correction" in policy:
            out["post_hoc_correction"] = policy.get("post_hoc_correction")

    top_level = run_data.get("multiplicity_policy") if isinstance(run_data.get("multiplicity_policy"), dict) else None
    if isinstance(top_level, dict):
        for key in (
            "enabled",
            "correction",
            "multiplicity_correction",
            "post_hoc_correction",
            "methods",
            "n_applied_steps",
            "n_ignored_steps",
        ):
            if key not in out and key in top_level:
                out[key] = top_level.get(key)

    globals_in = run_data.get("globals") if isinstance(run_data.get("globals"), dict) else {}
    if "correction" not in out and "multiplicity_correction" in globals_in:
        out["correction"] = globals_in.get("multiplicity_correction")
    if "post_hoc_correction" not in out and "post_hoc_correction" in globals_in:
        out["post_hoc_correction"] = globals_in.get("post_hoc_correction")

    if "multiplicity_correction" not in out and "correction" in out:
        out["multiplicity_correction"] = out.get("correction")
    if "correction" not in out and "multiplicity_correction" in out:
        out["correction"] = out.get("multiplicity_correction")

    return out


def _format_multiplicity_policy_text(policy: Dict[str, Any], *, is_ru: bool) -> str:
    if not isinstance(policy, dict):
        return "-"

    correction_raw = policy.get("correction") or policy.get("multiplicity_correction")
    correction_label = _format_correction_label(correction_raw, is_ru) if correction_raw else ""
    if not correction_label:
        correction_label = str(correction_raw or "-")

    post_hoc_raw = policy.get("post_hoc_correction")
    post_hoc_label = _format_correction_label(post_hoc_raw, is_ru) if post_hoc_raw else ""
    if not post_hoc_label:
        post_hoc_label = str(post_hoc_raw or "-")

    applied_raw = policy.get("n_applied_steps")
    applied_txt = "-"
    try:
        if applied_raw is not None:
            applied_txt = str(int(applied_raw))
    except Exception:
        applied_txt = str(applied_raw) if applied_raw is not None else "-"

    return f"correction={correction_label}; post_hoc={post_hoc_label}; applied_steps={applied_txt}"


def _extract_hypothesis_discovery_doc(run_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return {}
    direct = run_data.get("hypotheses")
    if isinstance(direct, dict) and isinstance(direct.get("items"), list):
        return direct
    return {}


def _normalize_hypothesis_method_id(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("-", "_")
    raw = re.sub(r"\s+", "_", raw)
    aliases = {
        "hclust": "hierarchical_clustering",
        "hierarchical": "hierarchical_clustering",
        "k_means": "kmeans",
        "timeseries": "time_series_analysis",
        "time_series": "time_series_analysis",
        "anovawelch": "anova_welch",
        "t_test": "t_test_ind",
        "ttest": "t_test_ind",
        "chisquare": "chi_square",
        "cochranq": "cochran_q",
        "point_biserial": "point_biserial",
        "pairedwide": "paired_wide",
    }
    return aliases.get(raw, raw)


def _split_hypothesis_suggested_methods(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"[,/|;+]+", text)
    out: List[str] = []
    seen: set = set()
    for part in parts:
        token = _normalize_hypothesis_method_id(part)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _extract_executed_methods_by_step(run_data: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(run_data, dict):
        return out

    step_meta = run_data.get("step_meta") if isinstance(run_data.get("step_meta"), dict) else {}
    results = run_data.get("results") if isinstance(run_data.get("results"), dict) else {}

    for step_id, payload in results.items():
        if not isinstance(step_id, str) or not step_id.strip() or not isinstance(payload, dict):
            continue
        method_obj = payload.get("method") if isinstance(payload.get("method"), dict) else {}
        method_hint = (
            method_obj.get("id")
            or method_obj.get("name")
            or payload.get("method_id")
        )
        if method_hint is None and isinstance(step_meta.get(step_id), dict):
            meta = step_meta.get(step_id)
            cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
            method_hint = cfg.get("method_id") or meta.get("method")
        method_id = _normalize_hypothesis_method_id(method_hint)
        if method_id:
            out[step_id] = method_id
    return out


def _build_hypothesis_discovery_context(run_data: Dict[str, Any], *, is_ru: bool) -> Dict[str, Any]:
    doc = _extract_hypothesis_discovery_doc(run_data)
    items_raw = doc.get("items") if isinstance(doc.get("items"), list) else []
    if not items_raw:
        return {"present": False}

    method_by_step = _extract_executed_methods_by_step(run_data)
    findings = _extract_protocol_findings(run_data if isinstance(run_data, dict) else {})
    findings_items = findings.get("items") if isinstance(findings.get("items"), list) else []
    findings_alpha = _safe_float(findings.get("alpha"))
    findings_by_step: Dict[str, Dict[str, Any]] = {}
    findings_by_method: Dict[str, List[Dict[str, Any]]] = {}

    for item in findings_items:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or "").strip()
        if step_id:
            findings_by_step[step_id] = item
        method_norm = _normalize_hypothesis_method_id(item.get("method"))
        if method_norm:
            findings_by_method.setdefault(method_norm, []).append(item)
    rows: List[Dict[str, Any]] = []
    covered = 0
    n_supported = 0
    n_not_supported = 0
    n_not_evaluated = 0

    for idx, item in enumerate(items_raw[:40]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("h1") or item.get("id") or f"H{idx + 1}").strip()
        h0 = str(item.get("h0") or "").strip()
        h1 = str(item.get("h1") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        priority = str(item.get("priority") or "").strip()
        suggested_raw = item.get("suggested_method")
        suggested_text = str(suggested_raw or "").strip()
        suggested_methods = _split_hypothesis_suggested_methods(suggested_raw)

        matched_steps: List[str] = []
        for step_id, method_id in method_by_step.items():
            if suggested_methods and method_id in set(suggested_methods):
                matched_steps.append(step_id)
        matched_steps = sorted(list(dict.fromkeys(matched_steps)))
        if matched_steps:
            covered += 1

        evidence_rows: List[Dict[str, Any]] = []
        seen_steps: set = set()
        for method_token in suggested_methods:
            for item in findings_by_method.get(method_token, []):
                if not isinstance(item, dict):
                    continue
                sid = str(item.get("step_id") or "").strip()
                if sid and sid in seen_steps:
                    continue
                if sid:
                    seen_steps.add(sid)
                evidence_rows.append(item)
        for sid in matched_steps:
            item = findings_by_step.get(sid)
            if not isinstance(item, dict):
                continue
            sid_norm = str(item.get("step_id") or "").strip()
            if sid_norm and sid_norm in seen_steps:
                continue
            if sid_norm:
                seen_steps.add(sid_norm)
            evidence_rows.append(item)

        sig_count = 0
        best_p: Optional[float] = None
        for ev in evidence_rows:
            if not isinstance(ev, dict):
                continue
            ev_alpha = _safe_float(ev.get("alpha")) or findings_alpha or 0.05
            p_adj = _safe_float(ev.get("p_value_adj"))
            p_raw = _safe_float(ev.get("p_value"))
            p_cmp = p_adj if p_adj is not None else p_raw
            if p_cmp is not None:
                if best_p is None or p_cmp < best_p:
                    best_p = p_cmp
            sig_flag = ev.get("significant")
            if isinstance(sig_flag, bool):
                if sig_flag:
                    sig_count += 1
            elif p_cmp is not None and ev_alpha is not None and p_cmp < ev_alpha:
                sig_count += 1

        if not evidence_rows:
            verdict = "not_evaluated"
            n_not_evaluated += 1
        elif sig_count > 0:
            verdict = "supported"
            n_supported += 1
        else:
            has_numeric_signal = any(
                _safe_float(ev.get("p_value_adj")) is not None or _safe_float(ev.get("p_value")) is not None
                for ev in evidence_rows
                if isinstance(ev, dict)
            )
            if has_numeric_signal:
                verdict = "not_supported"
                n_not_supported += 1
            else:
                verdict = "not_evaluated"
                n_not_evaluated += 1

        if verdict == "supported":
            verdict_label = "подтверждена" if is_ru else "supported"
        elif verdict == "not_supported":
            verdict_label = "не подтверждена" if is_ru else "not supported"
        else:
            verdict_label = "не оценена" if is_ru else "not evaluated"

        evidence_text = "-"
        if evidence_rows:
            steps_text = ", ".join(
                [
                    str(item.get("step_id"))
                    for item in evidence_rows
                    if isinstance(item, dict) and str(item.get("step_id") or "").strip()
                ][:6]
            ) or "-"
            p_text = _fmt_p_inline(best_p) if best_p is not None else "-"
            if is_ru:
                evidence_text = f"шаги={steps_text}; sig={sig_count}/{len(evidence_rows)}; min p={p_text}"
            else:
                evidence_text = f"steps={steps_text}; sig={sig_count}/{len(evidence_rows)}; min p={p_text}"

        rows.append(
            {
                "id": str(item.get("id") or f"h_{idx+1}"),
                "title": title or (f"H{idx + 1}" if not is_ru else f"Гипотеза {idx + 1}"),
                "h0": h0 or ("H0 не задана." if is_ru else "H0 is not specified."),
                "h1": h1 or ("H1 не задана." if is_ru else "H1 is not specified."),
                "rationale": rationale,
                "priority": priority or "-",
                "suggested_method": suggested_text or "-",
                "matched_steps": matched_steps,
                "verdict": verdict,
                "verdict_label": verdict_label,
                "evidence": evidence_text,
            }
        )

    return {
        "present": len(rows) > 0,
        "analysis_mode": str(doc.get("analysis_mode") or "-"),
        "design_type": str(doc.get("design_type") or "-"),
        "count": int(doc.get("count") or len(rows)),
        "covered": int(covered),
        "supported": int(n_supported),
        "not_supported": int(n_not_supported),
        "not_evaluated": int(n_not_evaluated),
        "rows": rows,
    }


def _protocol_validation_provenance_rows(
    run_data: Dict[str, Any],
    *,
    is_ru: bool,
    dataset_id: Any = None,
    run_id: Any = None,
) -> List[Tuple[str, str]]:
    if not isinstance(run_data, dict):
        return []

    validation = run_data.get("protocol_validation")
    if not isinstance(validation, dict):
        return []

    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    policy = validation.get("policy") if isinstance(validation.get("policy"), dict) else {}
    steps = validation.get("steps") if isinstance(validation.get("steps"), list) else []

    warning_count = 0
    warning_steps: List[str] = []
    for row in steps:
        if not isinstance(row, dict):
            continue
        warnings = row.get("warnings")
        if not isinstance(warnings, list):
            continue
        non_empty = [str(w).strip() for w in warnings if str(w).strip()]
        if not non_empty:
            continue
        warning_count += len(non_empty)
        step_id = str(row.get("step_id") or "").strip()
        if step_id:
            warning_steps.append(step_id)

    multiplicity = policy.get("multiplicity_correction")
    multiplicity_label = _format_correction_label(multiplicity, is_ru) if multiplicity else ""
    repair = policy.get("repair_correction")
    repair_label = _format_correction_label(repair, is_ru) if repair else ""
    profile = str(validation.get("policy_profile") or policy.get("profile") or "-")
    multiplicity_policy = _extract_multiplicity_policy(run_data, validation)
    multiplicity_policy_text = _format_multiplicity_policy_text(multiplicity_policy, is_ru=is_ru)
    bootstrap_policy = _extract_bootstrap_policy(run_data, validation)
    bootstrap_policy_text = _format_bootstrap_policy_text(bootstrap_policy, is_ru=is_ru)

    rows: List[Tuple[str, str]] = [
        (
            "Валидация протокола" if is_ru else "Protocol validation",
            (
                f"status={_format_validation_status_label(validation.get('status'), is_ru)}; "
                f"enabled={_format_boolean_label(validation.get('enabled'), is_ru)}; "
                f"strict={_format_boolean_label(validation.get('strict'), is_ru)}"
            ),
        ),
        (
            "Сводка валидации протокола" if is_ru else "Protocol validation summary",
            (
                f"checked={summary.get('steps_checked', '-')}; "
                f"failed={summary.get('steps_failed', '-')}; "
                f"warnings={warning_count}; "
                f"global_errors={summary.get('global_errors', '-')}"
            ),
        ),
        (
            "Политика валидации" if is_ru else "Validation policy",
            (
                f"profile={profile}; "
                f"multiplicity={(multiplicity_label or '-')}; "
                f"repair={(repair_label or '-')}; "
                f"reflection={_format_boolean_label(policy.get('reflection_enabled'), is_ru)}"
            ),
        ),
        (
            "Multiplicity-политика" if is_ru else "Multiplicity policy",
            multiplicity_policy_text,
        ),
        (
            "Bootstrap-политика" if is_ru else "Bootstrap policy",
            bootstrap_policy_text,
        ),
    ]

    warning_steps_preview = _preview_values(warning_steps, limit=8)
    if warning_steps_preview:
        rows.append(
            (
                "Шаги с предупреждениями валидатора"
                if is_ru
                else "Validator warning steps",
                warning_steps_preview,
            )
        )

    if dataset_id and run_id:
        rows.append(
            (
                "Артефакт валидации"
                if is_ru
                else "Validation artifact",
                os.path.join(
                    "workspace",
                    "datasets",
                    str(dataset_id),
                    "analysis",
                    str(run_id),
                    "artifacts",
                    "protocol_validation.json",
                ),
            )
        )
    return rows


def _compact_report_text(value: Any, max_len: int = 220) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _clean_report_messages(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = _compact_report_text(item, max_len=240)
        if text:
            out.append(text)
    return out


def _protocol_validation_section_context(run_data: Dict[str, Any], *, is_ru: bool) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return {"present": False}

    validation = run_data.get("protocol_validation")
    if not isinstance(validation, dict):
        return {"present": False}

    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    policy = validation.get("policy") if isinstance(validation.get("policy"), dict) else {}
    steps = validation.get("steps") if isinstance(validation.get("steps"), list) else []
    global_errors_raw = validation.get("global_errors") if isinstance(validation.get("global_errors"), list) else []

    global_errors: List[str] = []
    for row in global_errors_raw:
        if isinstance(row, dict):
            msg = row.get("message") or row.get("error") or row.get("detail")
            text = _compact_report_text(msg, max_len=240)
            if text:
                global_errors.append(text)

    issue_rows: List[Dict[str, str]] = []
    warning_count = 0
    for row in steps:
        if not isinstance(row, dict):
            continue
        step_status_raw = str(row.get("status") or "").strip().lower()
        errors = _clean_report_messages(row.get("errors"))
        warnings = _clean_report_messages(row.get("warnings"))
        warning_count += len(warnings)

        if step_status_raw in {"passed", "ok"} and not errors and not warnings:
            continue

        step_id = str(row.get("step_id") or "-")
        method = str(row.get("method") or "-")
        status_label = _format_validation_status_label(row.get("status"), is_ru)
        issue_bits: List[str] = []
        if errors:
            issue_bits.append(
                ("ошибки: " if is_ru else "errors: ") + "; ".join(errors[:2])
            )
        if warnings:
            issue_bits.append(
                ("предупреждения: " if is_ru else "warnings: ") + "; ".join(warnings[:2])
            )
        if not issue_bits:
            issue_bits.append("status=" + status_label)

        issue_rows.append(
            {
                "step_id": step_id,
                "method": method,
                "status": status_label,
                "issues": " | ".join(issue_bits),
            }
        )

    multiplicity = policy.get("multiplicity_correction")
    multiplicity_label = _format_correction_label(multiplicity, is_ru) if multiplicity else ""
    repair = policy.get("repair_correction")
    repair_label = _format_correction_label(repair, is_ru) if repair else ""
    profile = str(validation.get("policy_profile") or policy.get("profile") or "-")
    multiplicity_policy = _extract_multiplicity_policy(run_data, validation)
    multiplicity_policy_text = _format_multiplicity_policy_text(multiplicity_policy, is_ru=is_ru)
    bootstrap_policy = _extract_bootstrap_policy(run_data, validation)
    bootstrap_policy_text = _format_bootstrap_policy_text(bootstrap_policy, is_ru=is_ru)

    summary_rows: List[Tuple[str, str]] = [
        (
            "Статус валидации" if is_ru else "Validation status",
            _format_validation_status_label(validation.get("status"), is_ru),
        ),
        (
            "Профиль политики" if is_ru else "Policy profile",
            profile,
        ),
        (
            "Режим валидатора" if is_ru else "Validator mode",
            (
                f"enabled={_format_boolean_label(validation.get('enabled'), is_ru)}; "
                f"strict={_format_boolean_label(validation.get('strict'), is_ru)}"
            ),
        ),
        (
            "Политика поправок" if is_ru else "Correction policy",
            (
                f"multiplicity={(multiplicity_label or '-')}; "
                f"repair={(repair_label or '-')}; "
                f"reflection={_format_boolean_label(policy.get('reflection_enabled'), is_ru)}"
            ),
        ),
        (
            "Multiplicity-политика" if is_ru else "Multiplicity policy",
            multiplicity_policy_text,
        ),
        (
            "Bootstrap-политика" if is_ru else "Bootstrap policy",
            bootstrap_policy_text,
        ),
        (
            "Сводка шагов" if is_ru else "Step summary",
            (
                f"total={summary.get('steps_total', '-')}; "
                f"checked={summary.get('steps_checked', '-')}; "
                f"failed={summary.get('steps_failed', '-')}; "
                f"warnings={warning_count}; "
                f"global_errors={summary.get('global_errors', '-')}"
            ),
        ),
    ]

    return {
        "present": True,
        "summary_rows": summary_rows,
        "issues": issue_rows[:60],
        "global_errors": global_errors[:12],
    }


def _bootstrap_trace_lines(
    payload: Any,
    *,
    is_ru: bool,
    max_coef_rows: int = 6,
) -> List[str]:
    if not isinstance(payload, dict):
        return []
    if payload.get("enabled") is False:
        return []

    def _fmt_val(value: Any, digits: int = 3) -> str:
        try:
            if value is None:
                return "-"
            num = float(value)
            if not np.isfinite(num):
                return "-"
            return f"{num:.{digits}f}"
        except Exception:
            return "-"

    lines: List[str] = []
    samples = payload.get("samples")
    ci_level = payload.get("ci_level")
    method = payload.get("method")
    n_valid_models = payload.get("n_valid_models")
    header = (
        f"Bootstrap: method={method or '-'}; samples={samples if samples is not None else '-'}; "
        f"ci_level={_fmt_val(ci_level, 2)}"
    )
    if isinstance(n_valid_models, (int, float)):
        header += f"; n_valid_models={int(n_valid_models)}"
    lines.append(header)

    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    if not metrics:
        err = _compact_report_text(payload.get("error"), max_len=200)
        if err:
            lines.append(("ошибка: " if is_ru else "error: ") + err)
        return lines

    for key, val in metrics.items():
        key_s = str(key)
        if isinstance(val, dict):
            ci_l = _fmt_val(val.get("ci_lower"), 3)
            ci_u = _fmt_val(val.get("ci_upper"), 3)
            est = _fmt_val(val.get("estimate"), 3)
            n_valid = val.get("n_valid")
            lines.append(
                f"{key_s}: est={est}; CI [{ci_l}, {ci_u}]; n_valid={n_valid if n_valid is not None else '-'}"
            )
            continue

        if isinstance(val, list) and key_s == "coefficients":
            shown = 0
            for row in val:
                if not isinstance(row, dict):
                    continue
                var = str(row.get("variable") or "-")
                est = _fmt_val(row.get("estimate"), 3)
                ci_l = _fmt_val(row.get("ci_lower"), 3)
                ci_u = _fmt_val(row.get("ci_upper"), 3)
                n_valid = row.get("n_valid")
                line = f"{var}: est={est}; CI [{ci_l}, {ci_u}]; n_valid={n_valid if n_valid is not None else '-'}"
                or_l = row.get("or_ci_lower")
                or_u = row.get("or_ci_upper")
                if or_l is not None and or_u is not None:
                    line += f"; OR CI [{_fmt_val(or_l, 3)}, {_fmt_val(or_u, 3)}]"
                lines.append(line)
                shown += 1
                if shown >= max_coef_rows:
                    break
            continue

        if isinstance(val, list):
            lines.append(f"{key_s}: n={len(val)}")

    return lines


def _is_placeholder_interpretation(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip().lower()
    if not s:
        return True
    placeholders = {
        "analysis completed.",
        "analysis completed",
        "regression analysis completed.",
        "no interpretation available.",
        "n/a",
        "-",
    }
    return s in placeholders


def _extract_step_context_value(meta: Dict[str, Any], res: Dict[str, Any], keys: List[str]) -> Optional[str]:
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
        v = res.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _build_step_display(step_id: str, res: Dict[str, Any], step_meta: Dict[str, Any], is_ru: bool) -> str:
    title = step_meta.get("title") or step_meta.get("name")
    if isinstance(title, str) and title.strip():
        return title.strip()

    method_obj = res.get("method")
    method_id = ""
    if isinstance(method_obj, dict):
        method_id = str(method_obj.get("id") or method_obj.get("name") or "").strip().lower()
    elif isinstance(method_obj, str):
        method_id = method_obj.strip().lower()
    if not method_id:
        method_id = str(res.get("method_id") or "").strip().lower()

    method_label = _method_label_from_id(method_id, is_ru) if method_id else ""
    if not method_label:
        method_label = _method_label_from_type(res.get("type"), is_ru)
    if not method_label:
        method_label = step_id

    target = _extract_step_context_value(step_meta, res, ["target", "outcome", "endpoint", "y"])
    group = _extract_step_context_value(step_meta, res, ["group", "group_col", "predictor", "x"])
    corr = _extract_step_context_value(step_meta, res, ["multiplicity_correction", "correction"])
    corr_lbl = _format_correction_label(corr, is_ru) if corr else ""

    bits: List[str] = []
    if target:
        bits.append(target)
    if group:
        bits.append((("по фактору " if is_ru else "by ") + group))
    if corr_lbl:
        bits.append((("поправка " if is_ru else "correction ") + corr_lbl))

    if bits:
        return f"{method_label}: " + "; ".join(bits)
    return method_label


def _generate_fallback_interpretation(res: Dict[str, Any], step_meta: Dict[str, Any], is_ru: bool) -> Optional[str]:
    try:
        from app.modules.text_generator import TextGenerator
    except Exception:
        return None

    variables: Dict[str, Any] = {}
    target = _extract_step_context_value(step_meta, res, ["target", "outcome", "endpoint", "y"])
    group = _extract_step_context_value(step_meta, res, ["group", "group_col", "predictor", "x"])
    if target:
        variables["target"] = target
        variables["outcome"] = target
    if group:
        variables["group"] = group
        variables["predictor"] = group
    covariates = (step_meta.get("config") or {}).get("covariates") if isinstance(step_meta.get("config"), dict) else None
    if isinstance(covariates, list):
        variables["covariates"] = [str(x) for x in covariates if str(x).strip()]
        if covariates:
            variables["predictors"] = [str(x) for x in covariates if str(x).strip()]

    try:
        style = "ru" if is_ru else "pro"
        text = TextGenerator.generate_conclusion(res if isinstance(res, dict) else {}, variables, style=style)
    except Exception:
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    if _is_placeholder_interpretation(text):
        return None
    return text.strip()


def _preview_values(values: Any, limit: int = 6) -> str:
    if isinstance(values, str):
        return values.strip()
    if not isinstance(values, list):
        return ""
    cleaned = [str(v).strip() for v in values if isinstance(v, (str, int, float)) and str(v).strip()]
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    return ", ".join(cleaned[:limit]) + f", ... (n={len(cleaned)})"


def _step_scope_summary(step_meta: Dict[str, Any], res: Dict[str, Any], is_ru: bool) -> str:
    cfg = step_meta.get("config") if isinstance(step_meta.get("config"), dict) else {}
    bits: List[str] = []

    target = _extract_step_context_value(step_meta, res, ["target", "outcome", "endpoint", "y"])
    if target:
        bits.append((("исход=" if is_ru else "outcome=") + str(target)))

    targets = cfg.get("targets") if isinstance(cfg.get("targets"), list) else None
    if targets:
        bits.append((("targets: " if is_ru else "targets: ") + _preview_values(targets, limit=5)))

    group = _extract_step_context_value(step_meta, res, ["group", "group_column", "group_col", "predictor", "x"])
    if group:
        bits.append((("фактор=" if is_ru else "factor=") + str(group)))

    split_by = _extract_step_context_value(step_meta, res, ["split_by", "visit", "timepoint", "time", "time_col"])
    if split_by:
        bits.append((("срез/время=" if is_ru else "slice/time=") + str(split_by)))

    covariates = cfg.get("covariates")
    if isinstance(covariates, list) and covariates:
        bits.append((("ковариаты: " if is_ru else "covariates: ") + _preview_values(covariates, limit=4)))

    pairs = cfg.get("pairs")
    if isinstance(pairs, list) and pairs:
        pair_preview: List[str] = []
        for pair in pairs[:4]:
            if isinstance(pair, dict):
                a = pair.get("baseline") or pair.get("a")
                b = pair.get("followup") or pair.get("b")
                if a and b:
                    pair_preview.append(f"{a}->{b}")
        if pair_preview:
            pair_line = ", ".join(pair_preview)
            if len(pairs) > 4:
                pair_line += f", ... (n={len(pairs)})"
            bits.append((("пары: " if is_ru else "pairs: ") + pair_line))

    return "; ".join(bits) if bits else ("контекст не указан" if is_ru else "scope not specified")


def _batch_method_selection_rationale(step_meta: Dict[str, Any], res: Dict[str, Any], is_ru: bool) -> Optional[str]:
    cfg = step_meta.get("config") if isinstance(step_meta.get("config"), dict) else {}
    method_hint = cfg.get("method_id") or step_meta.get("method")
    method_hint_s = str(method_hint or "").strip().lower()
    normality_test = str(cfg.get("normality_test") or "").strip()
    homogeneity_test = str(cfg.get("homogeneity_test") or "").strip()
    bootstrap_ci = bool(cfg.get("bootstrap_ci"))
    bootstrap_samples = cfg.get("bootstrap_samples")
    correction = cfg.get("multiplicity_correction") or res.get("multiplicity_correction")
    correction_label = _format_correction_label(correction, is_ru) if correction else ""

    parts: List[str] = []
    if method_hint_s in {"", "auto", "none"}:
        if is_ru:
            base = "Тест для каждого показателя выбирался автоматически по предпосылкам."
            if normality_test or homogeneity_test:
                base += " "
                if normality_test:
                    base += f"Нормальность: {normality_test}. "
                if homogeneity_test:
                    base += f"Однородность дисперсий: {homogeneity_test}. "
                base = base.strip()
                if not base.endswith("."):
                    base += "."
            parts.append(base)
        else:
            base = "Per-target test selection was automatic based on assumptions."
            if normality_test or homogeneity_test:
                extra = []
                if normality_test:
                    extra.append(f"normality={normality_test}")
                if homogeneity_test:
                    extra.append(f"homogeneity={homogeneity_test}")
                base += " (" + ", ".join(extra) + ")."
            parts.append(base)
    else:
        method_label = _method_label_from_id(method_hint_s, is_ru) or str(method_hint)
        parts.append(
            ("Метод задан протоколом: " if is_ru else "Method fixed in protocol: ")
            + str(method_label)
            + "."
        )

    if bootstrap_ci:
        if is_ru:
            bs_txt = f" Бутстрэп для оценок/ДИ включен (n={bootstrap_samples})." if bootstrap_samples is not None else " Бутстрэп для оценок/ДИ включен."
        else:
            bs_txt = f" Bootstrap for estimates/CIs enabled (n={bootstrap_samples})." if bootstrap_samples is not None else " Bootstrap for estimates/CIs enabled."
        parts.append(bs_txt.strip())

    if correction_label:
        parts.append(
            ("Контроль множественных проверок: " if is_ru else "Multiple-testing control: ")
            + correction_label
            + "."
        )

    out = " ".join([p for p in parts if isinstance(p, str) and p.strip()]).strip()
    return out or None


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
        "agreement",
        "assumption_test",
        "time_series",
    }

    for item in items:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or "").strip() or "unknown_step"
        target = str(item.get("target") or "").strip()
        result_type = str(item.get("type") or "").strip().lower()
        method_raw = str(item.get("method") or "").strip()
        method_label = _method_label_from_id(method_raw, is_ru) if method_raw else ""
        if method_raw.lower() in {"auto", "none", "unknown"}:
            method_label = ""
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
    verification_status = str(findings.get("verification_status") or "").strip().lower()
    verification_present = bool(findings.get("verification_present"))
    excluded_unverified_steps = int(findings.get("excluded_unverified_steps") or 0)

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
        }
        if not is_inferential:
            continue
        inferential_total += 1
        if p_value is None:
            inferential_with_missing_p.append(str(item.get("step_id") or "unknown_step"))
        if effect is None:
            inferential_without_effect += 1

    limitations: List[str] = []
    if not verification_present:
        limitations.append(
            "Артефакт verification.json отсутствует: часть выводов может быть не верифицирована."
            if is_ru
            else "verification.json is missing: some statements may be unverified."
        )
    elif verification_status not in {"passed", "ok"}:
        limitations.append(
            "Верификатор зафиксировал ошибки; в отчёте показаны только шаги без ошибок проверки."
            if is_ru
            else "Verifier reported failures; only steps without verification failures are shown in this report."
        )
    if excluded_unverified_steps > 0:
        limitations.append(
            f"Из итогового отчёта исключено шагов из-за верификации: {excluded_unverified_steps}."
            if is_ru
            else f"Steps excluded from final report due to verification: {excluded_unverified_steps}."
        )
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

# --- Plot rendering extracted to reporting_plots.py ---
from app.modules import reporting_plots as _reporting_plots

_report_plot_theme = _reporting_plots._report_plot_theme


def _render_plot_png_bytes(res: Dict[str, Any], is_ru: bool = False) -> bytes:
    """Compatibility wrapper so monkeypatching reporting._report_plot_theme keeps working."""
    theme_fn = _report_plot_theme
    original_theme_fn = _reporting_plots._report_plot_theme
    if theme_fn is original_theme_fn:
        return _reporting_plots._render_plot_png_bytes(res, is_ru=is_ru)

    _reporting_plots._report_plot_theme = theme_fn
    try:
        return _reporting_plots._render_plot_png_bytes(res, is_ru=is_ru)
    finally:
        _reporting_plots._report_plot_theme = original_theme_fn




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
    from app.modules.reporting_html import ProtocolReport
    report = ProtocolReport(run_data, dataset_name, style=style or "gost", options=options)
    return report.generate_html()



# --- Lazy re-exports for functions extracted to sub-modules ---
# Uses __getattr__ to avoid circular imports (reporting_html/docx/pdf → reporting)
def __getattr__(name: str):
    if name == "ProtocolReport":
        from app.modules.reporting_html import ProtocolReport
        return ProtocolReport
    if name == "generate_protocol_docx_report":
        from app.modules.reporting_docx import generate_protocol_docx_report
        return generate_protocol_docx_report
    if name == "generate_pdf_report":
        from app.modules.reporting_pdf import generate_pdf_report
        return generate_pdf_report
    if name == "generate_protocol_pdf_report":
        from app.modules.reporting_pdf import generate_protocol_pdf_report
        return generate_protocol_pdf_report
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
