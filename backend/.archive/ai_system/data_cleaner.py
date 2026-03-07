import pandas as pd
import numpy as np
import re
from typing import List, Dict, Any

class DataCleaner:
    """
    Deterministically cleans and normalizes a pandas DataFrame.
    """

    def clean_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main entry point for cleaning.
        """
        df = df.copy()
        df = self.clean_column_names(df)
        df = self.normalize_categories(df)
        return df

    def clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardizes column names: strips whitespace, replaces non-breaking spaces.
        """
        new_cols = []
        for col in df.columns:
            s = str(col).strip()
            s = s.replace("\xa0", " ") # Non-breaking space
            s = re.sub(r'\s+', ' ', s) # Multiple spaces to one
            new_cols.append(s)
        df.columns = new_cols
        return df

    def normalize_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Unifies case variations in categorical columns (e.g., "Yes", "yes", "YES" -> "Yes").
        """
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                # Skip IDs or columns with too many unique values
                if df[col].nunique() > 50:
                    continue
                
                # normalize
                df[col] = self._unify_column_case(df[col])
        return df

    def _unify_column_case(self, series: pd.Series) -> pd.Series:
        """
        Helper: finds the most frequent casing for each underlying lower-case word and maps it.
        """
        # 1. Lowercase mapping
        # map lower_val -> list of original_vals
        val_map: Dict[str, List[str]] = {}
        original_values = series.dropna().unique()
        
        for v in original_values:
            v_str = str(v)
            lower = v_str.lower().strip()
            if lower not in val_map:
                val_map[lower] = []
            val_map[lower].append(v_str)

        # 2. Decide replacement
        # If multiple variants exist for the same lower-case (e.g. "Yes", "yes"), pick the most frequent
        replace_map = {}
        for lower_key, variants in val_map.items():
            if len(variants) > 1:
                # Find most frequent
                counts = series.value_counts()
                best_variant = max(variants, key=lambda x: counts.get(x, 0))
                for v in variants:
                    if v != best_variant:
                        replace_map[v] = best_variant
        
        if replace_map:
            return series.replace(replace_map)
        return series
