import pandas as pd
import numpy as np
import math
from typing import Dict, Any, List
from app.stats.engine import check_normality


def _safe_float(value):
    """Convert to JSON-safe float. Returns None for inf, -inf, nan."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None

class SmartScanner:
    """
    Analyzes a DataFrame for common "Dirty Data" problems and scientific metadata.
    Output: A comprehensive 'Scan Report' used by the frontend Cleaning Wizard.
    """
    
    def scan_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Single-pass analysis:
        1. Basic Stats (Rows, Cols, Head) - formerly Profiler
        2. Deep Scan (Mixed types, Normality) - SmartScanner
        
        Returns: {
            "profile": { ... }, # For UI basic view
            "report": { ... }   # For Cleaning Wizard
        }
        """
        # --- 1. Basic Metadata ---
        # Replace inf/-inf and nan with None for JSON serialization
        safe_head = df.head(10).copy()
        for col in safe_head.columns:
            if pd.api.types.is_numeric_dtype(safe_head[col]):
                safe_head[col] = safe_head[col].replace([np.inf, -np.inf], np.nan)
        safe_head = safe_head.replace({np.nan: None})
        
        profile = {
            "row_count": len(df),
            "col_count": len(df.columns),
            "head": safe_head.to_dict(orient="records") 
        }

        # --- 2. Deep Scan ---
        report = {
            "columns": {},
            "issues": [],
            "reorder_suggestion": [],
            "missing_report": {
                "total_rows": int(len(df)),
                "columns_with_missing": 0,
                "by_column": []
            }
        }

        missing_by_column = []
        
        for col in df.columns:
            # Analyze column (Combines profiling + smart checks)
            col_report = self._analyze_column(df[col], str(col))
            report["columns"][str(col)] = col_report
            
            # Identify Issues
            if col_report.get("mixed_type_suspected"):
                report["issues"].append({
                    "column": str(col),
                    "type": "mixed_type",
                    "severity": "high",
                    "details": f"Contains {col_report['numeric_convertible_percent']}% numbers but formatted as text."
                })

            missing_count = int(col_report.get("missing_count") or 0)
            if missing_count > 0:
                missing_percent = round((missing_count / max(1, len(df))) * 100, 2)
                missing_by_column.append({
                    "column": str(col),
                    "missing_count": missing_count,
                    "missing_percent": missing_percent,
                    "total": int(len(df))
                })

                report["issues"].append({
                    "column": str(col),
                    "type": "missing",
                    "severity": "medium",
                    "details": f"{missing_count} missing ({missing_percent}%)."
                })
        
        # Reorder suggestions
        report["reorder_suggestion"] = self._suggest_order(df, report["columns"])

        missing_by_column.sort(key=lambda x: x["missing_count"], reverse=True)
        report["missing_report"] = {
            "total_rows": int(len(df)),
            "columns_with_missing": int(len(missing_by_column)),
            "by_column": missing_by_column
        }

        # Merge for API convenience
        # The frontend expects 'profile' to be the top level object for /upload response
        # But we also want the report.
        # Let's return a combined dict that can satisfy both needs or splits them.
        return {
            "profile": {
                **profile, 
                "columns": [v for k,v in report["columns"].items()] # Array format for some UI components
            },
            "scan_report": report
        }

    def optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        for col in out.columns:
            try:
                s = out[col]

                if pd.api.types.is_integer_dtype(s.dtype):
                    out[col] = pd.to_numeric(s, downcast="integer")
                    continue

                if pd.api.types.is_float_dtype(s.dtype):
                    out[col] = pd.to_numeric(s, downcast="float")
                    continue

                if pd.api.types.is_bool_dtype(s.dtype) or isinstance(s.dtype, pd.CategoricalDtype):
                    continue

                if pd.api.types.is_object_dtype(s.dtype) or pd.api.types.is_string_dtype(s.dtype):
                    # First ensure all values are strings to avoid type errors
                    s_str = s.astype(str) if s.dtype == object else s
                    numeric_converted = pd.to_numeric(s_str, errors="coerce")
                    non_null = s.notna().sum()
                    numeric_non_null = numeric_converted.notna().sum()

                    if non_null > 0 and (numeric_non_null / non_null) >= 0.9:
                        out[col] = pd.to_numeric(s_str, errors="coerce")
                        if pd.api.types.is_integer_dtype(out[col].dropna().dtype):
                            out[col] = pd.to_numeric(out[col], downcast="integer")
                        elif pd.api.types.is_float_dtype(out[col].dtype):
                            out[col] = pd.to_numeric(out[col], downcast="float")
                        continue

                    unique_count = int(s.nunique(dropna=True))
                    if unique_count > 0:
                        unique_ratio = unique_count / max(1, int(non_null))
                        if unique_count <= 200 and unique_ratio <= 0.2:
                            out[col] = s.astype("category")
            except Exception as e:
                # If optimization fails for a column, leave it unchanged
                # This handles Excel files with unusual/mixed data types
                pass

        return out

    def _analyze_column(self, series: pd.Series, name: str) -> Dict[str, Any]:
        """
        Deep dive into a single column.
        """
        unique_c = series.nunique()
        
        stats = {
            "name": name,
            "type": str(series.dtype), # Schema expects "type"
            "missing_count": int(series.isnull().sum()), # Schema expects "missing_count"
            "unique_count": unique_c, # Schema expects "unique_count"
            "total": len(series)
        }
        
        # A. Detect Mixed Types (Numbers hidden in Object columns)
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
            # Try converting to numeric
            numeric_converted = pd.to_numeric(series, errors='coerce')
            num_count = numeric_converted.notna().sum()
            total_count = len(series)
            
            if num_count > 0 and num_count / total_count > 0.5:
                # Suspicious: >50% are numbers, but it's an object column (likely pollution)
                stats["mixed_type_suspected"] = True
                stats["numeric_convertible_percent"] = round((num_count / total_count) * 100, 1)
                
                # Find the "Polluters" (values that are NaN after conversion but weren't before)
                # Note: this is expensive for large sets, so we sample
                polluters = series[numeric_converted.isna() & series.notna()].unique()[:5]
                stats["polluting_values"] = [str(x) for x in polluters]

        # B. Normality Check (If Numeric)
        if pd.api.types.is_numeric_dtype(series.dtype):
            is_normal, p_val, _ = check_normality(series)
            
            # Shapiro limit check inside check_normality, but result implies:
            stats["normality"] = {
                "is_normal": is_normal,
                "p_value": _safe_float(p_val)
            }
            
            # Simple Desc - use _safe_float to handle inf/nan values
            stats["mean"] = _safe_float(series.mean())
            stats["min"] = _safe_float(series.min())
            stats["max"] = _safe_float(series.max())
            stats["example"] = _safe_float(series.iloc[0]) if len(series) > 0 else None

            try:
                clean = series.replace([np.inf, -np.inf], np.nan).dropna()
                if len(clean) >= 10:
                    counts, edges = np.histogram(clean.to_numpy(dtype=float), bins=12)
                    stats["histogram"] = {
                        "bins": [int(x) for x in counts.tolist()],
                        "edges": [_safe_float(x) for x in edges.tolist()],
                    }
            except Exception:
                pass

        # C. Categorical Intelligence
        if pd.api.types.is_object_dtype(series.dtype) or isinstance(series.dtype, pd.CategoricalDtype):
             if unique_c < 20:
                 stats["categories"] = [str(x) for x in series.dropna().unique()]
             try:
                 top = series.dropna().astype(str).value_counts().head(3)
                 stats["top_values"] = [
                     {"value": str(idx), "count": int(cnt)}
                     for idx, cnt in top.items()
                 ]
             except Exception:
                 pass
             stats["example"] = str(series.iloc[0]) if len(series) > 0 else None
        
        return stats


    def _suggest_order(self, df: pd.DataFrame, col_reports: Dict) -> List[str]:
        """
        Suggests a logical column order: ID -> Categorical/Groups -> Numeric -> Text/Other
        """
        ids = []
        cats = []
        nums = []
        others = []
        
        for col in df.columns:
            c = str(col)
            report = col_reports.get(c, {})
            
            # ID heuristics
            if "id" in c.lower() or "code" in c.lower() or report.get("unique_count") == len(df):
                ids.append(c)
                continue
                
            dtype = report.get("dtype", "")
            if "int" in dtype or "float" in dtype:
                nums.append(c)
            elif "object" in dtype or "category" in dtype:
                if report.get("unique_count", 999) < 20:
                    cats.append(c)
                else:
                    others.append(c) # High cardinality text
            else:
                others.append(c)
                
        return ids + cats + nums + others
