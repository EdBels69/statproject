import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any, Tuple

class DataPrepEngine:
    """
    Handles 'Smart Import': PII Sanitization, Structure Detection, and Cleaning.
    """

    def __init__(self):
        # Common Russian PII patterns
        self.pii_headers = [
            r'фио', r'fio', r'user', r'name', r'имя', r'фамилия', 
            r'телефон', r'phone', r'email', r'mail',
            r'дата.*рожд', r'birth', r'dob', r'д\.р\.', 
            r'data.*rozhd', r'date.*birth'
        ]
        self.date_pattern = r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}'
        # Simple names heuristic? Maybe too aggressive. We'll stick to headers for now + date values.

    def sanitize_dataset(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Masks columns suspected of containing PII.
        Returns cleaned dataframe and list of sanitized columns.
        """
        clean_df = df.copy()
        sanitized_cols = []
        
        # 1. Header-based detection
        for col in clean_df.columns:
            col_str = str(col).lower()
            if any(re.search(p, col_str) for p in self.pii_headers):
                clean_df[col] = "********"
                sanitized_cols.append(col)
                continue
                
        # 2. Value-based detection (Dates of Birth acting as IDs)
        # We generally want to analyze dates (Time), but not Birth Dates (PII).
        # We rely on header context usually. If ambiguous, we keep it but warn?
        # User requested aggressive protection for "Data Rozhdeniya".
        
        return clean_df, sanitized_cols

    def detect_header(self, df_raw: pd.DataFrame, max_scan_rows: int = 20) -> int:
        """
        Heuristic to find the 'real' header row in a messy Excel file.
        Messy files often have titles/metadata in the first few rows.
        Strategies:
        1. Find row with max non-null values.
        2. Find row with mostly strings (headers).
        """
        # Scan first N rows
        candidates = []
        
        for i in range(min(len(df_raw), max_scan_rows)):
            row = df_raw.iloc[i]
            # Score: +1 for non-null, +1 for unique string
            non_null = row.count()
            unique_str = 0
            for val in row:
                if isinstance(val, str) and len(val) > 0:
                    unique_str += 1
            
            candidates.append({
                "idx": i,
                "score": non_null * 1.5 + unique_str
            })
            
        # Best candidate
        best = max(candidates, key=lambda x: x["score"])
        return best["idx"]

    def analyze_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes the dataframe to suggest a transformation schema.
        Detects 'Wide' format (Timepoints as columns).
        """
        suggestion = {
            "type": "clean", # clean, wide, messy
            "melt_candidates": [],
            "id_vars": []
        }
        
        cols = df.columns.tolist()
        
        # 1. Detect Sequence Columns (e.g., T0, T1, T2 or Hb_1, Hb_2)
        # Pattern: prefix + number/date
        sequences = {}
        
        for col in cols:
            # Match "Name_1", "Name 1", "T1"
            # Anchor to start, allow underscores in name, end with digits
            match = re.search(r'^([a-zA-Zа-яА-Я_]+?)[_.\s]*(\d+)$', str(col))
            if match:
                prefix = match.group(1)
                # Cleanup trailing underscore from prefix if captured
                if prefix.endswith("_"):
                    prefix = prefix[:-1]
                    
                if prefix not in sequences:
                    sequences[prefix] = []
                sequences[prefix].append(col)
                
        # If we found sequences with > 2 items, suggest Melting
        melt_groups = []
        for prefix, col_list in sequences.items():
            if len(col_list) > 1:
                melt_groups.append({"prefix": prefix, "cols": col_list})
                
        if melt_groups:
            suggestion["type"] = "wide"
            suggestion["melt_candidates"] = melt_groups
            # Guess ID vars (everything else)
            all_melt_cols = [c for g in melt_groups for c in g["cols"]]
            suggestion["id_vars"] = [c for c in cols if c not in all_melt_cols]
            
        return suggestion
    
    def apply_melt(self, df: pd.DataFrame, id_vars: List[str], value_vars: List[str], 
                   var_name: str = "Timepoint", value_name: str = "Value") -> pd.DataFrame:
        """
        Transforms Wide -> Long.
        """
        return df.melt(id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name=value_name)

