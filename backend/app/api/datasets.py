import shutil
import uuid
import os
import pandas as pd
import aiofiles
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List

from app.schemas.dataset import DatasetUpload, DatasetProfile, DatasetReparse, DatasetModification, ColumnInfo
from app.modules.parsers import parse_file, get_dataset_path, get_dataframe
from app.core.pipeline import PipelineManager
from pydantic import BaseModel
import math

router = APIRouter()

WORKSPACE_DIR = "workspace"
DATA_DIR = os.path.join(WORKSPACE_DIR, "datasets")
pipeline = PipelineManager(DATA_DIR)


def generate_profile(df: pd.DataFrame, page: int = 1, limit: int = 100) -> DatasetProfile:
    """
    Generate a DatasetProfile from a pandas DataFrame.
    """
    import numpy as np
    
    def to_python(val):
        """Convert numpy types to Python native types for JSON serialization."""
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, np.ndarray):
            return val.tolist()
        if pd.isna(val):
            return None
        return val
    
    columns = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if "int" in dtype_str or "float" in dtype_str:
            col_type = "numeric"
        elif "datetime" in dtype_str:
            col_type = "datetime"
        elif df[col].dtype == "object" or df[col].dtype.name == "category":
            # Check if it's categorical (low cardinality) or text
            if df[col].nunique() < 20:
                col_type = "categorical"
            else:
                col_type = "text"
        else:
            col_type = "text"
        
        # Get example value and convert to native Python type
        example_val = None
        if not df[col].dropna().empty:
            example_val = to_python(df[col].dropna().iloc[0])
        
        columns.append(ColumnInfo(
            name=str(col),
            type=col_type,
            missing_count=int(df[col].isna().sum()),
            unique_count=int(df[col].nunique()),
            example=example_val
        ))
    
    # Pagination
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / limit))
    start = (page - 1) * limit
    end = start + limit
    
    # Convert head to native Python types for JSON serialization
    head_df = df.iloc[start:end].replace({pd.NA: None, float('nan'): None})
    head = []
    for _, row in head_df.iterrows():
        head.append({k: to_python(v) for k, v in row.items()})
    
    return DatasetProfile(
        row_count=total_rows,
        col_count=len(df.columns),
        columns=columns,
        head=head,
        page=page,
        total_pages=total_pages
    )

@router.get("", response_model=List[dict])
async def list_datasets():
    datasets = []
    if not os.path.exists(DATA_DIR):
        return []
    
    # New Pipeline Structure Logic
    for dataset_id in os.listdir(DATA_DIR):
        ds_dir = os.path.join(DATA_DIR, dataset_id)
        if not os.path.isdir(ds_dir): continue
        
        # Check source metadata first
        meta_path = os.path.join(ds_dir, "source", "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    datasets.append({
                        "id": dataset_id, 
                        "filename": meta.get("original_filename", "unknown"),
                        "created_at": meta.get("ingest_timestamp")
                    })
                continue
            except:
                pass
                
        # Fallback to old flat structure (Migration support)
        files = [f for f in os.listdir(ds_dir) if not f.endswith('.json') and f != "processed.csv" and not os.path.isdir(os.path.join(ds_dir, f))]
        if files:
            datasets.append({"id": dataset_id, "filename": files[0]})
            
    return datasets

@router.post("", response_model=DatasetUpload)
async def upload_dataset(file: UploadFile = File(...)):
    # File size validation (50MB max)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {MAX_FILE_SIZE/1024/1024:.0f}MB, got {file_size/1024/1024:.1f}MB"
        )
    
    dataset_id = str(uuid.uuid4())
    
    try:
        # Stage 0: Ingest (Save Raw)
        content = await file.read()
        raw_path = pipeline.save_source(dataset_id, content, file.filename)
        
        # Stage 1: Parse
        def parse_logic(): return parse_file(raw_path, header_row=0, original_filename=file.filename)
        df, used_header = await run_in_threadpool(parse_logic)
        
        # Stage 2: Create Processed Snapshot
        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header})

        # Stage 3: Smart Scan (One-Pass Optimization)
        # Replaces old 'profiler' + 'scanner' dual pass
        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        
        # Run scan in threadpool to avoid blocking event loop on large files
        scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        
        profile_data = scan_result["profile"]
        scan_report = scan_result["scan_report"]
        
        # Save scan report
        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        with open(report_path, "w") as f:
            json.dump(scan_report, f, indent=2, default=str)
            
    except Exception as e:
        # Cleanup
        shutil.rmtree(os.path.join(DATA_DIR, dataset_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Processing failed: {str(e)}")

    return DatasetUpload(id=dataset_id, filename=file.filename, profile=profile_data)

@router.post("/{dataset_id}/reparse", response_model=DatasetProfile)
def reparse_dataset(dataset_id: str, request: DatasetReparse):
    # Retrieve raw source path
    # With pipeline, raw is always in source/original.raw
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    raw_path = os.path.join(upload_dir, "source", "original.raw")
    
    if not os.path.exists(raw_path): 
        # Fallback for old datasets
        file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
        if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
        raw_path = file_path
        
    try:
        df, used_header = parse_file(raw_path, header_row=request.header_row, sheet_name=request.sheet_name)
        
        # Create new processed snapshot (Overwrite stage 1)
        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header, "sheet": request.sheet_name})
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not reparse file: {str(e)}")
        
    return generate_profile(df)

@router.post("/{dataset_id}/modify", response_model=DatasetProfile)
def modify_dataset(dataset_id: str, modification: DatasetModification):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
        actions = list((modification.actions or []))

        for action in actions:
            if action.type == "drop_col":
                if action.column and action.column in df.columns:
                    df = df.drop(columns=[action.column])
            elif action.type == "rename_col":
                if action.column and action.new_name and action.column in df.columns:
                    if action.new_name in df.columns and action.new_name != action.column:
                        raise ValueError(f"Column already exists: {action.new_name}")
                    df = df.rename(columns={action.column: action.new_name})
            elif action.type == "change_type":
                if action.column and action.new_type and action.column in df.columns:
                    if action.new_type == "numeric":
                        df[action.column] = pd.to_numeric(df[action.column], errors="coerce")
                    elif action.new_type == "datetime":
                        df[action.column] = pd.to_datetime(df[action.column], errors="coerce")
                    elif action.new_type in ("text", "categorical"):
                        df[action.column] = df[action.column].astype(str)
                    else:
                        raise ValueError(f"Unsupported new_type: {action.new_type}")
            elif action.type == "drop_row":
                if action.row_index is not None and isinstance(action.row_index, int):
                    if 0 <= action.row_index < len(df.index):
                        df = df.drop(index=action.row_index)
            elif action.type == "update_cell":
                if action.row_index is None or not isinstance(action.row_index, int):
                    continue
                if not action.column or action.column not in df.columns:
                    continue

                if 0 <= action.row_index < len(df.index):
                    v = action.value
                    if v == "":
                        v = None
                    df.at[action.row_index, action.column] = v
            else:
                raise ValueError(f"Unknown modification type: {action.type}")

        df = df.reset_index(drop=True)

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={"action": "modify", "count": len(actions)}
        )

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        scan_report = scanner.scan_dataset(df)["scan_report"]

        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        with open(report_path, "w") as f:
            json.dump(scan_report, f, indent=2, default=str)

        return generate_profile(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to modify dataset: {str(e)}")

class CleanCommand(BaseModel):
    column: str
    action: str


class MiceImputeCommand(BaseModel):
    columns: List[str]
    max_iter: int = 10
    n_imputations: int = 5
    random_state: int = 42


@router.post("/{dataset_id}/impute_mice")
def impute_mice_api(dataset_id: str, cmd: MiceImputeCommand):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)

        columns = [c for c in (cmd.columns or []) if isinstance(c, str) and c]
        if not columns:
            raise ValueError("columns must not be empty")

        missing_cols = [c for c in columns if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found: {missing_cols}")

        if len(columns) > 50:
            raise ValueError("MICE supports up to 50 columns per run")

        numeric_df = df[columns].apply(pd.to_numeric, errors="coerce")

        has_missing = bool(numeric_df.isna().any().any())
        if not has_missing:
            return generate_profile(df)

        try:
            from sklearn.experimental import enable_iterative_imputer  # noqa: F401
            from sklearn.impute import IterativeImputer
        except Exception as e:
            raise ValueError(f"MICE dependencies not available: {str(e)}")

        max_iter = int(cmd.max_iter)
        n_imputations = int(cmd.n_imputations)
        random_state = int(cmd.random_state)

        if max_iter < 1 or max_iter > 50:
            raise ValueError("max_iter must be between 1 and 50")
        if n_imputations < 1 or n_imputations > 20:
            raise ValueError("n_imputations must be between 1 and 20")

        matrices = []
        for i in range(n_imputations):
            imputer = IterativeImputer(
                max_iter=max_iter,
                random_state=random_state + i,
                sample_posterior=True,
                skip_complete=True
            )
            imputed = imputer.fit_transform(numeric_df)
            matrices.append(imputed)

        imputed_mean = sum(matrices) / float(len(matrices))
        df.loc[:, columns] = imputed_mean

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={
                "action": "mice_imputation",
                "columns": columns,
                "max_iter": max_iter,
                "n_imputations": n_imputations
            }
        )

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        scan_report = scanner.scan_dataset(df)["scan_report"]

        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        with open(report_path, "w") as f:
            json.dump(scan_report, f, indent=2, default=str)

        return generate_profile(df)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"MICE imputation failed: {str(e)}")

@router.post("/{dataset_id}/clean_column")
def clean_column_api(dataset_id: str, cmd: CleanCommand):
    """
    Apply a cleaning action to a column.
    """
    try:
        # 1. Load Data
        df = get_dataframe(dataset_id, DATA_DIR)
        
        # 2. Apply Operation
        if cmd.action == "to_numeric":
            df[cmd.column] = pd.to_numeric(df[cmd.column], errors='coerce')
        elif cmd.action == "fill_mean":
            if pd.api.types.is_numeric_dtype(df[cmd.column]):
                df[cmd.column] = df[cmd.column].fillna(df[cmd.column].mean())
            else:
                raise ValueError("fill_mean is only supported for numeric columns")
        elif cmd.action == "fill_median":
            if pd.api.types.is_numeric_dtype(df[cmd.column]):
                df[cmd.column] = df[cmd.column].fillna(df[cmd.column].median())
            else:
                raise ValueError("fill_median is only supported for numeric columns")
        elif cmd.action == "fill_mode":
            mode_series = df[cmd.column].mode(dropna=True)
            if mode_series.empty:
                raise ValueError("fill_mode requires at least one non-missing value")
            df[cmd.column] = df[cmd.column].fillna(mode_series.iloc[0])
        elif cmd.action == "fill_locf":
            df[cmd.column] = df[cmd.column].ffill()
        elif cmd.action == "fill_nocb":
            df[cmd.column] = df[cmd.column].bfill()
        elif cmd.action == "drop_na":
             df = df.dropna(subset=[cmd.column])
        else:
            raise ValueError(f"Unknown action: {cmd.action}")
             
        # 3. Save New Snapshot
        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": cmd.action, "column": cmd.column})
        
        # 4. Re-Scan (Update Report)
        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        scan_report = scanner.scan_dataset(df)["scan_report"]
        
        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        with open(report_path, "w") as f:
            json.dump(scan_report, f, indent=2, default=str)
            
        return generate_profile(df)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cleaning failed: {str(e)}")

@router.get("/{dataset_id}/scan_report")
def get_scan_report(dataset_id: str):
    try:
        path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        if not os.path.exists(path):
            return {"status": "no_report"}
            
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Report not found")

@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: str, page: int = 1, limit: int = 100):
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    
    # Priority 1: Processed Snapshot
    processed_path = os.path.join(upload_dir, "processed", "data.csv")
    if os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
        df.columns = df.columns.astype(str)
        return generate_profile(df, page=page, limit=limit)
        
    # Priority 2: Old Processed
    old_proc = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(old_proc):
         df = pd.read_csv(old_proc)
         df.columns = df.columns.astype(str)
         return generate_profile(df, page=page, limit=limit)

    # Priority 3: Fallback Source (Old structure)
    file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Assuming old metadata
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f: header_row = json.load(f).get("header_row", 0)
        
    df, _ = parse_file(file_path, header_row=header_row)
    df, _ = parse_file(file_path, header_row=header_row)
    return generate_profile(df, page=page, limit=limit)

@router.get("/{dataset_id}/content")
def get_dataset_content(dataset_id: str, page: int = 1, limit: int = 100, sheet: str = None):
    """
    Returns the dataset content (rows) with pagination.
    Used by the Data View component.
    """
    df = get_dataframe(dataset_id, DATA_DIR)
    
    # Pagination
    start = (page - 1) * limit
    end = start + limit
    
    # Slice
    data_slice = df.iloc[start:end].replace({pd.NA: None, float('nan'): None}).to_dict(orient="records")
    
    return {
        "data": data_slice,
        "total_rows": len(df),
        "page": page,
        "limit": limit,
        "columns": list(df.columns)
    }
