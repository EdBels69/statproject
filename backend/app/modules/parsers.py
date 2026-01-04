import os
import pandas as pd
from typing import Tuple, Optional

def get_dataset_path(dataset_id: str, base_dir: str) -> Tuple[Optional[str], str]:
    """
    Returns (path_to_file, upload_directory)
    """
    upload_dir = os.path.join(base_dir, dataset_id)
    if not os.path.exists(upload_dir):
        return None, upload_dir
    
    # Prioritize original uploaded file (not metadata, not processed)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
    if not files:
        return None, upload_dir
        
    return os.path.join(upload_dir, files[0]), upload_dir

def parse_file(file_path: str, header_row: int = 0, sheet_name: str = None) -> Tuple[pd.DataFrame, int]:
    """
    Parses various file types into a DataFrame.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
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
    else:
        raise ValueError(f"Unsupported file format: {ext}")
        
    return df, header_row

def get_dataframe(dataset_id: str, data_dir: str) -> pd.DataFrame:
    """
    Centralized function to load DataFrame for any dataset.
    Checks for processed.csv first (faster), falls back to original file.
    """
    import json
    
    upload_dir = os.path.join(data_dir, dataset_id)
    
    # Try processed.csv first (faster)
    processed_path = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(processed_path):
        return pd.read_csv(processed_path)
    
    # Load original file
    file_path, _ = get_dataset_path(dataset_id, data_dir)
    if not file_path:
        raise FileNotFoundError(f"Dataset {dataset_id} not found")
    
    # Load metadata for header_row
    meta_path = os.path.join(upload_dir, "metadata.json")
    header_row = 0
    sheet_name = None
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
            header_row = metadata.get("header_row", 0)
            sheet_name = metadata.get("sheet_name")
    
    df, _ = parse_file(file_path, header_row=header_row, sheet_name=sheet_name)
    return df