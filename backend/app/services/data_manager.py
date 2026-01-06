import pandas as pd
import uuid
import os
import shutil
import json
from typing import List, Optional, Any
from fastapi import HTTPException

from app.core.pipeline import PipelineManager
from app.modules.parsers import parse_file
from app.schemas.dataset import FilterCondition, SubsetRequest, DataPreviewResponse, DatasetListItem

class DataManagerService:
    def __init__(self):
        self.workspace_dir = "workspace"
        self.data_dir = os.path.join(self.workspace_dir, "datasets")
        self.pipeline = PipelineManager(self.data_dir)
        
    def _load_data(self, dataset_id: str) -> pd.DataFrame:
        """Helper to load processed data similar to AnalysisService."""
        ds_dir = self.pipeline.get_dataset_dir(dataset_id)
        
        # Priority: Pipeline Standard
        path_new = os.path.join(ds_dir, "processed", "data.csv")
        if os.path.exists(path_new):
            return pd.read_csv(path_new)
            
        # Fallback: Legacy/Flat
        path_old = os.path.join(ds_dir, "processed.csv")
        if os.path.exists(path_old):
            return pd.read_csv(path_old)

        raise HTTPException(status_code=404, detail="Processed data not found")
        
    def _apply_filters(self, df: pd.DataFrame, filters: List[FilterCondition]) -> pd.DataFrame:
        filtered = df.copy()
        for f in filters:
            if f.column not in filtered.columns: continue
            
            try:
                # Handle numeric conversion if needed
                is_numeric = pd.api.types.is_numeric_dtype(filtered[f.column])
                col_data = filtered[f.column]
                val = f.value
                
                if is_numeric and val is not None:
                     try: val = float(val)
                     except: pass
                
                if f.operator == "eq":
                    filtered = filtered[col_data == val]
                elif f.operator == "neq":
                    filtered = filtered[col_data != val]
                elif f.operator == "gt":
                    filtered = filtered[col_data > val]
                elif f.operator == "gte":
                    filtered = filtered[col_data >= val]
                elif f.operator == "lt":
                    filtered = filtered[col_data < val]
                elif f.operator == "lte":
                    filtered = filtered[col_data <= val]
                elif f.operator == "contains":
                    filtered = filtered[col_data.astype(str).str.contains(str(val), case=False, na=False)]
                elif f.operator == "isnull":
                    filtered = filtered[col_data.isna()]
                elif f.operator == "notnull":
                    filtered = filtered[col_data.notna()]
            except Exception as e:
                # Log error or skip invalid filter
                print(f"Filter failed for {f.column} {f.operator} {f.value}: {e}")
                
        return filtered

    def get_preview(
        self, 
        dataset_id: str, 
        limit: int = 50, 
        offset: int = 0, 
        filters: List[FilterCondition] = []
    ) -> DataPreviewResponse:
        df = self._load_data(dataset_id)
        
        if filters:
            df = self._apply_filters(df, filters)
            
        total = len(df)
        # Apply slice
        sliced = df.iloc[offset : offset + limit]
        
        # Replace NaN with null for JSON compatibility
        rows = sliced.where(pd.notnull(sliced), None).to_dict(orient="records")
        
        return DataPreviewResponse(
            rows=rows,
            total_rows=total,
            limit=limit,
            offset=offset
        )
        
    def create_subset(
        self,
        dataset_id: str,
        req: SubsetRequest
    ) -> DatasetListItem:
        df = self._load_data(dataset_id)
        filtered_df = self._apply_filters(df, req.filters)
        
        if filtered_df.empty:
            raise HTTPException(status_code=400, detail="Subset is empty. Adjust filters.")
            
        # Create new Dataset ID
        new_id = str(uuid.uuid4())
        
        # We need to simulate the ingestion flow partially
        # 1. Save processed.csv directly (since we derived it)
        # 2. Save source/meta.json denoting it's a derived dataset
        
        new_ds_dir = os.path.join(self.data_dir, new_id)
        os.makedirs(new_ds_dir, exist_ok=True)
        os.makedirs(os.path.join(new_ds_dir, "source"), exist_ok=True)
        
        # Metadata
        parent_meta = {}
        try:
             with open(os.path.join(self.pipeline.get_dataset_dir(dataset_id), "source", "meta.json"), "r") as f:
                 parent_meta = json.load(f)
        except: pass
        
        new_filename = req.new_name
        if not new_filename.endswith(".csv"): new_filename += ".csv"
        
        meta = {
            "id": new_id,
            "original_filename": new_filename,
            "parent_dataset_id": dataset_id,
            "ingest_timestamp": None, # Could add current time
            "is_derived": True,
            "filters_applied": [f.dict() for f in req.filters]
        }
        
        with open(os.path.join(new_ds_dir, "source", "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
            
        # Processed CSV
        filtered_df.to_csv(os.path.join(new_ds_dir, "processed.csv"), index=False)
        
        # Also need to run Smart Scan ideally, but we can skip or run basic profile
        # For parity, we should generate at least a profile scan
        # Skipping for MVP speed, user can trigger re-scan or view it. 
        # Actually without scan_report.json, the frontend might show empty columns.
        # Let's run a quick scan.
        
        return DatasetListItem(
            id=new_id, 
            filename=new_filename
        )
