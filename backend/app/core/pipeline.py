from __future__ import annotations

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
from app.core.run_state_machine import RunState, RunStateMachine
from app.core.artifact_contracts import assert_artifact_contract

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
        try:
            norm_path = os.path.normpath(str(path))
            if os.path.basename(norm_path) == "scan_report.json" and os.path.basename(os.path.dirname(norm_path)) == "processed":
                dataset_id = os.path.basename(os.path.dirname(os.path.dirname(norm_path)))
                if isinstance(dataset_id, str) and dataset_id.strip():
                    self._sync_processed_artifacts(
                        dataset_id,
                        scan_report=payload if isinstance(payload, dict) else {},
                        action="scan_report_update",
                    )
        except Exception:
            pass

    def get_dataset_dir(self, dataset_id: str) -> str:
        return self._get_dataset_dir(dataset_id)

    def _get_dataset_dir(self, dataset_id: str) -> str:
        return os.path.join(self.base_dir, dataset_id)

    @staticmethod
    def _run_state_path(run_dir: str) -> str:
        return os.path.join(run_dir, "run_state.json")

    @staticmethod
    def _artifact_key_from_filename(filename: str) -> Optional[str]:
        name = os.path.basename(str(filename or "").strip())
        mapping = {
            "protocol.json": "protocol",
            "results.json": "results",
            "verification.json": "verification",
            "protocol_report_auto.html": "report_html",
            "protocol_resolved.json": "protocol_resolved",
            "reproduce_run.py": "reproduce_script",
            "reproduce_payload.json": "reproduce_payload",
            "reproducibility_manifest.json": "reproducibility_manifest",
            "protocol_validation.json": "protocol_validation",
            "multiplicity_trace.json": "multiplicity_trace",
            "hypothesis_discovery.json": "hypothesis_discovery",
            "bootstrap_trace.json": "bootstrap_trace",
            "reflection_log.json": "reflection_log",
        }
        if name in mapping:
            return mapping[name]
        if name.endswith(".html") and "report" in name:
            return "report_html"
        return None

    def get_run_state(self, dataset_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        run_state_path = self._run_state_path(self.get_run_dir(dataset_id, run_id))
        if not os.path.exists(run_state_path):
            return None
        try:
            with open(run_state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            return loaded if isinstance(loaded, dict) else None
        except Exception:
            return None

    def update_run_state(
        self,
        run_dir: str,
        *,
        initial_state: RunState | str = RunState.COMPILE,
        to_state: Optional[RunState | str] = None,
        artifact_updates: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        strict_artifacts: bool = False,
    ) -> Dict[str, Any]:
        run_state_path = self._run_state_path(run_dir)
        existing: Dict[str, Any] = {}
        if os.path.exists(run_state_path):
            try:
                with open(run_state_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}

        state_seed = existing.get("state") if isinstance(existing.get("state"), str) else initial_state
        transitions_seed = existing.get("transitions") if isinstance(existing.get("transitions"), list) else []
        machine = RunStateMachine(initial_state=state_seed, transition_log=transitions_seed)

        artifacts = existing.get("artifacts") if isinstance(existing.get("artifacts"), dict) else {}
        artifacts = dict(artifacts)
        if isinstance(artifact_updates, dict):
            for key, value in artifact_updates.items():
                if not isinstance(key, str) or not key.strip():
                    continue
                if value is None:
                    artifacts.pop(key, None)
                    continue
                artifacts[key.strip()] = value

        if to_state is not None:
            target = str(to_state).strip().lower()
            if target and target != machine.state_value:
                machine.transition(to_state, reason=reason)

        missing = machine.missing_required_artifacts(artifacts)
        if strict_artifacts and missing:
            raise ValueError(
                f"Run state {machine.state_value} missing required artifacts: {', '.join(missing)}"
            )

        doc = machine.to_document(artifacts)
        self._atomic_write_json(run_state_path, doc)
        return doc

    def _processed_dir(self, dataset_id: str) -> str:
        return os.path.join(self._get_dataset_dir(dataset_id), "processed")

    def _safe_read_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            return loaded if isinstance(loaded, dict) else None
        except Exception:
            return None

    def _sync_profile_artifact(
        self,
        dataset_id: str,
        *,
        df: Any = None,
        scan_report: Optional[Dict[str, Any]] = None,
    ) -> None:
        profile: Dict[str, Any] = {
            "schema": "clinimetria.profile",
            "version": 1,
            "dataset_id": str(dataset_id),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source": "dataframe" if df is not None else "scan_report",
            "row_count": None,
            "column_count": None,
            "columns": [],
        }

        if df is not None and hasattr(df, "columns"):
            try:
                row_count = int(len(df))
            except Exception:
                row_count = None
            try:
                col_count = int(len(df.columns))
            except Exception:
                col_count = None
            profile["row_count"] = row_count
            profile["column_count"] = col_count

            columns: List[Dict[str, Any]] = []
            for col in [str(c) for c in df.columns]:
                try:
                    series = df[col]
                    missing_count = int(series.isna().sum())
                    unique_count = int(series.nunique(dropna=True))
                    dtype_name = str(series.dtype)
                except Exception:
                    missing_count = None
                    unique_count = None
                    dtype_name = None
                columns.append(
                    {
                        "name": col,
                        "dtype": dtype_name,
                        "missing_count": missing_count,
                        "unique_count": unique_count,
                    }
                )
            profile["columns"] = columns
        elif isinstance(scan_report, dict):
            columns_meta = scan_report.get("columns") if isinstance(scan_report.get("columns"), dict) else {}
            missing_report = scan_report.get("missing_report") if isinstance(scan_report.get("missing_report"), dict) else {}
            try:
                profile["row_count"] = int(missing_report.get("total_rows")) if missing_report.get("total_rows") is not None else None
            except Exception:
                profile["row_count"] = None
            profile["column_count"] = int(len(columns_meta))
            profile_columns: List[Dict[str, Any]] = []
            for name, meta in columns_meta.items():
                meta_obj = meta if isinstance(meta, dict) else {}
                profile_columns.append(
                    {
                        "name": str(name),
                        "dtype": str(meta_obj.get("type")) if meta_obj.get("type") is not None else None,
                        "missing_count": meta_obj.get("missing_count"),
                        "unique_count": meta_obj.get("unique_count"),
                    }
                )
            profile["columns"] = profile_columns

        path = os.path.join(self._processed_dir(dataset_id), "profile.json")
        self._atomic_write_json(path, profile)

    def _sync_data_contract_artifact(self, dataset_id: str, *, df: Any = None) -> None:
        if df is None or not hasattr(df, "columns"):
            return
        columns_out: List[Dict[str, Any]] = []
        for col in [str(c) for c in df.columns]:
            try:
                series = df[col]
                total = int(len(series))
                missing = int(series.isna().sum())
                missing_ratio = (float(missing) / float(total)) if total > 0 else 0.0
                unique_count = int(series.nunique(dropna=True))
                dtype_name = str(series.dtype)
                allowed_values = None
                if dtype_name in {"object", "category", "bool", "boolean"} and unique_count <= 20:
                    values: List[str] = []
                    for item in series.dropna().unique().tolist()[:20]:
                        values.append(str(item))
                    allowed_values = values
                quality_score = max(0.0, min(1.0, 1.0 - missing_ratio))
            except Exception:
                missing_ratio = None
                unique_count = None
                dtype_name = None
                allowed_values = None
                quality_score = None
            columns_out.append(
                {
                    "name": col,
                    "canonical_name": col,
                    "dtype": dtype_name,
                    "units": None,
                    "allowed_values": allowed_values,
                    "missing_policy": "allow",
                    "missing_ratio": missing_ratio,
                    "unique_count": unique_count,
                    "quality_score": quality_score,
                }
            )

        payload = {
            "schema": "clinimetria.data_contract",
            "version": 1,
            "dataset_id": str(dataset_id),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "columns": columns_out,
        }
        path = os.path.join(self._processed_dir(dataset_id), "data_contract.json")
        self._atomic_write_json(path, payload)

    def _sync_cleaning_plan_artifact(
        self,
        dataset_id: str,
        *,
        cleaning_log: Optional[Dict[str, Any]] = None,
        scan_report: Optional[Dict[str, Any]] = None,
    ) -> None:
        if cleaning_log is None and scan_report is None:
            return

        actions: List[Dict[str, Any]] = []
        if isinstance(cleaning_log, dict):
            action_name = str(cleaning_log.get("action") or "processed_snapshot").strip() or "processed_snapshot"
            actions.append(
                {
                    "id": "applied_1",
                    "action": action_name,
                    "status": "applied",
                    "details": cleaning_log,
                }
            )
            auto_meta = cleaning_log.get("auto") if isinstance(cleaning_log.get("auto"), dict) else {}
            auto_actions = auto_meta.get("actions") if isinstance(auto_meta.get("actions"), list) else []
            for idx, item in enumerate(auto_actions):
                if not isinstance(item, dict):
                    continue
                actions.append(
                    {
                        "id": f"applied_auto_{idx + 1}",
                        "action": str(item.get("type") or item.get("action") or "auto_clean"),
                        "status": "applied",
                        "details": item,
                    }
                )

        if not actions and isinstance(scan_report, dict):
            missing_report = scan_report.get("missing_report") if isinstance(scan_report.get("missing_report"), dict) else {}
            missing_total = missing_report.get("total_missing")
            actions.append(
                {
                    "id": "suggested_1",
                    "action": "scan_review",
                    "status": "suggested",
                    "details": {"total_missing": missing_total},
                }
            )

        payload = {
            "schema": "clinimetria.cleaning_plan",
            "version": 1,
            "dataset_id": str(dataset_id),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "applied" if isinstance(cleaning_log, dict) else "suggested",
            "actions": actions,
        }
        path = os.path.join(self._processed_dir(dataset_id), "cleaning_plan.json")
        self._atomic_write_json(path, payload)

    def _append_data_lineage(
        self,
        dataset_id: str,
        *,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        rows_after: Optional[int] = None,
        columns_after: Optional[int] = None,
    ) -> None:
        path = os.path.join(self._processed_dir(dataset_id), "data_lineage.json")
        existing = self._safe_read_json(path) or {}
        entries = existing.get("entries") if isinstance(existing.get("entries"), list) else []
        entry = {
            "action": str(action or "snapshot"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "rows_after": rows_after,
            "columns_after": columns_after,
            "details": details if isinstance(details, dict) else {},
        }
        entries.append(entry)
        if len(entries) > 500:
            entries = entries[-500:]
        payload = {
            "schema": "clinimetria.data_lineage",
            "version": 1,
            "dataset_id": str(dataset_id),
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "entries": entries,
        }
        self._atomic_write_json(path, payload)

    def _sync_processed_artifacts(
        self,
        dataset_id: str,
        *,
        df: Any = None,
        cleaning_log: Optional[Dict[str, Any]] = None,
        scan_report: Optional[Dict[str, Any]] = None,
        action: str = "processed_snapshot",
    ) -> None:
        rows_after = int(len(df)) if df is not None and hasattr(df, "__len__") else None
        cols_after = int(len(df.columns)) if df is not None and hasattr(df, "columns") else None
        self._sync_profile_artifact(dataset_id, df=df, scan_report=scan_report)
        self._sync_data_contract_artifact(dataset_id, df=df)
        self._sync_cleaning_plan_artifact(dataset_id, cleaning_log=cleaning_log, scan_report=scan_report)
        lineage_details = cleaning_log if isinstance(cleaning_log, dict) else {"source": "scan_report" if scan_report else "snapshot"}
        self._append_data_lineage(
            dataset_id,
            action=action,
            details=lineage_details,
            rows_after=rows_after,
            columns_after=cols_after,
        )

    def _collect_dataset_stage_artifacts(self, dataset_id: str) -> Dict[str, Any]:
        ds_dir = self._get_dataset_dir(dataset_id)
        source_dir = os.path.join(ds_dir, "source")
        processed_dir = os.path.join(ds_dir, "processed")
        artifacts: Dict[str, Any] = {}

        source_raw = os.path.join(source_dir, "original.raw")
        if os.path.exists(source_raw):
            artifacts["source_raw"] = os.path.join("source", "original.raw")

        source_meta = os.path.join(source_dir, "meta.json")
        if os.path.exists(source_meta):
            artifacts["source_meta"] = os.path.join("source", "meta.json")
        else:
            legacy_meta = os.path.join(ds_dir, "metadata.json")
            if os.path.exists(legacy_meta):
                artifacts["source_meta"] = "metadata.json"

        profile_path = os.path.join(processed_dir, "profile.json")
        if os.path.exists(profile_path):
            artifacts["profile"] = os.path.join("processed", "profile.json")
        else:
            scan_report = os.path.join(processed_dir, "scan_report.json")
            if os.path.exists(scan_report):
                artifacts["profile"] = os.path.join("processed", "scan_report.json")

        cleaning_plan = os.path.join(processed_dir, "cleaning_plan.json")
        if os.path.exists(cleaning_plan):
            artifacts["cleaning_plan"] = os.path.join("processed", "cleaning_plan.json")

        cleaning_log = os.path.join(processed_dir, "cleaning_log.json")
        if os.path.exists(cleaning_log):
            artifacts["cleaning_log"] = os.path.join("processed", "cleaning_log.json")

        processed_dataset = os.path.join(processed_dir, f"{dataset_id}.parquet")
        if os.path.exists(processed_dataset):
            artifacts["processed_dataset"] = os.path.join("processed", f"{dataset_id}.parquet")

        design_path = os.path.join(processed_dir, "study_design.json")
        if os.path.exists(design_path):
            artifacts["design"] = os.path.join("processed", "study_design.json")

        analysis_pointer = self._safe_read_json(os.path.join(processed_dir, "analysis_set_current.json")) or {}
        set_id = analysis_pointer.get("analysis_set_id") if isinstance(analysis_pointer.get("analysis_set_id"), str) else None
        if set_id:
            analysis_artifact = os.path.join(processed_dir, "analysis_sets", f"{set_id}.json")
            if os.path.exists(analysis_artifact):
                artifacts["analysis_set"] = os.path.join("processed", "analysis_sets", f"{set_id}.json")
            else:
                artifacts["analysis_set"] = os.path.join("processed", "analysis_set_current.json")
            analysis_parquet = os.path.join(processed_dir, "analysis_sets", f"{set_id}.parquet")
            if os.path.exists(analysis_parquet):
                artifacts["analysis_set_dataset"] = os.path.join("processed", "analysis_sets", f"{set_id}.parquet")

        analysis_set_hash = os.path.join(processed_dir, "analysis_set_hash.json")
        if os.path.exists(analysis_set_hash):
            artifacts["analysis_set_hash"] = os.path.join("processed", "analysis_set_hash.json")

        return artifacts

    def _bootstrap_run_state_with_dataset(self, run_dir: str, dataset_id: str) -> Dict[str, Any]:
        artifacts = self._collect_dataset_stage_artifacts(dataset_id)
        artifacts["protocol"] = "protocol.json"

        machine = RunStateMachine(initial_state=RunState.INGEST)
        for target, reason in [
            (RunState.PROFILE, "dataset_profile_ready"),
            (RunState.CLEAN, "dataset_clean_ready"),
            (RunState.DESIGN, "dataset_design_ready"),
            (RunState.FREEZE, "analysis_set_ready"),
        ]:
            if machine.missing_required_artifacts(artifacts):
                break
            if machine.can_transition(target):
                machine.transition(target, reason=reason)

        if machine.state == RunState.FREEZE and not machine.missing_required_artifacts(artifacts):
            machine.transition(RunState.COMPILE, reason="protocol_compiled")
            return machine.to_document(artifacts)

        fallback = RunStateMachine(initial_state=RunState.COMPILE)
        return fallback.to_document(artifacts)

    def collect_dataset_state_artifacts(self, dataset_id: str) -> Dict[str, Any]:
        return self._collect_dataset_stage_artifacts(dataset_id)

    def build_dataset_state_document(self, dataset_id: str) -> Dict[str, Any]:
        artifacts = self._collect_dataset_stage_artifacts(dataset_id)
        machine = RunStateMachine(initial_state=RunState.INGEST)
        for target, reason in [
            (RunState.PROFILE, "dataset_profile_ready"),
            (RunState.CLEAN, "dataset_clean_ready"),
            (RunState.DESIGN, "dataset_design_ready"),
            (RunState.FREEZE, "analysis_set_ready"),
        ]:
            if machine.missing_required_artifacts(artifacts):
                break
            if machine.can_transition(target):
                machine.transition(target, reason=reason)
        return machine.to_document(artifacts)

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
            assert_artifact_contract("source_meta.json", next_meta)
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
            if os.path.exists(parquet_path):
                history_root = os.path.join(processed_dir, "history")
                os.makedirs(history_root, exist_ok=True)
                stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                snap_dir = os.path.join(history_root, stamp)
                os.makedirs(snap_dir, exist_ok=True)

                for name in [f"{dataset_id}.parquet", "dtypes.json", "cleaning_log.json", "scan_report.json"]:
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
                        if isinstance(s.dtype, pd.CategoricalDtype):
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
                self._sync_processed_artifacts(
                    dataset_id,
                    df=df,
                    cleaning_log=cleaning_log if isinstance(cleaning_log, dict) else {},
                    action="create_processed_snapshot",
                )
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
        for name in [f"{dataset_id}.parquet", "dtypes.json", "cleaning_log.json", "scan_report.json"]:
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
            protocol_payload = dict(protocol) if isinstance(protocol, dict) else {}
            if not isinstance(protocol_payload.get("name"), str) or not str(protocol_payload.get("name")).strip():
                protocol_payload["name"] = "Protocol"
            try:
                protocol_payload["alpha"] = float(protocol_payload.get("alpha", 0.05))
            except Exception:
                protocol_payload["alpha"] = 0.05
            if not isinstance(protocol_payload.get("steps"), list):
                protocol_payload["steps"] = []
            assert_artifact_contract("protocol.json", protocol_payload)

            os.makedirs(run_dir, exist_ok=True)
            os.makedirs(os.path.join(run_dir, "artifacts"), exist_ok=True)
            self._atomic_write_json(os.path.join(run_dir, "protocol.json"), protocol_payload)
            state_doc = self._bootstrap_run_state_with_dataset(run_dir, dataset_id)
            self._atomic_write_json(self._run_state_path(run_dir), state_doc)
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
            if not isinstance(payload.get("dataset_id"), str) or not str(payload.get("dataset_id")).strip():
                payload["dataset_id"] = dataset_id
            if not isinstance(payload.get("results"), (dict, list)):
                payload["results"] = {}
            if not isinstance(payload.get("errors"), list):
                payload["errors"] = []
            if not isinstance(payload.get("warnings"), list):
                payload["warnings"] = []
            if not isinstance(payload.get("status"), str) or not str(payload.get("status")).strip():
                payload["status"] = "partial" if payload["errors"] else "completed"
            assert_artifact_contract("results.json", payload)
            self._atomic_write_json(path, payload)
            self.update_run_state(run_dir, artifact_updates={"results": "results.json"})

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
            artifact_key = self._artifact_key_from_filename(safe_name)
            if artifact_key:
                rel_path = os.path.join("artifacts", safe_name)
                self.update_run_state(run_dir, artifact_updates={artifact_key: rel_path})
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
            "p_value_raw",
            "p_value_adj",
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
            "assumptions",
            "warnings",
            "plots",
            "bootstrap",
            "multiplicity_correction",
            "multiplicity_trace",
            "multiplicity_trace_by_slice",
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

    def process_with_quality_gate(
        self,
        dataset_id: str,
        *,
        file_path: str,
        original_filename: str = "",
        header_row: Optional[int] = None,
        sheet_name: Optional[str] = None,
        outlier_policy: str = "flag",
        missing_threshold: float = 0.7,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        High-level pipeline: ExcelIntelligence → DataQualityGate → DataLineage.

        Reads a raw file, cleans it through the quality gate, records lineage,
        and optionally creates a processed snapshot. Returns a summary report.

        Args:
            dataset_id: Dataset identifier
            file_path: Path to the source file
            original_filename: Original upload filename (for extension detection)
            header_row: Override header row (None = auto-detect)
            sheet_name: Optional Excel sheet name/index
            outlier_policy: "flag", "winsorize", or "remove"
            missing_threshold: Drop columns with missing ratio above this
            persist: Whether to write parquet/artifacts to disk

        Returns:
            Dict with keys:
                parquet_path, dataframe, quality_report, cleaning_log,
                cleaning_plan, data_contract, lineage, structure_log
        """
        # --- Step 1: Parse with ExcelIntelligence ---
        structure_log: Optional[Dict[str, Any]] = None
        parse_error: Optional[str] = None
        try:
            from app.modules.parsers import parse_file_intelligent
            df, detected_header, structure_log = parse_file_intelligent(
                file_path,
                header_row=header_row,
                sheet_name=sheet_name,
                original_filename=original_filename,
            )
            if not isinstance(structure_log, dict):
                structure_log = None
        except Exception as e:
            parse_error = str(e)
            from app.modules.parsers import parse_file
            df, detected_header = parse_file(
                file_path,
                header_row=header_row or 0,
                sheet_name=sheet_name,
                original_filename=original_filename,
            )
            structure_log = None

        # --- Step 2: Run DataQualityGate ---
        quality_report = None
        gate_error: Optional[str] = None
        gate = None
        df_raw = df
        df_clean = df
        cleaning_log: Dict[str, Any] = {
            "schema": "clinimetria.cleaning_log",
            "version": 1,
            "action": "ingest_parse",
            "rows_original": int(len(df_raw)),
            "rows_final": int(len(df_raw)),
            "cols_original": int(len(df_raw.columns)),
            "cols_final": int(len(df_raw.columns)),
            "header_row": int(detected_header),
            "steps": [],
            "issues": [],
            "warnings": [],
        }
        cleaning_plan: Dict[str, Any] = {
            "schema": "clinimetria.cleaning_plan",
            "version": 1,
            "config": {
                "outlier_policy": str(outlier_policy or "flag"),
                "max_missing_threshold": float(missing_threshold),
            },
            "steps": [],
        }
        data_contract: Optional[Dict[str, Any]] = None
        quality_report_payload: Optional[Dict[str, Any]] = None

        try:
            from app.modules.data_quality_gate import DataQualityGate
            gate = DataQualityGate(
                outlier_policy=outlier_policy,
                max_missing_threshold=float(missing_threshold),
            )
            quality_report = gate.run(df)
            df_clean = quality_report.df_clean
            cleaning_log = gate.to_cleaning_log_json(quality_report)
            cleaning_log["action"] = "quality_gate"
            cleaning_log["header_row"] = int(detected_header)
            cleaning_plan = gate.to_cleaning_plan_json(quality_report)
            data_contract = (
                quality_report.data_contract
                if isinstance(quality_report.data_contract, dict)
                else None
            )
            quality_report_payload = {
                "is_ready": bool(quality_report.is_ready),
                "overall_score": float(quality_report.overall_score),
                "issues": list(quality_report.issues or []),
                "warnings": list(quality_report.warnings or []),
                "rows_original": int(quality_report.rows_original),
                "rows_final": int(quality_report.rows_final),
                "cols_original": int(quality_report.cols_original),
                "cols_final": int(quality_report.cols_final),
            }
        except Exception as e:
            gate_error = str(e)
            quality_report = None
            df_clean = df_raw
            cleaning_log["action"] = "quality_gate_failed"
            cleaning_log["warnings"] = [f"quality_gate_failed: {gate_error}"]

        # --- Step 3: Record DataLineage ---
        lineage_doc: Optional[Dict[str, Any]] = None
        try:
            from app.modules.data_lineage import DataLineage
            lineage = DataLineage(source_filename=original_filename or os.path.basename(file_path))
            lineage.record(
                "ingest_parse",
                details={
                    "file": original_filename or file_path,
                    "header_row": int(detected_header),
                    "sheet_name": sheet_name,
                    "structure_log": structure_log if isinstance(structure_log, dict) else None,
                    "parse_error": parse_error,
                },
                df_before=df_raw,
                df_after=df_raw,
            )
            if structure_log:
                lineage.record(
                    "excel_intelligence",
                    details=structure_log,
                    df_before=df_raw,
                    df_after=df_raw,
                )
            if quality_report:
                lineage.record(
                    "quality_gate",
                    details={
                        "is_ready": bool(quality_report.is_ready),
                        "overall_score": float(quality_report.overall_score),
                        "issues_count": int(len(quality_report.issues)),
                        "warnings_count": int(len(quality_report.warnings)),
                        "outlier_policy": str(outlier_policy or "flag"),
                        "max_missing_threshold": float(missing_threshold),
                    },
                    df_before=df_raw,
                    df_after=df_clean,
                )
                for step in (quality_report.cleaning_log or []):
                    if not isinstance(step, dict):
                        continue
                    lineage.record(
                        step.get("action", "quality_gate_step"),
                        details=step,
                    )
            elif gate_error:
                lineage.record(
                    "quality_gate_failed",
                    details={"error": gate_error},
                    df_before=df_raw,
                    df_after=df_clean,
                )
            lineage.record_snapshot("processed", df_clean)
            lineage_doc = lineage.to_document()
            if isinstance(lineage_doc, dict):
                lineage_doc["dataset_id"] = str(dataset_id)
                if isinstance(lineage_doc.get("steps"), list) and not isinstance(lineage_doc.get("entries"), list):
                    lineage_doc["entries"] = list(lineage_doc["steps"])
        except Exception:
            lineage_doc = None

        parquet_path: Optional[str] = None
        if persist:
            parquet_path = self.create_processed_snapshot(dataset_id, df_clean, cleaning_log)
            processed_dir = self._processed_dir(dataset_id)
            if isinstance(cleaning_plan, dict):
                try:
                    self._atomic_write_json(
                        os.path.join(processed_dir, "cleaning_plan.json"),
                        cleaning_plan,
                    )
                except Exception:
                    pass
            if isinstance(data_contract, dict):
                try:
                    self._atomic_write_json(
                        os.path.join(processed_dir, "data_contract.json"),
                        data_contract,
                    )
                except Exception:
                    pass
            if isinstance(lineage_doc, dict):
                try:
                    self._atomic_write_json(
                        os.path.join(processed_dir, "data_lineage.json"),
                        lineage_doc,
                    )
                except Exception:
                    pass

        return {
            "parquet_path": parquet_path,
            "dataframe": df_clean,
            "rows": int(len(df_clean)),
            "columns": int(len(df_clean.columns)),
            "header_row": detected_header,
            "quality_gate_applied": quality_report is not None,
            "error": gate_error,
            "quality_report": quality_report_payload,
            "lineage": lineage_doc,
            "cleaning_log": cleaning_log,
            "cleaning_plan": cleaning_plan,
            "data_contract": data_contract,
            "structure_log": structure_log,
        }
