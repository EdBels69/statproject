import re
import unicodedata
from typing import Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd


class DataNormalizer:
    def normalize(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        out = df.copy()
        report: Dict[str, Any] = {
            "columns_renamed": {},
            "units": {},
            "boolean_converted": [],
            "numeric_converted": [],
            "numeric_conversion_ratio": {},
        }

        mapping: Dict[str, str] = {}
        units: Dict[str, str] = {}
        seen: Dict[str, int] = {}

        for idx, col in enumerate(out.columns):
            cleaned, unit = self._clean_header(col)
            if not cleaned:
                cleaned = f"column_{idx + 1}"
            base = cleaned
            if base in seen:
                seen[base] += 1
                cleaned = f"{base}_{seen[base]}"
            else:
                seen[base] = 1
            mapping[str(col)] = cleaned
            if unit:
                units[cleaned] = unit

        out = out.rename(columns=mapping)
        report["columns_renamed"] = mapping
        report["units"] = units

        boolean_cols = []
        numeric_cols = []
        numeric_ratio: Dict[str, float] = {}

        for col in out.columns:
            s = out[col]

            if pd.api.types.is_bool_dtype(s.dtype):
                out[col] = s.astype("Int64")
                boolean_cols.append(col)
                continue

            if pd.api.types.is_object_dtype(s.dtype) or pd.api.types.is_string_dtype(s.dtype) or isinstance(s.dtype, pd.CategoricalDtype):
                normalized, did_bool = self._normalize_yes_no(s)
                if did_bool:
                    out[col] = normalized
                    boolean_cols.append(col)
                    continue

                normalized_num, ratio, did_num = self._normalize_numeric(normalized)
                if did_num:
                    out[col] = normalized_num
                    numeric_cols.append(col)
                    numeric_ratio[col] = ratio

        report["boolean_converted"] = boolean_cols
        report["numeric_converted"] = numeric_cols
        report["numeric_conversion_ratio"] = numeric_ratio

        return out, report

    def _clean_header(self, name: object) -> Tuple[str, Optional[str]]:
        raw = "" if name is None else str(name)
        cleaned = raw.replace("\u00a0", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        unit = None

        m = re.search(r"[\(\[]\s*([^\)\]]+)\s*[\)\]]\s*$", cleaned)
        if m:
            candidate = m.group(1).strip()
            if self._looks_like_unit(candidate):
                unit = candidate
                cleaned = cleaned[: m.start()].strip()

        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned, unit

    def _looks_like_unit(self, token: str) -> bool:
        if not token:
            return False
        if len(token) > 30:
            return False
        if re.search(r"[a-zA-Zа-яА-Я%μµ/]+", token):
            return True
        return False

    def _normalize_yes_no(self, s: pd.Series) -> Tuple[pd.Series, bool]:
        values = s.dropna()
        if values.empty:
            return s, False

        probe = values.head(5000)
        series_str = probe.astype(str).str.strip().str.lower()
        unique = series_str.unique()
        if len(unique) > 12:
            return s, False

        yes = {
            "да",
            "yes",
            "y",
            "true",
            "истина",
            "1",
            "t",
            "верно",
            "+",
            "✓",
            "v",
        }
        no = {
            "нет",
            "no",
            "n",
            "false",
            "ложь",
            "0",
            "f",
            "-",
            "✗",
            "x",
        }

        if not all((v in yes or v in no) for v in unique):
            return s, False

        full_str = s.astype(str).str.strip().str.lower()
        mapped = full_str.map(lambda v: 1 if v in yes else (0 if v in no else pd.NA))
        out = pd.Series(mapped, index=s.index, dtype="Int64")
        return out, True

    def _normalize_numeric(self, s: pd.Series) -> Tuple[pd.Series, float, bool]:
        values = s.dropna()
        if values.empty:
            return s, 0.0, False

        probe = values.head(5000).astype(str)
        parsed = probe.map(self._parse_numeric)
        ratio = float(parsed.notna().sum()) / float(max(1, len(parsed)))

        if ratio >= 0.9 and len(parsed) >= 3:
            full = s.astype(str).map(self._parse_numeric)
            return pd.to_numeric(full, errors="coerce"), ratio, True

        return s, ratio, False

    def _parse_numeric(self, value: object) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float, np.number)):
            try:
                if np.isnan(value) or np.isinf(value):
                    return None
            except Exception:
                pass
            return float(value)

        text = str(value).strip()
        if text == "" or text.lower() in {"nan", "none", "null"}:
            return None

        text = text.replace("\u00a0", " ").replace(" ", "")
        text = text.replace("−", "-").replace("–", "-").replace("—", "-")
        if text.endswith("%"):
            text = text[:-1]

        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            text = text.replace(",", "")

        text = re.sub(r"[^0-9eE\.\-\+]", "", text)
        if text in {"", ".", "-", "+", "e", "E"}:
            return None

        try:
            return float(text)
        except Exception:
            return None


def normalize_categorical_series(s: pd.Series) -> pd.Series:
    if not (
        pd.api.types.is_object_dtype(s.dtype)
        or pd.api.types.is_string_dtype(s.dtype)
        or isinstance(s.dtype, pd.CategoricalDtype)
    ):
        raise ValueError("normalize_categories поддерживается только для текстовых/категориальных столбцов")

    def norm_one(v: object) -> str:
        text = "" if v is None else str(v)
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
        text = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
        text = text.replace("−", "-").replace("–", "-").replace("—", "-").replace("‑", "-")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    out = s.copy()
    mask = out.notna()
    if mask.any():
        out.loc[mask] = out.loc[mask].astype(str).map(norm_one)
    return out
