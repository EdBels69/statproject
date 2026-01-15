import os
import shutil
import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

class PipelineManager:
    """
    Manages the folder structure and snapshots for the Data Pipeline.
    Enforces the Source -> Processed -> Analysis hierarchy.
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def get_dataset_dir(self, dataset_id: str) -> str:
        return self._get_dataset_dir(dataset_id)

    def _get_dataset_dir(self, dataset_id: str) -> str:
        return os.path.join(self.base_dir, dataset_id)

    def initialize_dataset(self, dataset_id: str) -> Dict[str, str]:
        """
        Creates the standard folder structure for a new dataset.
        Returns paths to key directories.
        """
        ds_dir = self._get_dataset_dir(dataset_id)
        
        paths = {
            "root": ds_dir,
            "source": os.path.join(ds_dir, "source"),
            "processed": os.path.join(ds_dir, "processed"),
            "analysis": os.path.join(ds_dir, "analysis")
        }
        
        for p in paths.values():
            os.makedirs(p, exist_ok=True)
            
        return paths

    def save_source(self, dataset_id: str, file_content: bytes, filename: str, meta: Dict[str, Any] = {}) -> str:
        """
        Stage 0: Save raw file to source/ directory and write metadata.
        """
        paths = self.initialize_dataset(dataset_id)
        
        # Save Raw File
        file_path = os.path.join(paths["source"], "original.raw")
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        # Save Metadata
        meta["original_filename"] = filename
        meta["ingest_timestamp"] = datetime.now().isoformat()
        
        with open(os.path.join(paths["source"], "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
            
        return file_path

    def create_processed_snapshot(self, dataset_id: str, df, cleaning_log: Dict[str, Any] = None) -> str:
        """
        Stage 1: Save cleaned dataframe to processed/ directory.
        Returns path to the primary processed file.
        """
        import pandas as pd
        paths = self.initialize_dataset(dataset_id)

        # Fix mixed-type object columns before Parquet save
        # PyArrow can't handle object columns with mixed types (e.g., str + int)
        df_copy = df.copy()
        for col in df_copy.columns:
            if df_copy[col].dtype == object:
                # Convert to string to avoid PyArrow errors
                df_copy[col] = df_copy[col].astype(str).replace('nan', pd.NA).replace('None', pd.NA)

        parquet_path = os.path.join(paths["processed"], f"{dataset_id}.parquet")
        df_copy.to_parquet(parquet_path, engine="pyarrow", index=False)
        
        # Save schema/dtypes
        dtypes = df.dtypes.astype(str).to_dict()
        with open(os.path.join(paths["processed"], "dtypes.json"), "w") as f:
            json.dump(dtypes, f, indent=2)
            
        # Save log
        if cleaning_log:
             with open(os.path.join(paths["processed"], "cleaning_log.json"), "w") as f:
                json.dump(cleaning_log, f, indent=2)
                
        return parquet_path
    
    def create_analysis_run(self, dataset_id: str, protocol: Dict[str, Any]) -> str:
        """
        Stage 2: Create a new isolation container for an analysis run.
        Returns the path to the run directory.
        """
        paths = self.initialize_dataset(dataset_id)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{timestamp}"
        run_dir = os.path.join(paths["analysis"], run_id)
        
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(os.path.join(run_dir, "artifacts"), exist_ok=True)
        
        # Save Protocol Config
        with open(os.path.join(run_dir, "protocol.json"), "w") as f:
            json.dump(protocol, f, indent=2)
            
        return run_dir

    def save_run_results(self, run_dir: str, results: Dict):
        path = os.path.join(run_dir, "results.json")
        with open(path, "w") as f:
            json.dump(results, f, indent=2, default=str)

    def get_run_results(self, dataset_id: str, run_id: str) -> Dict:
        # Tries to find results.json
        run_path = os.path.join(self._get_dataset_dir(dataset_id), "analysis", run_id, "results.json")
        if os.path.exists(run_path):
            with open(run_path, "r") as f:
                return json.load(f)
        return None
