"""Legacy-compatible clinical utility helpers.

This module exists as a compatibility shim for older tests/import paths.
New analytical code should prefer explicit protocol rules and engine adapters.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

import pandas as pd


def discover_longitudinal_groups(
    df: pd.DataFrame,
    visits: Optional[Iterable[str]],
) -> Dict[str, Dict[str, str]]:
    """Group repeated-measure columns by base marker and visit label.

    Example:
    - HGB_V1, HGB_V2 -> {"HGB": {"V1": "HGB_V1", "V2": "HGB_V2"}}
    """

    if not isinstance(df, pd.DataFrame):
        return {}
    visit_list = [str(v).strip() for v in (visits or []) if str(v).strip()]
    if not visit_list:
        return {}

    out: Dict[str, Dict[str, str]] = {}
    for raw_col in list(df.columns):
        col = str(raw_col).strip()
        if not col:
            continue

        for visit in visit_list:
            # Accept suffixes like _V1, -V1, .V1, " V1", or plain V1 at end.
            m = re.match(rf"^(?P<base>.+?)[_\-.\s]*{re.escape(visit)}$", col, flags=re.IGNORECASE)
            if not m:
                continue

            base = str(m.group("base") or "").strip(" _-.")
            if not base:
                continue
            bucket = out.setdefault(base, {})
            bucket[visit] = col
            break

    return out

