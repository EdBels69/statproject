import os
import pandas as pd
from typing import Tuple, Optional

def get_dataset_path(dataset_id: str, data_dir: str) -> Tuple[Optional[str], str]:
    """
    Resolves the absolute path to the raw dataset file.
    Supports new Pipeline Structure (source/) and legacy Flat Structure.
    """
    upload_dir = os.path.join(data_dir, dataset_id)
    if not os.path.exists(upload_dir):
        return None, None
        
    # 1. New Pipeline Structure
    raw_path_new = os.path.join(upload_dir, "source", "original.raw")
    if os.path.exists(raw_path_new):
        return raw_path_new, upload_dir
        
    # 2. Legacy Flat Structure
    # Exclude metadata, processed, and dirs
    files = [f for f in os.listdir(upload_dir) 
             if not f.endswith('.json') 
             and f != "processed.csv"
             and not os.path.isdir(os.path.join(upload_dir, f))]
             
    if files:
        return os.path.join(upload_dir, files[0]), upload_dir
        
    return None, upload_dir

def parse_file(file_path: str, header_row: int = 0, sheet_name: str = None, original_filename: str = None) -> Tuple[pd.DataFrame, int]:
    """
    Parses various file types into a DataFrame.
    """
    # Use original filename for extension if provided, else file path
    path_for_ext = original_filename if original_filename else file_path
    ext = os.path.splitext(path_for_ext)[1].lower()
    
    if ext == '.csv':
        df = pd.read_csv(file_path, header=header_row)
    elif ext == '.xlsx':
        df = pd.read_excel(file_path, header=header_row, sheet_name=sheet_name or 0, engine='openpyxl')
    elif ext == '.xls':
        # Fallback for old Excel
        df = pd.read_excel(file_path, header=header_row, sheet_name=sheet_name or 0)
    elif ext == '.json':
        df = pd.read_json(file_path)
    elif ext == '.parquet':
        df = pd.read_parquet(file_path)
    # Allow .raw if original filename was passed and had valid ext, OR just try basic CSV for raw as fallback?
    # No, better to be strict on original_filename if provided.
    else:
        # If .raw and no original_filename, we can try to guess or fail.
        # But for now, system should always pass original_filename.
        raise ValueError(f"Unsupported file format: {ext}")
        
    return df, header_row

def get_dataframe(dataset_id: str, data_dir: str) -> pd.DataFrame:
    """
    Centralized function to load DataFrame for any dataset.
    Checks for processed Parquet first (faster), falls back to original file.
    """
    import json
    
    upload_dir = os.path.join(data_dir, dataset_id)
    
    # Try processed files (Parquet/CSV)
    # Check for processed/{id}.parquet (Pipeline Standard)
    parquet_path = os.path.join(upload_dir, "processed", f"{dataset_id}.parquet")
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)

    pipeline_csv_path = os.path.join(upload_dir, "processed", "data.csv")
    if os.path.exists(pipeline_csv_path):
        return pd.read_csv(pipeline_csv_path)
        
    processed_path = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(processed_path):
        return pd.read_csv(processed_path)
    
    # Load original file
    file_path, _ = get_dataset_path(dataset_id, data_dir)
    if not file_path:
        raise FileNotFoundError(f"Dataset {dataset_id} not found")
    
    # Load metadata for header_row
    # Load metadata for header_row and original_filename
    meta_path = os.path.join(upload_dir, "source", "meta.json")
    if not os.path.exists(meta_path):
         meta_path = os.path.join(upload_dir, "metadata.json") # Fallback
         
    header_row = 0
    sheet_name = None
    original_filename = None
     
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
            header_row = metadata.get("header_row", 0)
            sheet_name = metadata.get("sheet_name")
            original_filename = metadata.get("original_filename")
    
    df, _ = parse_file(file_path, header_row=header_row, sheet_name=sheet_name, original_filename=original_filename)
    try:
        from app.modules.smart_scanner import SmartScanner

        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)
    except Exception:
        pass
    return df
