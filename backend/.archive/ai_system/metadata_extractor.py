"""
Smart Metadata Extractor: Extracts intelligent metadata from large DataFrames.

Purpose:
    Convert 100M cells → 5KB JSON for LLM analysis
    Detect patterns, roles, families automatically
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import re
from collections import Counter


class MetadataExtractor:
    """
    Extracts comprehensive metadata from DataFrame without sending data to LLM.
    """
    
    def extract(self, df: pd.DataFrame, max_samples: int = 5) -> Dict[str, Any]:
        """
        Extract smart metadata for LLM decision-making.
        
        Args:
            df: DataFrame to analyze
            max_samples: Number of sample values to include
            
        Returns:
            Comprehensive metadata dict
        """
        metadata = {
            "shape": {
                "rows": len(df),
                "cols": len(df.columns),
                "total_cells": len(df) * len(df.columns),
                "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
            },
            "columns": [],
            "detected_families": [],
            "detected_structure": None,
            "quality_summary": {
                "total_missing_pct": round(df.isna().sum().sum() / (len(df) * len(df.columns)) * 100, 2),
                "columns_with_missing": int((df.isna().sum() > 0).sum()),
                "duplicate_rows": int(df.duplicated().sum())
            }
        }
        
        # Analyze each column
        for col in df.columns:
            col_metadata = self._analyze_column(df, col, max_samples)
            metadata["columns"].append(col_metadata)
        
        # Detect longitudinal families
        metadata["detected_families"] = self._detect_families([c["name"] for c in metadata["columns"]])
        
        # Detect overall structure
        metadata["detected_structure"] = self._detect_structure(metadata)
        
        return metadata
    
    def _analyze_column(self, df: pd.DataFrame, col: str, max_samples: int) -> Dict[str, Any]:
        """Analyze single column comprehensively."""
        series = df[col]
        
        # Basic stats
        col_info = {
            "name": col,
            "dtype": str(series.dtype),
            "unique_count": int(series.nunique()),
            "missing_count": int(series.isna().sum()),
            "missing_pct": round(series.isna().mean() * 100, 2),
            "total_count": len(series)
        }
        
        # Sample values (non-null)
        non_null = series.dropna()
        if len(non_null) > 0:
            col_info["sample_values"] = non_null.head(max_samples).tolist()
        else:
            col_info["sample_values"] = []
        
        # Numeric stats
        if pd.api.types.is_numeric_dtype(series):
            col_info["statistics"] = {
                "mean": float(series.mean()) if not series.isna().all() else None,
                "std": float(series.std()) if not series.isna().all() else None,
                "min": float(series.min()) if not series.isna().all() else None,
                "max": float(series.max()) if not series.isna().all() else None,
                "median": float(series.median()) if not series.isna().all() else None
            }
        else:
            col_info["statistics"] = None
        
        # Auto-detect likely role
        col_info["likely_role"] = self._detect_column_role(col, series)
        
        # Detect pattern
        col_info["detected_pattern"] = self._detect_pattern(col, series)
        
        return col_info
    
    def _detect_column_role(self, col_name: str, series: pd.Series) -> str:
        """Detect what role this column likely plays."""
        col_lower = col_name.lower()
        unique_ratio = series.nunique() / len(series) if len(series) > 0 else 0
        
        # Row index
        if col_lower in ['unnamed: 0', 'index', 'row', '#']:
            return "row_index"
        
        # Subject ID
        if any(kw in col_lower for kw in ['id', 'patient', 'subject', 'пац', 'субъект']):
            if 0.5 < unique_ratio <= 1.0:  # High uniqueness
                return "subject_id"
        
        # Group/Treatment
        if any(kw in col_lower for kw in ['group', 'treatment', 'arm', 'группа', 'лечение']):
            if series.nunique() <= 10:  # Low cardinality
                return "grouping_variable"
        
        # Endpoint/Outcome
        if any(kw in col_lower for kw in ['outcome', 'endpoint', 'score', 'исход', 'результат']):
            if pd.api.types.is_numeric_dtype(series):
                return "endpoint"
        
        # Time/Visit column
        if any(kw in col_lower for kw in ['visit', 'time', 'week', 'month', 'визит', 'неделя']):
            if series.nunique() <= 20:
                return "time_variable"
        
        # Covariate
        if pd.api.types.is_numeric_dtype(series):
            if series.nunique() > 10:
                return "numeric_covariate"
        
        # Categorical
        if series.nunique() <= 30:
            return "categorical_variable"
        
        return "unknown"
    
    def _detect_pattern(self, col_name: str, series: pd.Series) -> Optional[str]:
        """Detect naming pattern in column."""
        # Check for timepoint suffix
        timepoint_pattern = re.compile(
            r"(V|T|W|M|В|Т|М|Визит|Visit|Week|Month|Месяц)[\s_]?(\d+)",
            re.IGNORECASE
        )
        if timepoint_pattern.search(col_name):
            return "longitudinal_timepoint"
        
        # Check for Pre/Post
        if re.search(r"(Pre|Post|Baseline|До|После)", col_name, re.IGNORECASE):
            return "pre_post_timepoint"
        
        # Check for ID pattern in values
        if not pd.api.types.is_numeric_dtype(series):
            samples = series.dropna().head(10).astype(str)
            if any(re.match(r'^[A-Z]\d+', s) for s in samples):
                return "id_alphanumeric"
        
        return None
    
    def _detect_families(self, column_names: List[str]) -> List[Dict[str, Any]]:
        """Detect longitudinal families in column names."""
        # Pattern for visit/time numbers
        pattern = re.compile(
            r"^(.+?)[\s_\-]+(V|T|W|M|В|Т|М|Visit|Time|Week|Month|Месяц)[\s_]?(\d+)",
            re.IGNORECASE
        )
        
        # Pattern for Pre/Post
        pattern_prepost = re.compile(
            r"^(.+?)[\s_\-]+(Pre|Post|Baseline|До|После|Исходно)",
            re.IGNORECASE
        )
        
        base_map = {}
        
        for col in column_names:
            # Try visit number pattern
            match = pattern.match(col)
            if match:
                base = match.group(1).strip(" _-")
                timepoint = f"{match.group(2).upper()}{match.group(3)}"
                base_map.setdefault(base, {})[timepoint] = col
                continue
            
            # Try Pre/Post pattern
            match2 = pattern_prepost.match(col)
            if match2:
                base = match2.group(1).strip(" _-")
                timepoint = match2.group(2).capitalize()
                base_map.setdefault(base, {})[timepoint] = col
        
        # Build families (>=2 timepoints)
        families = []
        for base_name, timepoints in base_map.items():
            if len(timepoints) >= 2:
                families.append({
                    "family_name": base_name,
                    "timepoints": list(timepoints.keys()),
                    "n_timepoints": len(timepoints),
                    "columns": timepoints
                })
        
        return families
    
    def _detect_structure(self, metadata: Dict[str, Any]) -> str:
        """Detect overall study structure."""
        has_families = len(metadata.get("detected_families", [])) > 0
        has_subject_id = any(c["likely_role"] == "subject_id" for c in metadata["columns"])
        has_time_var = any(c["likely_role"] == "time_variable" for c in metadata["columns"])
        has_group = any(c["likely_role"] == "grouping_variable" for c in metadata["columns"])
        
        if has_families and has_subject_id:
            return "wide_format_longitudinal"
        elif has_time_var and has_subject_id:
            return "long_format_longitudinal"
        elif has_group and not has_time_var:
            return "cross_sectional_groups"
        else:
            return "unknown_structure"
