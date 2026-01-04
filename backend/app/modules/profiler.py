import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List

def detect_type(series: pd.Series) -> str:
    """
    Detects the logical data type of a pandas Series.
    Returns: 'numeric', 'categorical', 'datetime', 'text'
    """
    if series.empty or series.isnull().all():
        return "text"
    
    dtype = series.dtype
    
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    elif pd.api.types.is_bool_dtype(dtype):
        return "categorical"
    
    # Try parsing string to datetime
    if pd.api.types.is_object_dtype(dtype):
        # Sampling for performance
        sample = series.dropna().head(100)
        try:
            pd.to_datetime(sample, errors='raise')
            return "datetime"
        except:
            pass
            
    return "text"

def clean_for_json(obj: Any) -> Any:
    """
    Recursively replaces NaN/Infinity/NaT with None for JSON compatibility.
    """
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    elif isinstance(obj, pd.Timestamp) or (hasattr(obj, 'to_pydatetime') and pd.isna(obj)):
        return None
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(x) for x in obj]
    return obj

def generate_profile(df: pd.DataFrame, page: int = 1, limit: int = 100) -> Dict[str, Any]:
    """
    Generates a data profile summary including row counts, column types, and basic statistics.
    Alinged with app.schemas.dataset.DatasetProfile
    """
    column_infos = []
    
    for col_name in df.columns:
        series = df[col_name]
        col_type = detect_type(series)
        
        # Example value (non-null)
        example = None
        non_null = series.dropna()
        if not non_null.empty:
            example = non_null.iloc[0]
            if isinstance(example, (pd.Timestamp, np.datetime64)):
                example = example.isoformat()
            elif isinstance(example, (np.integer, np.floating)):
                example = example.item()
        
        info = {
            "name": str(col_name),
            "type": col_type,
            "missing_count": int(series.isnull().sum()),
            "unique_count": int(series.nunique()),
            "example": clean_for_json(example)
        }
        column_infos.append(info)
    
    # Pagination
    total_rows = len(df)
    total_pages = (total_rows + limit - 1) // limit if total_rows > 0 else 1
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    # Clean rows for JSON
    head_rows = df.iloc[start_idx:end_idx].replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient="records")
    # Also handle NaT in head_rows
    for row in head_rows:
        for k, v in row.items():
            if isinstance(v, (pd.Timestamp, np.datetime64)):
                if pd.isna(v): row[k] = None
                else: row[k] = v.isoformat()

    profile = {
        "row_count": total_rows,
        "col_count": len(df.columns),
        "columns": column_infos,
        "head": head_rows,
        "page": page,
        "total_pages": total_pages
    }
    
    return profile