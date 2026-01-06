import pandas as pd
import numpy as np
from typing import Dict, Any, List
from app.stats.engine import check_normality

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
        profile = {
            "row_count": len(df),
            "col_count": len(df.columns),
            # Generate safe head for JSON
            "head": df.head(10).replace({np.nan: None}).to_dict(orient="records") 
        }

        # --- 2. Deep Scan ---
        report = {
            "columns": {},
            "issues": [],
            "reorder_suggestion": []
        }
        
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
        
        # Reorder suggestions
        report["reorder_suggestion"] = self._suggest_order(df, report["columns"])

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
                "p_value": float(p_val)
            }
            
            # Simple Desc
            stats["mean"] = float(series.mean())
            stats["min"] = float(series.min())
            stats["max"] = float(series.max())
            stats["example"] = float(series.iloc[0]) if len(series) > 0 else None

        # C. Categorical Intelligence
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_categorical_dtype(series.dtype):
             if unique_c < 20:
                 stats["categories"] = [str(x) for x in series.dropna().unique()]
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
