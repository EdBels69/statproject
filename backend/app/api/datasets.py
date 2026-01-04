import shutil
import uuid
import os
import pandas as pd
import aiofiles
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List

from app.schemas.dataset import DatasetUpload, DatasetProfile, DatasetReparse, DatasetModification
from app.modules.parsers import parse_file, get_dataset_path
from app.modules.profiler import generate_profile

router = APIRouter()

WORKSPACE_DIR = "workspace"
DATA_DIR = os.path.join(WORKSPACE_DIR, "datasets")
os.makedirs(DATA_DIR, exist_ok=True)

@router.get("", response_model=List[dict])
async def list_datasets():
    datasets = []
    if not os.path.exists(DATA_DIR):
        return []
    for dataset_id in os.listdir(DATA_DIR):
        upload_dir = os.path.join(DATA_DIR, dataset_id)
        if not os.path.isdir(upload_dir): continue
        files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
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
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
    try:
        def parse_logic(): return parse_file(file_path, header_row=0)
        df, used_header = await run_in_threadpool(parse_logic)
        with open(os.path.join(upload_dir, "metadata.json"), "w") as f:
            json.dump({"header_row": used_header}, f)
    except Exception as e:
        shutil.rmtree(upload_dir)
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(e)}")
    profile = await run_in_threadpool(generate_profile, df, page=1, limit=100)
    return DatasetUpload(id=dataset_id, filename=file.filename, profile=profile)

@router.post("/{dataset_id}/reparse", response_model=DatasetProfile)
def reparse_dataset(dataset_id: str, request: DatasetReparse):
    file_path, upload_dir = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        df, used_header = parse_file(file_path, header_row=request.header_row, sheet_name=request.sheet_name)
        with open(os.path.join(upload_dir, "metadata.json"), "w") as f:
            meta = {"header_row": used_header}
            if request.sheet_name: meta["sheet_name"] = request.sheet_name
            json.dump(meta, f)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not reparse file: {str(e)}")
    return generate_profile(df)

@router.post("/{dataset_id}/modify", response_model=DatasetProfile)
def modify_dataset(dataset_id: str, modification: DatasetModification):
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir): raise HTTPException(status_code=404, detail="Dataset not found")
    processed_path = os.path.join(upload_dir, "processed.csv")
    file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f: header_row = json.load(f).get("header_row", 0)
    try:
        df = pd.read_csv(processed_path) if os.path.exists(processed_path) else parse_file(file_path, header_row=header_row)[0]
        df.columns = df.columns.astype(str)
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to load data: {e}")
    try:
        for action in modification.actions:
            if action.type == "drop_col":
                if action.column in df.columns: df = df.drop(columns=[action.column])
            elif action.type == "rename_col":
                if action.column in df.columns and action.new_name:
                    df = df.rename(columns={action.column: action.new_name})
            elif action.type == "change_type":
                if action.column in df.columns and action.new_type:
                    if action.new_type == "numeric": df[action.column] = pd.to_numeric(df[action.column], errors='coerce')
                    elif action.new_type == "datetime": df[action.column] = pd.to_datetime(df[action.column], errors='coerce')
                    elif action.new_type == "text" or action.new_type == "categorical": df[action.column] = df[action.column].astype(str)
            elif action.type == "drop_row":
                if action.row_index is not None and action.row_index in df.index: df = df.drop(index=action.row_index)
            elif action.type == "update_cell":
                if (action.row_index is not None and action.column in df.columns and action.row_index in df.index):
                    df.at[action.row_index, action.column] = action.value
        df = df.reset_index(drop=True)
        df.to_csv(processed_path, index=False)
    except Exception as e: raise HTTPException(status_code=400, detail=f"Failed to modify dataset: {str(e)}")
    return generate_profile(df)

@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: str, page: int = 1, limit: int = 100):
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.exists(upload_dir): raise HTTPException(status_code=404, detail="Dataset not found")
    processed_path = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
        df.columns = df.columns.astype(str)
        return generate_profile(df, page=page, limit=limit)
    file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f: header_row = json.load(f).get("header_row", 0)
    df, _ = parse_file(file_path, header_row=header_row)
    return generate_profile(df, page=page, limit=limit)