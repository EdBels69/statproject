import shutil
import uuid
import os
import pandas as pd
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List

from app.schemas.dataset import DatasetUpload, DatasetProfile, ColumnInfo, DatasetReparse, DatasetModification
from app.core.config import settings

router = APIRouter()

WORKSPACE_DIR = "workspace"
DATA_DIR = os.path.join(WORKSPACE_DIR, "datasets")

os.makedirs(DATA_DIR, exist_ok=True)

def detect_type(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    # Heuristic for categorical vs text
    if series.nunique() < 20 and series.dtype == "object":
        return "categorical"
    return "text"

def detect_header(file_path: str) -> int:
    """
    Attempts to auto-detect the header row by finding the row with the most valid string columns.
    Checks first 20 rows.
    """
    try:
        # Read first 20 rows without header
        if file_path.endswith('.csv'):
            df_preview = pd.read_csv(file_path, header=None, nrows=20)
        else:
            df_preview = pd.read_excel(file_path, header=None, nrows=20)
            
        best_row = 0
        max_score = -1
        
        for i in range(len(df_preview)):
            row = df_preview.iloc[i]
            # Score: Count of non-null string values that don't look like data (len > 0)
            # Heuristic: Headers are usually all strings and unique
            
            non_nulls = row.dropna()
            if len(non_nulls) < 2: 
                continue # Skip empty-ish rows
                
            # Count strings
            string_count = sum(1 for x in non_nulls if isinstance(x, str))
            
            # Count unique
            unique_count = len(set(non_nulls))
            
            # Score formula: We want many strings, mostly unique
            score = string_count + (unique_count * 0.5)
            
            if score > max_score:
                max_score = score
                best_row = i
                
        return best_row
    except:
        return 0 # Fallback to 0

def parse_file(file_path: str, header_row: int = 0, sheet_name: str = None) -> tuple[pd.DataFrame, int]:
    # If header_row is explicitly -1 (flag for auto-detect), try to find it
    if header_row == -1:
        header_row = detect_header(file_path)

    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, header=header_row)
    elif file_path.endswith((".xls", ".xlsx")):
        # Read specific sheet if provided
        if sheet_name:
             df = pd.read_excel(file_path, header=header_row, sheet_name=sheet_name)
        else:
            # Fallback for now: read first sheet if no sheet specified, OR read all and concatenate
            # User wants to SELECT sheet, so default behavior should be specific.
            # If no sheet provided, we read the FIRST sheet by default now (simplification)
            # or keep logic to read all? 
            # Original logic read all and concatenated. 
            # If we transition to sheet selection, better to default to first sheet if none specified.
            df = pd.read_excel(file_path, header=header_row, sheet_name=0)
            
            # Legacy robust check: if it fails with index 0
    else:
        # Fallback
        df = pd.read_csv(file_path, header=header_row)
        
    return df, header_row
        
    return df, header_row

def generate_profile(df: pd.DataFrame, page: int = 1, limit: int = 50) -> DatasetProfile:
    columns_info = []
    # Convert all columns to string for safe naming
    df.columns = df.columns.astype(str)
    
    for col in df.columns:
        col_type = detect_type(df[col])
        # Safe head value
        first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
        
        columns_info.append(ColumnInfo(
            name=str(col),
            type=col_type,
            missing_count=int(df[col].isna().sum()),
            unique_count=int(df[col].nunique()),
            example=str(first_valid) if first_valid is not None else None
        ))
        
    # Pagination
    total_rows = len(df)
    total_pages = (total_rows + limit - 1) // limit
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    page_df = df.iloc[start_idx:end_idx].where(pd.notnull(df), None)
    
    return DatasetProfile(
        row_count=total_rows,
        col_count=len(df.columns),
        columns=columns_info,
        head=page_df.to_dict(orient="records"),
        page=page,
        total_pages=total_pages
    )

def get_dataset_path(dataset_id: str):
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir):
        return None, None
    
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
    if not files:
        return None, None
        
    return os.path.join(upload_dir, files[0]), upload_dir

@router.post("", response_model=DatasetUpload)
async def upload_dataset(file: UploadFile = File(...)):
    print(f"DEBUG: Starting Async Chunked Upload for {file.filename}")
    
    # 1. Generate ID and paths
    dataset_id = str(uuid.uuid4())
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    print(f"DEBUG: Saving to {file_path}")
    
    # 2. Save file (Async Chunked)
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)
        print("DEBUG: File saved successfully (Async)")
    except Exception as e:
        print(f"DEBUG: Error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
        
    # 3. Parse with Pandas (Run in Threadpool to avoid blocking event loop)
    try:
        print("DEBUG: Parsing file (in threadpool)...")
        # Define wrapper for parsing logic
        def parse_logic():
            # Use explicit header_row=0 for stability and avoid auto-detect hangs
            d, h = parse_file(file_path, header_row=0)
            return d, h

        df, used_header = await run_in_threadpool(parse_logic)
        print(f"DEBUG: Parsed dataframe shape: {df.shape}")
        
        # Save metadata
        import json
        with open(os.path.join(upload_dir, "metadata.json"), "w") as f:
            json.dump({"header_row": used_header}, f)
            
    except Exception as e:
        print(f"DEBUG: Error parsing file: {e}")
        # Cleanup
        shutil.rmtree(upload_dir)
        raise HTTPException(status_code=400, detail=f"Could not parse file. Ensure it is a valid CSV or Excel file. Error: {str(e)}")

    # 4. Generate Profile (Also cpu-bound, run in threadpool)
    print("DEBUG: Generating profile (in threadpool)...")
    profile = await run_in_threadpool(generate_profile, df)
    print("DEBUG: Profile generated")

    return DatasetUpload(
        id=dataset_id,
        filename=file.filename,
        profile=profile
    )

@router.post("/{dataset_id}/reparse", response_model=DatasetProfile)
def reparse_dataset(dataset_id: str, request: DatasetReparse):
    # 1. Find dataset directory
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # 2. Find file (assuming only one file per dataset for MVP)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json')]
    if not files:
        raise HTTPException(status_code=404, detail="File lost")
    
    file_path = os.path.join(upload_dir, files[0])
    
    # 3. Reparse
    try:
        sheet_name = request.sheet_name if hasattr(request, 'sheet_name') else None
        df, used_header = parse_file(file_path, header_row=request.header_row, sheet_name=sheet_name)
        
        # Save metadata
        import json
        with open(os.path.join(upload_dir, "metadata.json"), "w") as f:
            meta = {"header_row": used_header}
            if sheet_name:
                meta["sheet_name"] = sheet_name
            json.dump(meta, f)
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not reparse file: {str(e)}")
        
    # 4. Generate new profile
    profile = generate_profile(df)
    
    return profile

@router.post("/{dataset_id}/modify", response_model=DatasetProfile)
def modify_dataset(dataset_id: str, modification: DatasetModification):
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Check for existing processed file, else load original
    processed_path = os.path.join(upload_dir, "processed.csv")
    
    # Finds original file
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
    if not files:
        raise HTTPException(status_code=404, detail="Original file lost")
    original_path = os.path.join(upload_dir, files[0])
    
    # Load Metadata
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
            header_row = meta.get("header_row", 0)

    # Load DF
    try:
        if os.path.exists(processed_path):
            df = pd.read_csv(processed_path)
            # Ensure columns are strings
            df.columns = df.columns.astype(str)
        else:
            df, _ = parse_file(original_path, header_row=header_row)
            df.columns = df.columns.astype(str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load data: {e}")
        
    # Apply Actions
    try:
        for action in modification.actions:
            if action.type == "drop_col":
                if action.column in df.columns:
                    df = df.drop(columns=[action.column])
            
            elif action.type == "rename_col":
                if action.column in df.columns and action.new_name:
                    df = df.rename(columns={action.column: action.new_name})
                    
            elif action.type == "change_type":
                if action.column in df.columns and action.new_type:
                    # Best effort conversion
                    if action.new_type == "numeric":
                        df[action.column] = pd.to_numeric(df[action.column], errors='coerce')
                    elif action.new_type == "datetime":
                        df[action.column] = pd.to_datetime(df[action.column], errors='coerce')
                    elif action.new_type == "text":
                        df[action.column] = df[action.column].astype(str)
                    # categorical is just object/category, usually handled by analysis engine, 
                    # but we can cast to string to be safe or category dtype
                    elif action.new_type == "categorical":
                         df[action.column] = df[action.column].astype(str)

            elif action.type == "drop_row":
                if action.row_index is not None and action.row_index in df.index:
                     df = df.drop(index=action.row_index)
            
            elif action.type == "update_cell":
                if (action.row_index is not None and 
                    action.column in df.columns and 
                    action.row_index in df.index):
                        # Attempt to set value, respecting type logic if needed, 
                        # but pandas generally handles mixed types in object columns
                        df.at[action.row_index, action.column] = action.value

        # Reset index if rows were dropped so that 0..N matches for UI
        df = df.reset_index(drop=True)

        # Save processed
        df.to_csv(processed_path, index=False)
        
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Failed to modify dataset: {str(e)}")

    return generate_profile(df)


@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: str, page: int = 1, limit: int = 100):
    print(f"DEBUG: get_dataset called with page={page}, limit={limit}")
    # 1. Find dataset directory
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # 2. Prefer processed file
    processed_path = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(processed_path):
        try:
            df = pd.read_csv(processed_path)
            # Ensure columns are strings
            df.columns = df.columns.astype(str)
            return generate_profile(df, page=page, limit=limit)
        except Exception as e:
            # Fallback or error? Let's error since state is corrupted
            raise HTTPException(status_code=500, detail=f"Corrupt processed data: {e}")

    # 3. Fallback to original
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
    if not files:
        raise HTTPException(status_code=404, detail="File lost")
    file_path = os.path.join(upload_dir, files[0])
    
    # 4. Load Metadata
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
            header_row = meta.get("header_row", 0)
    
    # 5. Parse & Profile
    try:
        df, _ = parse_file(file_path, header_row=header_row)
        return generate_profile(df, page=page, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
