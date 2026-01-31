import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

from app.stats.engine import _bf10_from_p_value_bound
from app.modules.plot_with_brackets import add_significance_bracket, normalize_comparisons
from app.modules.plot_config import apply_publication_config


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


def _render_plot_png_bytes(res: Dict[str, Any], is_ru: bool = False) -> bytes:
    try:
        apply_publication_config()
        base_type = res.get("type") if isinstance(res, dict) else None

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
                        cmap="Blues",
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
                for g in groups:
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
                    plt.errorbar(xs, ys, yerr=yerr_arr, marker="o", linewidth=2, capsize=3, label=str(g))

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
                    cmap="vlag",
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
                sns.boxplot(x="group", y="value", data=df_plot, showfliers=False, color="lightblue", width=0.5)
                sns.stripplot(
                    x="group",
                    y="value",
                    data=df_plot,
                    size=4,
                    alpha=0.6,
                    color="#0f172a",
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
                                color="#0f172a",
                            )

            elif "x" in df_plot.columns and "y" in df_plot.columns:
                if plot_config.get("type") == "line":
                    df_sorted = df_plot.sort_values("x")
                    plt.plot(df_sorted["x"], df_sorted["y"], color="#8b5cf6", linewidth=2)
                    plt.plot([0, 1], [0, 1], linestyle="--", color="#666", linewidth=1)
                    plt.xlim(0, 1)
                    plt.ylim(0, 1)
                    plt.title("ROC-кривая" if is_ru else "ROC Curve")
                    plt.xlabel("1 − специфичность" if is_ru else "1 − Specificity")
                    plt.ylabel("Чувствительность" if is_ru else "Sensitivity")
                else:
                    sns.scatterplot(x="x", y="y", data=df_plot)
                    sns.regplot(x="x", y="y", data=df_plot, scatter=False, color="red")
                    plt.title("Корреляция" if is_ru else "Correlation Analysis")
                    plt.xlabel(str(res.get("x_label") or "X"))
                    plt.ylabel(str(res.get("y_label") or "Y"))

            elif "probability" in df_plot.columns and "time" in df_plot.columns and "group" in df_plot.columns:
                groups = df_plot["group"].unique()
                for g in groups:
                    sub = df_plot[df_plot["group"] == g]
                    plt.step(
                        sub["time"],
                        sub["probability"],
                        where="post",
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
                    plt.bar(groups, means, yerr=sems, capsize=5, color="skyblue", alpha=0.8)
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
    except Exception:
        try:
            plt.close()
        except Exception:
            pass
        return b""
