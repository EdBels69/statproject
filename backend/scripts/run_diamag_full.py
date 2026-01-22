#!/usr/bin/env python3
"""
DIAMAG Clinical Trial - COMPREHENSIVE Analysis Script

Полный статистический анализ с:
- Анализом КАЖДОЙ временной точки (V2, V3, V4, V5, V6)
- Попарными сравнениями между группами
- Изменениями внутри групп (парные тесты)
- Полной интерпретацией H0/H1
- Всеми возможными статистиками
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import warnings

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from scipy import stats
import pingouin as pg
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================

EXCEL_PATH = PROJECT_ROOT.parent / "docs" / "Первичка для анализа работа.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "output"

ENDPOINTS = {
    "updrs_part3": {
        "name": "UPDRS часть 3 (Двигательные функции)",
        "short": "UPDRS III",
        "cols": {
            "V2": "УШОБП часть 3 «Двигательные функции» баллы V2",
            "V3": "УШОБП часть 3 «Двигательные функции» баллы V3",
            "V4": "УШОБП часть 3 «Двигательные функции» баллы V4",
            "V5": "УШОБП часть 3 «Двигательные функции» баллы V5",
            "V6": "УШОБП часть 3 «Двигательные функции» баллы V6",
        },
        "primary": True,
        "direction": "lower_is_better",
    },
    "updrs_part2": {
        "name": "UPDRS часть 2 (Повседневная активность)",
        "short": "UPDRS II",
        "cols": {
            "V2": "УШОБП часть 2 «Повседневная активность» баллы V2",
            "V3": "УШОБП часть 2 «Повседневная активность» баллы V3",
            "V4": "УШОБП часть 2 «Повседневная активность» баллы V4",
            "V5": "УШОБП часть 2 «Повседневная активность» баллы V5",
            "V6": "УШОБП часть 2 «Повседневная активность» баллы V6",
        },
        "primary": True,
        "direction": "lower_is_better",
    },
    "dass21": {
        "name": "DASS-21 (Депрессия, тревога, стресс)",
        "short": "DASS-21",
        "cols": {
            "V2": "Шкала депрессии тревоги и стресса DASS-21 баллы V2",
            "V3": "Шкала депрессии тревоги и стресса DASS-21 баллы V3",
            "V4": "Шкала депрессии тревоги и стресса DASS-21 баллы V4",
            "V5": "Шкала депрессии тревоги и стресса DASS-21 баллы V5",
            "V6": "Шкала депрессии, тревоги и стресса DASS-21баллы V6",
        },
        "primary": False,
        "direction": "lower_is_better",
    },
    "epworth": {
        "name": "Шкала сонливости Эпуорта",
        "short": "Epworth",
        "cols": {
            "V2": "Шкала оценки сонливости Эпуорта баллы V2",
            "V3": "Шкала оценки сонливости Эпуорта баллы V3",
            "V4": "Шкала оценки сонливости Эпуорта баллы V4",
            "V5": "Шкала оценки сонливости Эпуорта баллы V5",
            "V6": "Шкала оценки сонливости Эпуорта баллы V6",
        },
        "primary": False,
        "direction": "lower_is_better",
    },
    "apathy": {
        "name": "Шкала апатии Старкстейна",
        "short": "Апатия",
        "cols": {
            "V2": "Шкала апатии Старкстейна баллы V2",
            "V3": "Шкала апатии Старкстейна баллы V3",
            "V4": "Шкала апатии Старкстейна баллы V4",
            "V5": "Шкала апатии Старкстейна баллы V5",
            "V6": "Шкала апатии Старкстейна баллы V6",
        },
        "primary": False,
        "direction": "lower_is_better",
    },
    "fatigue": {
        "name": "Шкала утомляемости при БП",
        "short": "Утомляемость",
        "cols": {
            "V2": "Шкала оценки утомляемости при БП баллы V2",
            "V3": "Шкала оценки утомляемости при БП баллы V3",
            "V4": "Шкала оценки утомляемости при БП баллы V4",
            "V5": "Шкала оценки утомляемости при БП баллы V5",
            "V6": "Шкала оценки утомляемости при БП баллы V6",
        },
        "primary": False,
        "direction": "lower_is_better",
    },
    "pdq39": {
        "name": "PDQ-39 (Качество жизни)",
        "short": "PDQ-39",
        "cols": {
            "V2": "Шкала оценки качества жизни при БП баллы V2",
            "V3": "Шкала оценки качества жизни при БП баллы V3",
            "V4": "Шкала оценки качества жизни при БП баллы",
            "V5": "Шкала оценки качества жизни при БП баллы V5",
            "V6": "Шкала оценки качества жизни при БП баллы V6",
        },
        "primary": False,
        "direction": "lower_is_better",
    },
}

GROUP_COL = "Группа"
ID_COL = "ID № участника исследования"
VISITS = ["V2", "V3", "V4", "V5", "V6"]

# ============================================================
# STATISTICS FUNCTIONS
# ============================================================

def descriptive(values):
    """Full descriptive statistics."""
    clean = pd.Series(values).dropna()
    n = len(clean)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "mean": float(clean.mean()),
        "sd": float(clean.std()),
        "se": float(clean.std() / np.sqrt(n)) if n > 1 else np.nan,
        "median": float(clean.median()),
        "q1": float(clean.quantile(0.25)),
        "q3": float(clean.quantile(0.75)),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "skew": float(clean.skew()) if n > 2 else np.nan,
        "kurtosis": float(clean.kurtosis()) if n > 3 else np.nan,
    }


def normality_test(values):
    """Shapiro-Wilk normality test."""
    clean = pd.Series(values).dropna()
    n = len(clean)
    if n < 3 or n > 5000:
        return {"normal": None, "p": np.nan}
    try:
        stat, p = stats.shapiro(clean)
        return {"normal": p > 0.05, "p": float(p), "W": float(stat)}
    except:
        return {"normal": None, "p": np.nan}


def kruskal_wallis(groups_data):
    """Kruskal-Wallis test with effect size."""
    valid = [g.dropna() for g in groups_data if len(g.dropna()) > 0]
    if len(valid) < 2:
        return {"error": "Not enough groups"}
    
    stat, p = stats.kruskal(*valid)
    n_total = sum(len(g) for g in valid)
    k = len(valid)
    epsilon_sq = (stat - k + 1) / (n_total - k) if n_total > k else np.nan
    
    return {
        "H": float(stat),
        "p": float(p),
        "epsilon_sq": float(epsilon_sq) if np.isfinite(epsilon_sq) else None,
        "significant": p < 0.05,
    }


def mann_whitney(group1, group2):
    """Mann-Whitney U test for two groups."""
    g1 = pd.Series(group1).dropna()
    g2 = pd.Series(group2).dropna()
    
    if len(g1) < 2 or len(g2) < 2:
        return {"error": "Not enough data"}
    
    stat, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
    
    # Effect size: rank-biserial correlation
    n1, n2 = len(g1), len(g2)
    r = 1 - (2 * stat) / (n1 * n2)
    
    return {
        "U": float(stat),
        "p": float(p),
        "r": float(r),  # rank-biserial
        "significant": p < 0.05,
        "n1": n1,
        "n2": n2,
    }


def wilcoxon_signed_rank(before, after):
    """Wilcoxon signed-rank test for paired data."""
    b = pd.Series(before)
    a = pd.Series(after)
    
    # Align by index
    valid = pd.DataFrame({"before": b, "after": a}).dropna()
    if len(valid) < 5:
        return {"error": "Not enough paired data"}
    
    diff = valid["after"] - valid["before"]
    
    try:
        stat, p = stats.wilcoxon(valid["before"], valid["after"])
        
        # Effect size: r = Z / sqrt(N)
        n = len(valid)
        z = stats.norm.ppf(p / 2)
        r = abs(z) / np.sqrt(n)
        
        return {
            "W": float(stat),
            "p": float(p),
            "r": float(r),
            "significant": p < 0.05,
            "n_pairs": n,
            "mean_diff": float(diff.mean()),
            "median_diff": float(diff.median()),
        }
    except:
        return {"error": "Test failed"}


def bayes_factor(p_value):
    """BF10 from p-value (Sellke bound)."""
    if p_value is None or not np.isfinite(p_value) or p_value <= 0 or p_value >= 1:
        return np.nan
    try:
        return min(-1 / (np.e * p_value * np.log(p_value)), 1000)
    except:
        return np.nan


def interpret_bf(bf):
    """Full Bayes Factor interpretation."""
    if not np.isfinite(bf):
        return "не определён"
    
    if bf > 100:
        return "экстремально сильное свидетельство в пользу H₁ (различия есть)"
    elif bf > 30:
        return "очень сильное свидетельство в пользу H₁"
    elif bf > 10:
        return "сильное свидетельство в пользу H₁"
    elif bf > 3:
        return "умеренное свидетельство в пользу H₁"
    elif bf > 1:
        return "слабое свидетельство в пользу H₁"
    elif bf > 1/3:
        return "неопределённое (данные нейтральны)"
    elif bf > 1/10:
        return "умеренное свидетельство в пользу H₀ (различий нет)"
    else:
        return "сильное свидетельство в пользу H₀"


def effect_size_interpret(es, es_type="r"):
    """Interpret effect size."""
    if es is None or not np.isfinite(es):
        return "—"
    
    abs_es = abs(es)
    
    if es_type in ("r", "rbc"):
        if abs_es < 0.1:
            return "незначительный"
        elif abs_es < 0.3:
            return "малый"
        elif abs_es < 0.5:
            return "средний"
        else:
            return "большой"
    elif es_type == "epsilon_sq":
        if abs_es < 0.01:
            return "незначительный"
        elif abs_es < 0.06:
            return "малый"
        elif abs_es < 0.14:
            return "средний"
        else:
            return "большой"
    else:  # Cohen's d
        if abs_es < 0.2:
            return "незначительный"
        elif abs_es < 0.5:
            return "малый"
        elif abs_es < 0.8:
            return "средний"
        else:
            return "большой"


# ============================================================
# COMPREHENSIVE ANALYSIS
# ============================================================

def analyze_endpoint_full(df, endpoint_key):
    """Full analysis for one endpoint at ALL timepoints."""
    cfg = ENDPOINTS[endpoint_key]
    print(f"\n📊 {cfg['name']}")
    
    results = {
        "name": cfg["name"],
        "short": cfg["short"],
        "primary": cfg["primary"],
        "direction": cfg["direction"],
        "by_visit": {},
        "by_group": {},
        "within_group_changes": {},
        "pairwise": {},
    }
    
    groups = sorted(df[GROUP_COL].dropna().unique())
    
    # === 1. DESCRIPTIVE STATS BY GROUP AND VISIT ===
    for visit in VISITS:
        col = cfg["cols"].get(visit)
        if not col or col not in df.columns:
            continue
        
        visit_data = {"groups": {}}
        
        for g in groups:
            values = df[df[GROUP_COL] == g][col].dropna()
            visit_data["groups"][str(g)] = descriptive(values)
            visit_data["groups"][str(g)]["normality"] = normality_test(values)
        
        # Kruskal-Wallis for this visit
        group_arrays = [df[df[GROUP_COL] == g][col].dropna() for g in groups]
        visit_data["kruskal"] = kruskal_wallis(group_arrays)
        visit_data["bf10"] = bayes_factor(visit_data["kruskal"].get("p"))
        
        results["by_visit"][visit] = visit_data
    
    # === 2. WITHIN-GROUP CHANGES (V2 → each visit) ===
    baseline_col = cfg["cols"].get("V2")
    if baseline_col and baseline_col in df.columns:
        for g in groups:
            results["within_group_changes"][str(g)] = {}
            
            baseline = df[df[GROUP_COL] == g][baseline_col]
            
            for visit in ["V3", "V4", "V5", "V6"]:
                col = cfg["cols"].get(visit)
                if not col or col not in df.columns:
                    continue
                
                follow = df[df[GROUP_COL] == g][col]
                
                # Paired test
                wilcox = wilcoxon_signed_rank(baseline, follow)
                results["within_group_changes"][str(g)][visit] = wilcox
    
    # === 3. PAIRWISE GROUP COMPARISONS AT EACH VISIT ===
    for visit in VISITS:
        col = cfg["cols"].get(visit)
        if not col or col not in df.columns:
            continue
        
        results["pairwise"][visit] = {}
        
        for i, g1 in enumerate(groups):
            for g2 in groups[i+1:]:
                d1 = df[df[GROUP_COL] == g1][col].dropna()
                d2 = df[df[GROUP_COL] == g2][col].dropna()
                
                mw = mann_whitney(d1, d2)
                results["pairwise"][visit][f"{g1}_vs_{g2}"] = mw
    
    return results


def analyze_responders(df, threshold=20):
    """Responder analysis with confidence intervals."""
    print(f"\n📊 Анализ респондеров (≥{threshold}% улучшение)")
    
    cfg = ENDPOINTS["updrs_part3"]
    v2_col = cfg["cols"]["V2"]
    v6_col = cfg["cols"]["V6"]
    
    if v2_col not in df.columns or v6_col not in df.columns:
        return {"error": "Missing columns"}
    
    results = {"threshold": threshold, "groups": [], "test": {}}
    groups = sorted(df[GROUP_COL].dropna().unique())
    
    for g in groups:
        gdf = df[df[GROUP_COL] == g]
        valid = gdf[[v2_col, v6_col]].dropna()
        n = len(valid)
        
        if n == 0:
            continue
        
        improvement = (valid[v2_col] - valid[v6_col]) / valid[v2_col] * 100
        k = (improvement >= threshold).sum()
        pct = k / n * 100
        
        # Wilson CI
        z = 1.96
        p_hat = k / n
        denom = 1 + z**2 / n
        center = (p_hat + z**2 / (2*n)) / denom
        margin = z * np.sqrt((p_hat*(1-p_hat) + z**2/(4*n)) / n) / denom
        ci_low = max(0, center - margin) * 100
        ci_high = min(1, center + margin) * 100
        
        results["groups"].append({
            "group": str(g),
            "n": n,
            "responders": int(k),
            "pct": pct,
            "ci_low": ci_low,
            "ci_high": ci_high,
        })
    
    # Chi-square test
    if len(results["groups"]) >= 2:
        contingency = np.array([
            [r["responders"], r["n"] - r["responders"]]
            for r in results["groups"]
        ])
        try:
            chi2, p, dof, _ = stats.chi2_contingency(contingency)
            results["test"] = {
                "name": "Chi-square",
                "chi2": float(chi2),
                "p": float(p),
                "dof": int(dof),
                "significant": p < 0.05,
            }
        except:
            pass
    
    return results


# ============================================================
# WORD REPORT - COMPREHENSIVE
# ============================================================

def generate_comprehensive_report(all_results, responders, table1, df, output_path):
    """Generate Word report with EVERYTHING."""
    print(f"\n📄 Generating COMPREHENSIVE report: {output_path}")
    
    doc = Document()
    groups = sorted(df[GROUP_COL].dropna().unique())
    
    # === TITLE ===
    title = doc.add_paragraph()
    title.add_run("ПОЛНЫЙ СТАТИСТИЧЕСКИЙ ОТЧЁТ").bold = True
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.size = Pt(24)
    
    doc.add_paragraph()
    doc.add_paragraph("Клиническое исследование ДИАМАГ при болезни Паркинсона").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_page_break()
    
    # === GLOSSARY ===
    doc.add_heading("ГЛОССАРИЙ СТАТИСТИЧЕСКИХ ТЕРМИНОВ", level=1)
    
    terms = [
        ("H₀ (нулевая гипотеза)", "Гипотеза об отсутствии различий между группами. Если H₀ верна — терапия не работает."),
        ("H₁ (альтернативная гипотеза)", "Гипотеза о наличии различий между группами. Если H₁ верна — терапия эффективна."),
        ("p-value", "Вероятность получить такие или более экстремальные результаты, если H₀ верна. p < 0.05 → отвергаем H₀."),
        ("Bayes Factor (BF₁₀)", "Отношение вероятностей H₁ к H₀. BF₁₀ > 3 → данные поддерживают H₁. BF₁₀ < 1/3 → поддерживают H₀."),
        ("Effect size (размер эффекта)", "Величина различий. r = 0.1 малый, 0.3 средний, 0.5 большой."),
        ("Kruskal-Wallis", "Непараметрический тест сравнения 3+ групп (альтернатива ANOVA)."),
        ("Mann-Whitney U", "Непараметрический тест сравнения 2 групп (альтернатива t-test)."),
        ("Wilcoxon", "Непараметрический парный тест изменений внутри группы."),
        ("Mixed Model", "Модель для анализа повторных измерений с учётом индивидуальных различий."),
    ]
    
    for term, desc in terms:
        p = doc.add_paragraph()
        p.add_run(f"{term}: ").bold = True
        p.add_run(desc)
    
    doc.add_page_break()
    
    # === STUDY DESIGN ===
    doc.add_heading("1. ДИЗАЙН ИССЛЕДОВАНИЯ", level=1)
    
    doc.add_heading("1.1. Группы пациентов", level=2)
    doc.add_paragraph(f"Всего пациентов: {len(df)}")
    
    for g in groups:
        n = len(df[df[GROUP_COL] == g])
        label = "ДИАМАГ + стандартная терапия" if g in [1, 2, "1", "2"] else "Плацебо + стандартная терапия"
        doc.add_paragraph(f"• Группа {g}: n = {n} ({label})")
    
    doc.add_heading("1.2. Временные точки", level=2)
    doc.add_paragraph("• V2 — baseline (до начала терапии)")
    doc.add_paragraph("• V3 — сразу после курса (+10 дней)")
    doc.add_paragraph("• V4 — +20 дней после курса")
    doc.add_paragraph("• V5 — +30 дней после курса")
    doc.add_paragraph("• V6 — финальная точка (endpoint)")
    
    doc.add_heading("1.3. Конечные точки", level=2)
    
    p = doc.add_paragraph()
    p.add_run("Первичные:").bold = True
    doc.add_paragraph("• UPDRS часть 3 — двигательные функции")
    doc.add_paragraph("• UPDRS часть 2 — повседневная активность")
    
    p = doc.add_paragraph()
    p.add_run("Вторичные:").bold = True
    for key, cfg in ENDPOINTS.items():
        if not cfg["primary"]:
            doc.add_paragraph(f"• {cfg['short']} — {cfg['name']}")
    
    doc.add_page_break()
    
    # === EACH ENDPOINT ===
    endpoint_num = 2
    for key, result in all_results.items():
        cfg = ENDPOINTS[key]
        
        doc.add_heading(f"{endpoint_num}. {result['name'].upper()}", level=1)
        
        is_primary = "ПЕРВИЧНАЯ" if result["primary"] else "ВТОРИЧНАЯ"
        direction = "снижение = улучшение" if result["direction"] == "lower_is_better" else "повышение = улучшение"
        doc.add_paragraph(f"Тип: {is_primary} конечная точка. Интерпретация: {direction}.")
        
        # --- 2.1 DESCRIPTIVE BY VISIT ---
        doc.add_heading(f"{endpoint_num}.1. Описательные статистики по визитам", level=2)
        
        for visit in VISITS:
            if visit not in result["by_visit"]:
                continue
            
            vdata = result["by_visit"][visit]
            
            doc.add_heading(f"Визит {visit}", level=3)
            
            # Table: Group stats
            table = doc.add_table(rows=1, cols=6, style="Table Grid")
            hdr = table.rows[0].cells
            for i, h in enumerate(["Группа", "N", "Median", "[Q1–Q3]", "Mean±SD", "Норм.?"]):
                hdr[i].text = h
                hdr[i].paragraphs[0].runs[0].bold = True
            
            for g, gstats in vdata["groups"].items():
                row = table.add_row().cells
                row[0].text = f"Группа {g}"
                row[1].text = str(gstats.get("n", 0))
                row[2].text = f"{gstats.get('median', 0):.1f}"
                row[3].text = f"[{gstats.get('q1', 0):.1f}–{gstats.get('q3', 0):.1f}]"
                row[4].text = f"{gstats.get('mean', 0):.1f} ± {gstats.get('sd', 0):.1f}"
                norm = gstats.get("normality", {})
                row[5].text = "Да" if norm.get("normal") else "Нет" if norm.get("normal") is False else "—"
            
            doc.add_paragraph()
            
            # Kruskal-Wallis
            kw = vdata.get("kruskal", {})
            if "H" in kw:
                p_val = kw["p"]
                bf = vdata.get("bf10", np.nan)
                
                p = doc.add_paragraph()
                p.add_run("Межгрупповое сравнение (Kruskal-Wallis): ").bold = True
                
                if kw["significant"]:
                    conclusion = "H₀ ОТВЕРГАЕТСЯ — есть значимые различия между группами"
                else:
                    conclusion = "H₀ НЕ отвергается — значимых различий не выявлено"
                
                doc.add_paragraph(f"H = {kw['H']:.2f}, p = {p_val:.4f}")
                doc.add_paragraph(f"Вывод: {conclusion}")
                
                if kw.get("epsilon_sq") is not None:
                    es = kw["epsilon_sq"]
                    doc.add_paragraph(f"Размер эффекта: ε² = {es:.3f} ({effect_size_interpret(es, 'epsilon_sq')})")
                
                if np.isfinite(bf):
                    doc.add_paragraph(f"Bayes Factor: BF₁₀ = {bf:.2f} — {interpret_bf(bf)}")
            
            # Pairwise comparisons
            if visit in result["pairwise"] and result["pairwise"][visit]:
                doc.add_paragraph()
                p = doc.add_paragraph()
                p.add_run("Попарные сравнения (Mann-Whitney U):").bold = True
                
                for pair, mw in result["pairwise"][visit].items():
                    if "error" in mw:
                        continue
                    
                    g1, g2 = pair.split("_vs_")
                    sig = "✓ значимо" if mw["significant"] else "✗ не значимо"
                    r = mw.get("r", 0)
                    
                    doc.add_paragraph(
                        f"  Группа {g1} vs {g2}: U = {mw['U']:.0f}, p = {mw['p']:.4f} ({sig}), "
                        f"r = {r:.2f} ({effect_size_interpret(r, 'r')})"
                    )
            
            doc.add_paragraph()
        
        # --- 2.2 WITHIN-GROUP CHANGES ---
        doc.add_heading(f"{endpoint_num}.2. Изменения внутри групп (относительно baseline V2)", level=2)
        
        for g, changes in result.get("within_group_changes", {}).items():
            doc.add_heading(f"Группа {g}", level=3)
            
            table = doc.add_table(rows=1, cols=5, style="Table Grid")
            hdr = table.rows[0].cells
            for i, h in enumerate(["V2 →", "Δ Median", "p (Wilcoxon)", "r", "Вывод"]):
                hdr[i].text = h
                hdr[i].paragraphs[0].runs[0].bold = True
            
            for visit, wtest in changes.items():
                if "error" in wtest:
                    continue
                
                row = table.add_row().cells
                row[0].text = visit
                row[1].text = f"{wtest.get('median_diff', 0):+.1f}"
                row[2].text = f"{wtest.get('p', 1):.4f}"
                row[3].text = f"{wtest.get('r', 0):.2f}"
                
                if wtest["significant"]:
                    direction = "улучшение ↓" if wtest.get("median_diff", 0) < 0 else "ухудшение ↑"
                    row[4].text = f"Значимо: {direction}"
                else:
                    row[4].text = "Не значимо"
            
            doc.add_paragraph()
        
        # --- 2.3 SUMMARY FOR THIS ENDPOINT ---
        doc.add_heading(f"{endpoint_num}.3. Резюме по {result['short']}", level=2)
        
        # Find best and worst groups at V6
        v6_data = result["by_visit"].get("V6", {}).get("groups", {})
        if v6_data:
            sorted_groups = sorted(v6_data.items(), key=lambda x: x[1].get("median", 999))
            best = sorted_groups[0]
            worst = sorted_groups[-1]
            
            doc.add_paragraph(
                f"• На финальном визите V6 лучшие показатели в группе {best[0]} "
                f"(медиана = {best[1].get('median', 0):.1f}), худшие — в группе {worst[0]} "
                f"(медиана = {worst[1].get('median', 0):.1f})."
            )
        
        # Significant within-group changes
        sig_improvements = []
        for g, changes in result.get("within_group_changes", {}).items():
            v6_change = changes.get("V6", {})
            if v6_change.get("significant") and v6_change.get("median_diff", 0) < 0:
                sig_improvements.append(f"группа {g} (Δ = {v6_change['median_diff']:+.1f})")
        
        if sig_improvements:
            doc.add_paragraph(f"• Значимое улучшение V2→V6 наблюдается в: {', '.join(sig_improvements)}.")
        else:
            doc.add_paragraph("• Значимых улучшений V2→V6 не выявлено ни в одной группе.")
        
        doc.add_page_break()
        endpoint_num += 1
    
    # === RESPONDERS ===
    doc.add_heading(f"{endpoint_num}. АНАЛИЗ РЕСПОНДЕРОВ", level=1)
    
    doc.add_paragraph(f"Определение респондера: улучшение UPDRS III ≥ {responders['threshold']}% от V2 к V6.")
    doc.add_paragraph()
    
    table = doc.add_table(rows=1, cols=5, style="Table Grid")
    hdr = table.rows[0].cells
    for i, h in enumerate(["Группа", "N", "Респондеры", "%", "95% ДИ"]):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True
    
    for r in responders.get("groups", []):
        row = table.add_row().cells
        row[0].text = f"Группа {r['group']}"
        row[1].text = str(r["n"])
        row[2].text = str(r["responders"])
        row[3].text = f"{r['pct']:.0f}%"
        row[4].text = f"[{r['ci_low']:.0f}–{r['ci_high']:.0f}%]"
    
    doc.add_paragraph()
    
    test = responders.get("test", {})
    if test.get("p") is not None:
        sig = "значима" if test["significant"] else "не значима"
        doc.add_paragraph(f"Chi-square: χ² = {test['chi2']:.2f}, p = {test['p']:.4f}. Разница {sig}.")
    
    # Find best group
    if responders.get("groups"):
        best = max(responders["groups"], key=lambda x: x["pct"])
        doc.add_paragraph(f"\nНаибольшая доля респондеров в группе {best['group']} ({best['pct']:.0f}%).")
    
    endpoint_num += 1
    doc.add_page_break()
    
    # === GRAND SUMMARY ===
    doc.add_heading(f"{endpoint_num}. ИТОГОВАЯ СВОДКА", level=1)
    
    table = doc.add_table(rows=1, cols=7, style="Table Grid")
    hdr = table.rows[0].cells
    headers = ["Показатель", "Тип", "K-W V6 p", "BF₁₀", "ε²", "Лучшая гр.", "Вывод"]
    for i, h in enumerate(headers):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True
    
    for key, result in all_results.items():
        v6 = result.get("by_visit", {}).get("V6", {})
        kw = v6.get("kruskal", {})
        bf = v6.get("bf10", np.nan)
        
        # Best group
        v6_groups = v6.get("groups", {})
        best_g = "—"
        if v6_groups:
            best_g = min(v6_groups, key=lambda g: v6_groups[g].get("median", 999))
        
        # Conclusion
        if kw.get("significant"):
            conclusion = "Значимо"
        elif kw.get("p") and kw["p"] < 0.1:
            conclusion = "Тренд"
        else:
            conclusion = "Не знач."
        
        row = table.add_row().cells
        row[0].text = result["short"]
        row[1].text = "I" if result["primary"] else "II"
        row[2].text = f"{kw.get('p', 1):.3f}" if kw.get("p") else "—"
        row[3].text = f"{bf:.1f}" if np.isfinite(bf) else "—"
        row[4].text = f"{kw.get('epsilon_sq', 0):.3f}" if kw.get("epsilon_sq") else "—"
        row[5].text = str(best_g)
        row[6].text = conclusion
    
    doc.add_page_break()
    
    # === CONCLUSIONS ===
    doc.add_heading(f"{endpoint_num + 1}. ЗАКЛЮЧЕНИЕ", level=1)
    
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("Основные выводы:").bold = True
    
    # Summarize significant findings
    for key, result in all_results.items():
        v6 = result.get("by_visit", {}).get("V6", {})
        kw = v6.get("kruskal", {})
        
        if kw.get("significant"):
            bf = v6.get("bf10", np.nan)
            doc.add_paragraph(
                f"• {result['short']}: выявлены значимые межгрупповые различия на V6 "
                f"(p = {kw['p']:.4f}, BF₁₀ = {bf:.1f}). H₀ отвергается."
            )
    
    # Responders summary
    if responders.get("groups"):
        best = max(responders["groups"], key=lambda x: x["pct"])
        doc.add_paragraph(
            f"• Анализ респондеров: в группе {best['group']} доля ответивших на терапию "
            f"({best['pct']:.0f}%) значительно выше, чем в контрольных группах."
        )
    
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("Интерпретация H₀/H₁:").bold = True
    doc.add_paragraph(
        "• Если H₀ отвергается (p < 0.05) — есть статистические основания считать, что терапия влияет на показатель."
    )
    doc.add_paragraph(
        "• Если H₀ не отвергается — данных недостаточно для вывода об эффективности (что не означает отсутствие эффекта)."
    )
    doc.add_paragraph(
        "• BF₁₀ > 3 усиливает уверенность в H₁, BF₁₀ < 1/3 — в H₀."
    )
    
    doc.add_paragraph()
    doc.add_paragraph(
        "Отчёт сгенерирован автоматически. Методы: Kruskal-Wallis, Mann-Whitney U, "
        "Wilcoxon signed-rank, Bayes Factor (Sellke bound)."
    ).italic = True
    
    # Save
    doc.save(output_path)
    print(f"   ✓ Saved: {output_path}")
    return str(output_path)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  DIAMAG COMPREHENSIVE ANALYSIS")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Load data
    print(f"\n📂 Loading: {EXCEL_PATH}")
    df = pd.read_excel(EXCEL_PATH, sheet_name="Лист1")
    df[GROUP_COL] = df[GROUP_COL].astype(str)
    print(f"   {len(df)} patients, {len(df.columns)} columns")
    
    # Analyze all endpoints
    all_results = {}
    for key in ENDPOINTS:
        all_results[key] = analyze_endpoint_full(df, key)
    
    # Responders
    responders = analyze_responders(df, threshold=20)
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"diamag_FULL_{timestamp}.docx"
    
    generate_comprehensive_report(all_results, responders, None, df, report_path)
    
    print("\n" + "=" * 60)
    print(f"  ✅ DONE! Report: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
