import os
import shutil
import uuid
import json
import math
import pandas as pd
import numpy as np
import aiofiles
from fastapi import UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List, Dict, Optional, Any

from app.schemas.dataset import (
    DatasetProfile, ColumnInfo, DatasetUpload, DatasetListItem, 
    DatasetReparse, CleanCommand, PrepApplyRequest, DatasetModification
)
from app.core.pipeline import PipelineManager
from app.modules.parsers import parse_file, get_dataset_path, get_dataframe
from app.modules.data_prep import DataPrepEngine
from app.modules.smart_scanner import SmartScanner

class DatasetService:
    def __init__(self):
        self.workspace_dir = "workspace"
        self.data_dir = os.path.join(self.workspace_dir, "datasets")
        self.pipeline = PipelineManager(self.data_dir)
        self.prep_engine = DataPrepEngine()
        self.scanner = SmartScanner()
        
    def _to_python(self, val):
        if isinstance(val, (np.integer,)): return int(val)
        if isinstance(val, (np.floating,)): return float(val)
        if isinstance(val, np.ndarray): return val.tolist()
        if pd.isna(val): return None
        return val

    def generate_profile(self, df: pd.DataFrame, page: int = 1, limit: int = 100) -> DatasetProfile:
        columns = []
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            if "int" in dtype_str or "float" in dtype_str: col_type = "numeric"
            elif "datetime" in dtype_str: col_type = "datetime"
            elif df[col].dtype == "object" or df[col].dtype.name == "category":
                col_type = "categorical" if df[col].nunique() < 20 else "text"
            else: col_type = "text"
            
            example_val = None
            if not df[col].dropna().empty:
                example_val = self._to_python(df[col].dropna().iloc[0])
            
            columns.append(ColumnInfo(
                name=str(col),
                type=col_type,
                missing_count=int(df[col].isna().sum()),
                unique_count=int(df[col].nunique()),
                example=example_val
            ))
        
        total_rows = len(df)
        total_pages = max(1, math.ceil(total_rows / limit))
        start = (page - 1) * limit
        end = start + limit
        
        head_df = df.iloc[start:end].replace({pd.NA: None, float('nan'): None})
        head = []
        for _, row in head_df.iterrows():
            head.append({k: self._to_python(v) for k, v in row.items()})
        
        return DatasetProfile(
            row_count=total_rows,
            col_count=len(df.columns),
            columns=columns,
            head=head,
            page=page,
            total_pages=total_pages
        )

    async def list_datasets(self) -> List[DatasetListItem]:
        datasets = []
        if not os.path.exists(self.data_dir): return []
        
        for dataset_id in os.listdir(self.data_dir):
            ds_dir = os.path.join(self.data_dir, dataset_id)
            if not os.path.isdir(ds_dir): continue
            
            meta_path = os.path.join(ds_dir, "source", "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        datasets.append(DatasetListItem(
                            id=dataset_id, 
                            filename=meta.get("original_filename", "unknown"),
                            created_at=meta.get("ingest_timestamp")
                        ))
                    continue
                except: pass
            
            # Fallback
            files = [f for f in os.listdir(ds_dir) if not f.endswith('.json') and f != "processed.csv" and not os.path.isdir(os.path.join(ds_dir, f))]
            if files:
                datasets.append(DatasetListItem(id=dataset_id, filename=files[0]))
                
        returndatasets = sorted(datasets, key=lambda x: x.created_at or "", reverse=True)
        return datasets

    async def upload_dataset(self, file: UploadFile) -> DatasetUpload:
        MAX_FILE_SIZE = 50 * 1024 * 1024
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
            
        dataset_id = str(uuid.uuid4())
        try:
            content = await file.read()
            raw_path = self.pipeline.save_source(dataset_id, content, file.filename)
            
            def parse_logic(): return parse_file(raw_path, header_row=0, original_filename=file.filename)
            df, used_header = await run_in_threadpool(parse_logic)
            
            self.pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header})
            
            scan_result = await run_in_threadpool(self.scanner.scan_dataset, df)
            profile_data = scan_result["profile"]
            
            self._save_scan_report(dataset_id, scan_result["scan_report"])
            
        except Exception as e:
            shutil.rmtree(os.path.join(self.data_dir, dataset_id), ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e))
            
        return DatasetUpload(id=dataset_id, filename=file.filename, profile=profile_data)

    def _save_scan_report(self, dataset_id: str, report: dict):
        report_path = os.path.join(self.pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

    def get_dataset(self, dataset_id: str, page: int = 1, limit: int = 100) -> DatasetProfile:
        df = get_dataframe(dataset_id, self.data_dir) # Handles processed vs raw logic internally if robust
        # But get_dataframe in modules/parsers might be simple. 
        # Re-implementing robustness here:
        
        upload_dir = os.path.join(self.data_dir, dataset_id)
        processed_path = os.path.join(upload_dir, "processed", "data.csv")
        
        if os.path.exists(processed_path):
            df = pd.read_csv(processed_path)
            df.columns = df.columns.astype(str)
        else:
            # Fallbacks
            old_proc = os.path.join(upload_dir, "processed.csv")
            if os.path.exists(old_proc):
                df = pd.read_csv(old_proc)
                df.columns = df.columns.astype(str)
            else:
                file_path, _ = get_dataset_path(dataset_id, self.data_dir)
                if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
                df, _ = parse_file(file_path)
                
        return self.generate_profile(df, page, limit)

    def reparse_dataset(self, dataset_id: str, request: DatasetReparse) -> DatasetProfile:
        upload_dir = os.path.join(self.data_dir, dataset_id)
        raw_path = os.path.join(upload_dir, "source", "original.raw")
        if not os.path.exists(raw_path):
            file_path, _ = get_dataset_path(dataset_id, self.data_dir)
            if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
            raw_path = file_path
            
        try:
            df, _ = parse_file(raw_path, header_row=request.header_row, sheet_name=request.sheet_name)
            self.pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header, "sheet": request.sheet_name})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        return self.generate_profile(df)

    def modify_dataset(self, dataset_id: str, modification: DatasetModification) -> DatasetProfile:
        try:
            df = get_dataframe(dataset_id, self.data_dir)
            
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
            self.pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": "modify", "modifications": len(modification.actions)})
            
            return self.generate_profile(df)
        except Exception as e: 
            raise HTTPException(status_code=400, detail=f"Failed to modify: {str(e)}")

    def get_scan_report(self, dataset_id: str) -> dict:
        path = os.path.join(self.pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        if not os.path.exists(path):
            return {"status": "no_report"}
        with open(path, "r") as f:
            return json.load(f)

    def clean_column(self, dataset_id: str, cmd: CleanCommand) -> DatasetProfile:
        try:
            df = get_dataframe(dataset_id, self.data_dir)
            if cmd.action == "to_numeric":
                df[cmd.column] = pd.to_numeric(df[cmd.column], errors='coerce')
            elif cmd.action == "fill_mean":
                if pd.api.types.is_numeric_dtype(df[cmd.column]):
                    df[cmd.column] = df[cmd.column].fillna(df[cmd.column].mean())
            elif cmd.action == "drop_na":
                df = df.dropna(subset=[cmd.column])
                
            self.pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": cmd.action, "column": cmd.column})
            
            # Rescan
            scan_result = self.scanner.scan_dataset(df)
            self._save_scan_report(dataset_id, scan_result["scan_report"])
            
            return self.generate_profile(df)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    def get_analysis_prep(self, dataset_id: str):
        df = get_dataframe(dataset_id, self.data_dir)
        _, sanitized_cols = self.prep_engine.sanitize_dataset(df)
        structure = self.prep_engine.analyze_structure(df)
        return {
            "pii_columns": sanitized_cols,
            "structure_suggestion": structure,
            "preview_rows": df.head(5).replace({pd.NA: None, float('nan'): None}).to_dict(orient="records")
        }

    def apply_prep(self, dataset_id: str, req: PrepApplyRequest) -> DatasetProfile:
        try:
            df = get_dataframe(dataset_id, self.data_dir)
            log_entry = {}
            
            if req.action == "sanitize":
                df, sanitized = self.prep_engine.sanitize_dataset(df)
                log_entry = {"action": "sanitize", "cols": sanitized}
            elif req.action == "melt":
                df = self.prep_engine.apply_melt(
                    df, 
                    id_vars=req.params.get("id_vars", []), 
                    value_vars=req.params.get("value_vars"),
                    var_name="Timepoint",
                    value_name="Value"
                )
                log_entry = {"action": "melt"}
            elif req.action == "set_header":
                 # Re-routing to reparse logic mostly, but let's handle specific set_header logic if different
                 # Actually set_header in prep usually means re-parsing.
                 return self.reparse_dataset(dataset_id, DatasetReparse(header_row=req.params.get("row_index", 0)))
            
            self.pipeline.create_processed_snapshot(dataset_id, df, cleaning_log=log_entry)
            
            scan_result = self.scanner.scan_dataset(df)
            self._save_scan_report(dataset_id, scan_result["scan_report"])
            
            return self.generate_profile(df)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    def delete_dataset(self, dataset_id: str):
        """Delete a dataset and all its files."""
        dataset_dir = os.path.join(self.data_dir, dataset_id)
        if not os.path.exists(dataset_dir):
            raise HTTPException(status_code=404, detail="Dataset not found")
        try:
            shutil.rmtree(dataset_dir)
            return {"status": "deleted", "id": dataset_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")

    def auto_classify_variables(self, dataset_id: str):
        """Automatically classify variables based on column names."""
        from app.modules.variable_classifier import classify_variables, get_classification_summary
        
        try:
            # Get dataset profile (which includes columns)
            profile = self.get_dataset(dataset_id)
            columns = [{"name": c.name, "type": c.type} for c in profile.columns]
            
            # Run classification
            classification = classify_variables(columns)
            summary = get_classification_summary(classification)
            
            return {
                "classification": classification,
                "summary": summary
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

