"""
Memory-Efficient Data Scanner for Large Datasets
Optimized for MacBook M1 8GB constraints with intelligent sampling and streaming.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import os
import gc
from pathlib import Path
from app.stats.engine import check_normality


class MemoryEfficientScanner:
    """
    Advanced scanner that uses intelligent sampling, chunking, and memory monitoring
    to handle large datasets on memory-constrained systems.
    """
    
    def __init__(self, max_memory_mb: int = 800, sample_size: int = 10000):
        """
        Initialize with memory constraints.
        
        Args:
            max_memory_mb: Maximum memory allowed for processing (in MB)
            sample_size: Sample size for large datasets analysis
        """
        self.max_memory = max_memory_mb * 1024 * 1024  # bytes
        self.sample_size = sample_size
    
    def scan_dataset(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """
        Scan dataset with memory-efficient strategies.
        
        For files > 50MB: Use sampling
        For files <= 50MB: Full analysis with memory monitoring
        """
        file_size = self._get_file_size(file_path)
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            return self._scan_large_dataset(file_path, original_filename)
        else:
            return self._scan_small_dataset(file_path, original_filename)
    
    def _scan_large_dataset(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Scan large datasets using intelligent sampling."""
        # Estimate total rows for sampling strategy
        total_rows = self._estimate_row_count(file_path)
        
        # Use smaller sample for very large datasets
        effective_sample_size = min(self.sample_size, total_rows)
        
        # Read sample with optimized memory usage
        df_sample = pd.read_csv(
            file_path,
            nrows=effective_sample_size,
            low_memory=False,
            memory_map=True
        )
        
        # Perform analysis on sample
        profile = self._get_basic_profile(df_sample, total_rows)
        report = self._analyze_sample(df_sample, total_rows)
        
        # Clean up memory
        del df_sample
        gc.collect()
        
        return {
            "profile": profile,
            "scan_report": report,
            "sampling_info": {
                "sampled": True,
                "sample_size": effective_sample_size,
                "total_rows": total_rows,
                "sampling_percentage": round((effective_sample_size / total_rows) * 100, 2)
            }
        }
    
    def _scan_small_dataset(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Full analysis for small datasets with memory monitoring."""
        # Read with memory optimization
        df = pd.read_csv(file_path, low_memory=False, memory_map=True)
        
        # Check memory usage
        memory_usage = df.memory_usage(deep=True).sum()
        if memory_usage > self.max_memory:
            # Fallback to sampling if memory exceeds limit
            return self._scan_large_dataset(file_path, original_filename)
        
        # Perform full analysis
        profile = self._get_basic_profile(df, len(df))
        report = self._analyze_full_dataset(df)
        
        # Clean up
        del df
        gc.collect()
        
        return {
            "profile": profile,
            "scan_report": report,
            "sampling_info": {
                "sampled": False,
                "sample_size": len(df),
                "total_rows": len(df),
                "sampling_percentage": 100.0
            }
        }
    
    def _get_basic_profile(self, df: pd.DataFrame, total_rows: int) -> Dict[str, Any]:
        """Get basic dataset profile information."""
        return {
            "row_count": total_rows,
            "col_count": len(df.columns),
            "head": df.head(10).replace({np.nan: None}).to_dict(orient="records")
        }
    
    def _analyze_sample(self, df_sample: pd.DataFrame, total_rows: int) -> Dict[str, Any]:
        """Analyze sampled data with adjustments for sampling."""
        report = {
            "columns": {},
            "issues": [],
            "reorder_suggestion": [],
            "sampling_adjustments": {}
        }
        
        for col in df_sample.columns:
            col_report = self._analyze_column(df_sample[col], str(col))
            
            # Adjust for sampling
            if "unique_count" in col_report:
                col_report["unique_count_estimated"] = self._estimate_unique_count(
                    col_report["unique_count"], 
                    len(df_sample), 
                    total_rows
                )
            
            report["columns"][str(col)] = col_report
        
        report["reorder_suggestion"] = self._suggest_order(df_sample, report["columns"])
        
        return report
    
    def _analyze_full_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Full dataset analysis (similar to original SmartScanner)."""
        report = {
            "columns": {},
            "issues": [],
            "reorder_suggestion": []
        }
        
        for col in df.columns:
            col_report = self._analyze_column(df[col], str(col))
            report["columns"][str(col)] = col_report
        
        report["reorder_suggestion"] = self._suggest_order(df, report["columns"])
        
        return report
    
    def _analyze_column(self, series: pd.Series, name: str) -> Dict[str, Any]:
        """Optimized column analysis with memory awareness."""
        unique_c = series.nunique()
        
        stats = {
            "name": name,
            "type": str(series.dtype),
            "missing_count": int(series.isnull().sum()),
            "unique_count": unique_c,
            "total": len(series)
        }
        
        # Mixed type detection (optimized)
        if pd.api.types.is_object_dtype(series.dtype):
            # Sample for large series to avoid memory issues
            if len(series) > 10000:
                sample_series = series.sample(n=10000, random_state=42)
                numeric_converted = pd.to_numeric(sample_series, errors='coerce')
                num_count = numeric_converted.notna().sum()
                stats["numeric_convertible_percent"] = round((num_count / 10000) * 100, 1)
            else:
                numeric_converted = pd.to_numeric(series, errors='coerce')
                num_count = numeric_converted.notna().sum()
                stats["numeric_convertible_percent"] = round((num_count / len(series)) * 100, 1)
            
            if stats["numeric_convertible_percent"] > 50:
                stats["mixed_type_suspected"] = True
        
        # Normality check (only for reasonable sample sizes)
        if pd.api.types.is_numeric_dtype(series.dtype) and len(series) <= 5000:
            is_normal, p_val, _ = check_normality(series)
            stats["normality"] = {
                "is_normal": is_normal,
                "p_value": float(p_val)
            }
        
        # Basic stats
        if pd.api.types.is_numeric_dtype(series.dtype):
            stats["mean"] = float(series.mean())
            stats["min"] = float(series.min())
            stats["max"] = float(series.max())
        
        return stats
    
    def _estimate_row_count(self, file_path: str) -> int:
        """Estimate total rows without loading entire file."""
        try:
            # Use wc command for efficiency
            result = os.popen(f'wc -l "{file_path}"').read().split()
            if result:
                return int(result[0]) - 1  # Subtract header
        except:
            pass
        
        # Fallback: count lines in Python
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f) - 1
    
    def _estimate_unique_count(self, sample_unique: int, sample_size: int, total_rows: int) -> int:
        """Estimate unique values in full dataset based on sample."""
        if sample_size >= total_rows:
            return sample_unique
        
        # Simple extrapolation (can be improved with statistical estimation)
        estimated = int(sample_unique * (total_rows / sample_size))
        return min(estimated, total_rows)
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(file_path)
    
    def _suggest_order(self, df: pd.DataFrame, col_reports: Dict) -> List[str]:
        """Suggest logical column order."""
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
                
            dtype = report.get("type", "")
            if "int" in dtype or "float" in dtype:
                nums.append(c)
            elif "object" in dtype:
                if report.get("unique_count", 999) < 20:
                    cats.append(c)
                else:
                    others.append(c)
            else:
                others.append(c)
                
        return ids + cats + nums + others


def get_memory_usage() -> Dict[str, Any]:
    """Get current memory usage statistics."""
    import psutil
    
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
        "percent": process.memory_percent(),
        "available_mb": psutil.virtual_memory().available / 1024 / 1024
    }