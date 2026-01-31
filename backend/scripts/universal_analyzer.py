#!/usr/bin/env python3
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.modules.data_normalizer import DataNormalizer
from app.modules.study_detector import StudyDetector
from app.stats.engine import run_analysis
from app.llm import interpret_general_summary, interpret_discussion, interpret_conclusions


def _load_dataframe(path: Path, sheet: Optional[str]) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet or 0)
    return pd.read_csv(path, sep=None, engine="python")


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _describe_by_group(df: pd.DataFrame, value_col: str, group_col: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if group_col not in df.columns:
        return out
    for group, sub in df.groupby(group_col):
        s = sub[value_col].dropna()
        out[str(group)] = {
            "n": int(s.shape[0]),
            "mean": float(s.mean()) if s.shape[0] else None,
            "median": float(s.median()) if s.shape[0] else None,
        }
    return out


def _build_endpoint_results(df: pd.DataFrame, detection: Dict[str, Any]) -> Dict[str, Any]:
    group_col = detection.get("group_column") or None
    endpoint_groups = detection.get("endpoint_groups") or []
    results: Dict[str, Any] = {"endpoints": []}
    for endpoint in endpoint_groups:
        endpoint_name = endpoint.get("endpoint")
        cols = endpoint.get("columns") or []
        timepoints = endpoint.get("timepoints") or []
        comparisons: Dict[str, Any] = {}
        descriptives: Dict[str, Any] = {}
        for col in cols:
            if col not in df.columns:
                continue
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue
            label = None
            for t in timepoints:
                if str(t).lower() in str(col).lower():
                    label = t
                    break
            label = label or str(col)
            if group_col and group_col in df.columns:
                try:
                    res = run_analysis(df, "auto", col, group_col)
                except Exception:
                    res = None
                comparisons[str(label)] = res
                descriptives[str(label)] = _describe_by_group(df, col, group_col)
        results["endpoints"].append(
            {
                "endpoint": endpoint_name,
                "timepoints": timepoints,
                "columns": cols,
                "comparisons": comparisons,
                "descriptives": descriptives,
            }
        )
    return results


async def _generate_llm_sections(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = {
        "study_detection": payload.get("study_detection"),
        "normalization_report": payload.get("normalization_report"),
        "sample_size": payload.get("sample_size"),
    }
    results = payload.get("results") or {}
    general = await interpret_general_summary(results=results, hypotheses=context)
    discussion = await interpret_discussion(context=context, results=results)
    conclusions = await interpret_conclusions(context=context, results=results)
    return {"general_summary": general, "discussion": discussion, "conclusions": conclusions}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, nargs="?")
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--output", type=str, default="backend/output/universal")
    parser.add_argument("--export-openapi", action="store_true")
    parser.add_argument("--openapi-output", type=str, default="backend/artifacts/openapi.json")
    args = parser.parse_args()

    if args.export_openapi:
        from app.main import app

        output_path = Path(args.openapi_output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2))
        print(str(output_path))
        return 0

    if not args.input:
        parser.error("input is required unless --export-openapi is provided")

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    df_raw = _load_dataframe(input_path, args.sheet)
    normalizer = DataNormalizer()
    df, normalization_report = normalizer.normalize(df_raw)

    detector = StudyDetector()
    detection = detector.detect(df)

    results = _build_endpoint_results(df, detection)

    payload = {
        "source": str(input_path),
        "sample_size": int(df.shape[0]),
        "normalization_report": normalization_report,
        "study_detection": detection,
        "results": results,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    llm_sections = asyncio.run(_generate_llm_sections(payload))
    payload["llm"] = llm_sections

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"universal_analysis_{timestamp}.json"
    out_path.write_text(json.dumps(_sanitize(payload), ensure_ascii=False, indent=2))
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
