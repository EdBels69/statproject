import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


_SENSITIVE_RE = re.compile(
    r"(name|имя|фам|surname|phone|тел|email|e-mail|mail|паспорт|snils|address|адрес|street|улиц|passport|ssn)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
_ID_RE = re.compile(r"\b\d{6,}\b")
_SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s*\d{2}\b")
_PASSPORT_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")


def _looks_like_pii(text: str) -> bool:
    if not text:
        return False
    s = str(text).strip()
    if not s:
        return False
    if _EMAIL_RE.search(s):
        return True
    if _SNILS_RE.search(s) or _PASSPORT_RE.search(s):
        return True
    # phone-like
    if _PHONE_RE.search(s):
        digits = [c for c in s if c.isdigit()]
        if len(digits) >= 7:
            return True
    # long numeric id-like tokens
    if _ID_RE.search(s):
        return True
    return False


def _is_sensitive(col: str) -> bool:
    return bool(_SENSITIVE_RE.search(str(col or "")))


def _safe_value(val: Any, max_len: int = 80, *, col: Optional[str] = None, redact_mode: str = "pii") -> Any:
    if val is None:
        return None
    mode = str(redact_mode or "pii").strip().lower()
    if col and _is_sensitive(col):
        return "[REDACTED]"
    if isinstance(val, (np.floating, float)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    text = str(val)
    text = " ".join(text.split())
    if mode in {"strict", "full"}:
        return "[REDACTED]" if text else None
    if mode in {"pii", "mask"}:
        if _looks_like_pii(text):
            return "[REDACTED]"
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _pick_columns(
    df: pd.DataFrame,
    max_cols: int = 18,
) -> Tuple[List[str], List[str], List[str]]:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols]

    numeric_ranked = []
    if numeric_cols:
        try:
            variances = df[numeric_cols].var(numeric_only=True)
            numeric_ranked = list(variances.sort_values(ascending=False).index)
        except Exception:
            numeric_ranked = numeric_cols[:]

    cat_ranked = []
    if cat_cols:
        try:
            counts = {c: df[c].nunique(dropna=True) for c in cat_cols}
            cat_ranked = [c for c, _ in sorted(counts.items(), key=lambda kv: kv[1])]
        except Exception:
            cat_ranked = cat_cols[:]

    selected: List[str] = []
    for col in numeric_ranked:
        if col not in selected:
            selected.append(col)
        if len(selected) >= max_cols // 2:
            break
    for col in cat_ranked:
        if col not in selected:
            selected.append(col)
        if len(selected) >= max_cols:
            break

    return selected, numeric_ranked, cat_ranked


def _collect_quantile_rows(df: pd.DataFrame, col: str, quantiles: Sequence[float]) -> List[int]:
    rows: List[int] = []
    try:
        series = df[col].dropna()
        if series.empty:
            return rows
        qs = series.quantile(quantiles).drop_duplicates()
        for val in qs.tolist():
            idx = series[series == val].index
            if len(idx) > 0:
                rows.append(int(idx[0]))
    except Exception:
        return rows
    return rows


def _diversity_sample_indices(
    df: pd.DataFrame,
    numeric_cols: List[str],
    max_rows: int,
) -> List[int]:
    if max_rows <= 0:
        return []
    if df.empty or not numeric_cols:
        return []

    try:
        from sklearn.cluster import MiniBatchKMeans
        from sklearn.preprocessing import StandardScaler
    except Exception:
        return []

    numeric = df[numeric_cols].copy()
    numeric = numeric.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(numeric.median(numeric_only=True))
    if numeric.empty:
        return []

    try:
        scaler = StandardScaler()
        X = scaler.fit_transform(numeric.values)
    except Exception:
        X = numeric.values

    n_clusters = min(max_rows, X.shape[0], max(4, int(max_rows / 2)))
    if n_clusters < 2:
        return []

    try:
        kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init=3)
        labels = kmeans.fit_predict(X)
        centers = kmeans.cluster_centers_
        indices = []
        for k in range(n_clusters):
            cluster_idx = np.where(labels == k)[0]
            if cluster_idx.size == 0:
                continue
            center = centers[k]
            dists = np.linalg.norm(X[cluster_idx] - center, axis=1)
            pick = cluster_idx[int(np.argmin(dists))]
            indices.append(int(df.index[pick]))
        return indices
    except Exception:
        return []


def build_smart_sample(
    df: pd.DataFrame,
    *,
    max_rows: int = 40,
    max_cols: int = 18,
    redact_mode: str = "pii",
) -> Dict[str, Any]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"rows": [], "columns": [], "strategy": "empty"}

    max_rows = max(5, min(120, int(max_rows)))
    max_cols = max(6, min(40, int(max_cols)))

    selected_cols, numeric_ranked, cat_ranked = _pick_columns(df, max_cols=max_cols)
    if not selected_cols:
        return {"rows": [], "columns": [], "strategy": "no_columns"}

    indices: List[int] = []

    for col in cat_ranked[:6]:
        try:
            series = df[col].dropna()
            if series.empty:
                continue
            value_counts = series.value_counts().head(5)
            for value in value_counts.index.tolist():
                idx = series[series == value].index
                if len(idx) > 0:
                    indices.append(int(idx[0]))
        except Exception:
            continue

    for col in numeric_ranked[:6]:
        indices.extend(_collect_quantile_rows(df, col, [0, 0.25, 0.5, 0.75, 1.0]))

    indices.extend(_diversity_sample_indices(df, numeric_ranked[:10], max_rows=max_rows))

    if len(indices) < max_rows:
        try:
            remaining = df.index.difference(pd.Index(indices))
            extra = remaining.to_series().sample(min(max_rows - len(indices), len(remaining)), random_state=42).tolist()
            indices.extend([int(x) for x in extra])
        except Exception:
            pass

    unique_indices = []
    seen = set()
    for idx in indices:
        if idx in seen:
            continue
        seen.add(idx)
        unique_indices.append(idx)
        if len(unique_indices) >= max_rows:
            break

    rows: List[Dict[str, Any]] = []
    for idx in unique_indices:
        if idx not in df.index:
            continue
        row = {}
        for col in selected_cols:
            try:
                row[col] = _safe_value(df.at[idx, col], col=col, redact_mode=redact_mode)
            except Exception:
                row[col] = None
        rows.append(row)

    return {
        "rows": rows,
        "columns": selected_cols,
        "strategy": "diverse+stratified",
        "row_count": len(rows),
    }
