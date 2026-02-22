import os
import shutil
import json
import tempfile
import time
import uuid
import errno
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

from app.modules.analysis_result_v2 import normalize_run_data_results

class PipelineManager:
    """
    Manages the folder structure and snapshots for the Data Pipeline.
    Enforces the Source -> Processed -> Analysis hierarchy.
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def _lock_path(self, dataset_id: str) -> str:
        return os.path.join(self._get_dataset_dir(dataset_id), ".lock")

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(int(pid), 0)
            return True
        except OSError as e:
            if getattr(e, "errno", None) == errno.ESRCH:
                return False
            return True
        except Exception:
            return False

    @contextmanager
    def _dataset_lock(self, dataset_id: str, timeout_s: float = 15.0):
        lock_path = self._lock_path(dataset_id)
        start = time.time()
        fd: Optional[int] = None
        stale_ttl_s = 600.0

        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                break
            except FileExistsError:
                try:
                    existing_pid: Optional[int] = None
                    with open(lock_path, "r") as f:
                        raw = f.read().strip()
                    if raw:
                        existing_pid = int(raw)

                    if existing_pid is not None and not self._pid_alive(existing_pid):
                        try:
                            os.remove(lock_path)
                            continue
                        except Exception:
                            pass

                    try:
                        age = time.time() - float(os.path.getmtime(lock_path))
                        if age >= stale_ttl_s:
                            os.remove(lock_path)
                            continue
                    except Exception:
                        pass
                except Exception:
                    pass
                if (time.time() - start) >= float(timeout_s):
                    raise TimeoutError(f"Dataset lock timeout: {dataset_id}")
                time.sleep(0.05)

        try:
            yield
        finally:
            try:
                if fd is not None:
                    os.close(fd)
            except Exception:
                pass
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                pass

    def _atomic_write_bytes(self, path: str, data: bytes) -> None:
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def _atomic_write_json(self, path: str, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        self._atomic_write_bytes(path, data)

    def write_json_atomic(self, path: str, payload: Any, *, allow_nan: bool = True) -> None:
        if not isinstance(payload, dict):
            payload = {}
        data = json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
            allow_nan=bool(allow_nan),
        ).encode("utf-8")
        self._atomic_write_bytes(path, data)

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
        with self._dataset_lock(dataset_id):
            file_path = os.path.join(paths["source"], "original.raw")
            self._atomic_write_bytes(file_path, file_content)

            next_meta = dict(meta or {})
            next_meta["original_filename"] = filename
            next_meta["ingest_timestamp"] = datetime.now().isoformat()
            self._atomic_write_json(os.path.join(paths["source"], "meta.json"), next_meta)

            return file_path

    def create_processed_snapshot(self, dataset_id: str, df, cleaning_log: Dict[str, Any] = None) -> str:
        """
        Stage 1: Save cleaned dataframe to processed/ directory.
        Returns path to the primary processed file.
        """
        import pandas as pd
        paths = self.initialize_dataset(dataset_id)
        processed_dir = paths["processed"]
        parquet_path = os.path.join(processed_dir, f"{dataset_id}.parquet")

        with self._dataset_lock(dataset_id):
            previous_df = None
            if os.path.exists(parquet_path):
                try:
                    previous_df = pd.read_parquet(parquet_path)
                except Exception:
                    previous_df = None
                history_root = os.path.join(processed_dir, "history")
                os.makedirs(history_root, exist_ok=True)
                stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                snap_dir = os.path.join(history_root, stamp)
                os.makedirs(snap_dir, exist_ok=True)

                for name in [f"{dataset_id}.parquet", "dtypes.json", "cleaning_log.json", "cleaning_run.json", "scan_report.json"]:
                    src = os.path.join(processed_dir, name)
                    if os.path.exists(src):
                        try:
                            shutil.copy2(src, os.path.join(snap_dir, name))
                        except Exception:
                            pass

            tmp_path = os.path.join(processed_dir, f".tmp_{dataset_id}.{int(time.time() * 1000)}.parquet")

            try:
                df.to_parquet(tmp_path, engine="pyarrow", index=False)
            except Exception:
                df_copy = df.copy()
                for col in df_copy.columns:
                    try:
                        s = df_copy[col]
                        if pd.api.types.is_categorical_dtype(s.dtype):
                            try:
                                cats = list(s.cat.categories[:2000])
                                cat_types = {type(v) for v in cats if v is not None}
                            except Exception:
                                cat_types = set()

                            if len(cat_types) > 1:
                                df_copy[col] = s.astype(str).replace("nan", pd.NA).replace("None", pd.NA)
                            continue

                        if s.dtype != object:
                            continue

                        probe = s.dropna().head(2000)
                        types = {type(v) for v in probe.tolist()} if not probe.empty else set()
                        if len(types) <= 1 and (not types or list(types)[0] is str):
                            continue

                        df_copy[col] = s.astype(str).replace("nan", pd.NA).replace("None", pd.NA)
                    except Exception:
                        try:
                            df_copy[col] = df_copy[col].astype(str).replace("nan", pd.NA).replace("None", pd.NA)
                        except Exception:
                            pass

                df_copy.to_parquet(tmp_path, engine="pyarrow", index=False)
            os.replace(tmp_path, parquet_path)

            dtypes = df.dtypes.astype(str).to_dict()
            self._atomic_write_json(os.path.join(processed_dir, "dtypes.json"), dtypes)

            if cleaning_log:
                self._atomic_write_json(os.path.join(processed_dir, "cleaning_log.json"), cleaning_log)
                try:
                    from app.modules.cleaning_run import (
                        build_cleaning_run_artifact,
                        save_cleaning_run_artifact,
                    )

                    artifact = build_cleaning_run_artifact(
                        dataset_id=str(dataset_id),
                        cleaning_log=cleaning_log if isinstance(cleaning_log, dict) else {},
                        df_before=previous_df if isinstance(previous_df, pd.DataFrame) else None,
                        df_after=df,
                        actor="system",
                        source="pipeline",
                    )
                    save_cleaning_run_artifact(self.base_dir, dataset_id, artifact)
                except Exception:
                    pass

            return parquet_path

    def get_processed_history_count(self, dataset_id: str) -> int:
        processed_dir = os.path.join(self._get_dataset_dir(dataset_id), "processed")
        history_root = os.path.join(processed_dir, "history")
        if not os.path.isdir(history_root):
            return 0
        try:
            items = [d for d in os.listdir(history_root) if os.path.isdir(os.path.join(history_root, d))]
            return int(len(items))
        except Exception:
            return 0

    def restore_last_processed_snapshot(self, dataset_id: str) -> bool:
        processed_dir = os.path.join(self._get_dataset_dir(dataset_id), "processed")
        history_root = os.path.join(processed_dir, "history")
        if not os.path.isdir(history_root):
            return False

        try:
            items = [d for d in os.listdir(history_root) if os.path.isdir(os.path.join(history_root, d))]
            items.sort()
        except Exception:
            return False

        if not items:
            return False

        snap_dir = os.path.join(history_root, items[-1])
        restored_any = False
        for name in [f"{dataset_id}.parquet", "dtypes.json", "cleaning_log.json", "cleaning_run.json", "scan_report.json"]:
            src = os.path.join(snap_dir, name)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, os.path.join(processed_dir, name))
                    restored_any = True
                except Exception:
                    pass

        try:
            shutil.rmtree(snap_dir, ignore_errors=True)
        except Exception:
            pass

        return restored_any
    
    def create_analysis_run(self, dataset_id: str, protocol: Dict[str, Any]) -> str:
        """
        Stage 2: Create a new isolation container for an analysis run.
        Returns the path to the run directory.
        """
        paths = self.initialize_dataset(dataset_id)

        with self._dataset_lock(dataset_id):
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            run_id = f"run_{timestamp}_{uuid.uuid4().hex[:8]}"
            run_dir = os.path.join(paths["analysis"], run_id)

            os.makedirs(run_dir, exist_ok=True)
            os.makedirs(os.path.join(run_dir, "artifacts"), exist_ok=True)
            self._atomic_write_json(os.path.join(run_dir, "protocol.json"), protocol if isinstance(protocol, dict) else {})
            return run_dir

    def save_run_results(self, run_dir: str, results: Dict):
        ds_dir = os.path.dirname(os.path.dirname(run_dir))
        dataset_id = os.path.basename(ds_dir)
        with self._dataset_lock(dataset_id):
            path = os.path.join(run_dir, "results.json")
            payload = normalize_run_data_results(results if isinstance(results, dict) else {})
            if isinstance(payload.get("results"), (dict, list)) and "result_ir" not in payload:
                next_payload = dict(payload)
                next_payload["result_ir"] = self.build_result_ir(next_payload)
                payload = next_payload
            self._atomic_write_json(path, payload)

    def get_run_dir(self, dataset_id: str, run_id: str) -> str:
        return os.path.join(self._get_dataset_dir(dataset_id), "analysis", run_id)

    def get_run_artifacts_dir(self, dataset_id: str, run_id: str) -> str:
        return os.path.join(self.get_run_dir(dataset_id, run_id), "artifacts")

    def save_run_artifact(self, run_dir: str, filename: str, content: bytes) -> str:
        ds_dir = os.path.dirname(os.path.dirname(run_dir))
        dataset_id = os.path.basename(ds_dir)

        safe_name = os.path.basename(str(filename or "").strip())
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("Invalid artifact filename")
        if safe_name != str(filename).strip():
            raise ValueError("Invalid artifact filename")

        with self._dataset_lock(dataset_id):
            artifacts_dir = os.path.join(run_dir, "artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)
            path = os.path.join(artifacts_dir, safe_name)
            self._atomic_write_bytes(path, content)
            return path

    def save_run_analysis_dataset(self, run_dir: str, df) -> Dict[str, Any]:
        ds_dir = os.path.dirname(os.path.dirname(run_dir))
        dataset_id = os.path.basename(ds_dir)

        rows = int(getattr(df, "shape", [0, 0])[0]) if hasattr(df, "shape") else 0
        cols = int(getattr(df, "shape", [0, 0])[1]) if hasattr(df, "shape") else 0

        parquet_name = "analysis_dataset.parquet"
        xlsx_name = "analysis_dataset.xlsx"
        xlsx_row_limit = 1_048_576

        metadata: Dict[str, Any] = {
            "parquet": None,
            "xlsx": None,
            "rows": rows,
            "columns": cols,
            "xlsx_status": "pending",
            "xlsx_reason": None,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

        with self._dataset_lock(dataset_id):
            artifacts_dir = os.path.join(run_dir, "artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)

            parquet_path = os.path.join(artifacts_dir, parquet_name)
            tmp_parquet = os.path.join(
                artifacts_dir, f".tmp_analysis_dataset_{int(time.time() * 1000)}.parquet"
            )
            try:
                df.to_parquet(tmp_parquet, engine="pyarrow", index=False)
                os.replace(tmp_parquet, parquet_path)
                metadata["parquet"] = parquet_name
            finally:
                try:
                    if os.path.exists(tmp_parquet):
                        os.remove(tmp_parquet)
                except Exception:
                    pass

            if rows > xlsx_row_limit:
                metadata["xlsx_status"] = "skipped"
                metadata["xlsx_reason"] = (
                    f"row_limit_exceeded:{rows}>{xlsx_row_limit}"
                )
            else:
                xlsx_path = os.path.join(artifacts_dir, xlsx_name)
                tmp_xlsx = os.path.join(
                    artifacts_dir, f".tmp_analysis_dataset_{int(time.time() * 1000)}.xlsx"
                )
                try:
                    df.to_excel(tmp_xlsx, index=False)
                    os.replace(tmp_xlsx, xlsx_path)
                    metadata["xlsx"] = xlsx_name
                    metadata["xlsx_status"] = "exported"
                except Exception as e:
                    metadata["xlsx_status"] = "failed"
                    metadata["xlsx_reason"] = str(e)
                finally:
                    try:
                        if os.path.exists(tmp_xlsx):
                            os.remove(tmp_xlsx)
                    except Exception:
                        pass

            self._atomic_write_json(
                os.path.join(artifacts_dir, "analysis_dataset.meta.json"),
                metadata,
            )

        return metadata

    def read_run_artifact(self, dataset_id: str, run_id: str, filename: str) -> bytes:
        safe_name = os.path.basename(str(filename or "").strip())
        if not safe_name or safe_name in {".", ".."}:
            raise FileNotFoundError("Artifact not found")
        if safe_name != str(filename).strip():
            raise FileNotFoundError("Artifact not found")

        path = os.path.join(self.get_run_artifacts_dir(dataset_id, run_id), safe_name)
        if not os.path.exists(path) or not os.path.isfile(path):
            raise FileNotFoundError("Artifact not found")
        with open(path, "rb") as f:
            return f.read()

    def get_run_results(self, dataset_id: str, run_id: str) -> Dict:
        # Tries to find results.json
        run_path = os.path.join(self._get_dataset_dir(dataset_id), "analysis", run_id, "results.json")
        if os.path.exists(run_path):
            with open(run_path, "r") as f:
                loaded = json.load(f)
            loaded = normalize_run_data_results(loaded if isinstance(loaded, dict) else {})
            if isinstance(loaded, dict) and isinstance(loaded.get("results"), (dict, list)):
                if "result_ir" not in loaded:
                    next_loaded = dict(loaded)
                    next_loaded["result_ir"] = self.build_result_ir(next_loaded)
                    loaded = next_loaded
            return loaded
        return None

    @staticmethod
    def _extract_summary(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        summary: Dict[str, Any] = {}
        for key in [
            "method_id",
            "engine",
            "p_value",
            "adjusted_p_value",
            "significant",
            "significant_adj",
            "stat_value",
            "stats",
            "effect_size",
            "effect_size_name",
            "effect_size_ci_lower",
            "effect_size_ci_upper",
            "diagnostics",
            "warnings",
            "plots",
            "power",
            "bf10",
            "r_squared",
        ]:
            if key in payload:
                summary[key] = payload.get(key)

        if "conclusion" in payload and isinstance(payload.get("conclusion"), str):
            summary["conclusion"] = payload.get("conclusion")
        return summary

    @staticmethod
    def _make_block(step_id: Any, payload: Any, *, status: Optional[str] = None) -> Dict[str, Any]:
        sid = str(step_id) if step_id is not None else "step"
        pdata = payload if isinstance(payload, dict) else {"value": payload}

        kind = pdata.get("type") if isinstance(pdata.get("type"), str) and pdata.get("type") else "result"
        method = pdata.get("method") if isinstance(pdata.get("method"), dict) else None
        if method is None and isinstance(pdata.get("method_id"), str) and pdata.get("method_id").strip():
            method = {"id": str(pdata.get("method_id")).strip(), "name": str(pdata.get("method_id")).strip()}
        title = None
        if isinstance(pdata.get("title"), str) and pdata.get("title"):
            title = pdata.get("title")
        elif isinstance(pdata.get("label"), str) and pdata.get("label"):
            title = pdata.get("label")
        elif isinstance(method, dict) and isinstance(method.get("name"), str) and method.get("name"):
            title = method.get("name")
        else:
            title = sid

        block_status = status
        if not isinstance(block_status, str) or not block_status:
            block_status = "error" if pdata.get("error") else "completed"

        conclusion = pdata.get("conclusion")
        if not (isinstance(conclusion, str) and conclusion.strip()):
            ai = pdata.get("ai_interpretation")
            conclusion = ai if isinstance(ai, str) else None

        out: Dict[str, Any] = {
            "id": sid,
            "kind": kind,
            "title": title,
            "status": block_status,
            "summary": PipelineManager._extract_summary(pdata),
            "method": method,
            "conclusion": conclusion,
            "payload": pdata,
        }
        return out

    @staticmethod
    def build_result_ir(run_data: Any) -> Dict[str, Any]:
        base: Dict[str, Any] = {}
        if isinstance(run_data, dict):
            base = run_data

        results = base.get("results")
        blocks: List[Dict[str, Any]] = []

        if isinstance(results, dict):
            for step_id, payload in results.items():
                blocks.append(PipelineManager._make_block(step_id, payload))
        elif isinstance(results, list):
            for i, item in enumerate(results):
                if not isinstance(item, dict):
                    blocks.append(PipelineManager._make_block(f"step_{i+1}", item))
                    continue
                step_id = item.get("step_id") or item.get("id") or f"step_{i+1}"
                payload = item.get("results") if "results" in item else item.get("payload")
                status = item.get("status")
                blocks.append(PipelineManager._make_block(step_id, payload, status=status if isinstance(status, str) else None))

        errors = base.get("errors") if isinstance(base.get("errors"), list) else []
        log = base.get("log") if isinstance(base.get("log"), list) else []

        inferred_status = base.get("status")
        if not isinstance(inferred_status, str) or not inferred_status:
            inferred_status = "partial" if errors or any(b.get("status") == "error" for b in blocks) else "completed"

        ir: Dict[str, Any] = {
            "schema": "clinimetria.result_ir",
            "version": 1,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "dataset_id": base.get("dataset_id"),
            "protocol_name": base.get("protocol_name"),
            "status": inferred_status,
            "blocks": blocks,
            "errors": errors,
            "log": log,
            "total_steps": base.get("total_steps"),
            "completed_steps": base.get("completed_steps"),
            "failed_steps": base.get("failed_steps"),
        }
        return ir
