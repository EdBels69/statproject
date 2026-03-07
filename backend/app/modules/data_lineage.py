"""
DataLineage — tracks every transformation applied to a dataset.

Provides a JSON-serializable log of all data changes with provenance,
enabling reproducibility and automatic Data Preparation sections in reports.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class LineageEntry:
    """One recorded transformation step."""
    action: str
    details: Dict[str, Any] = field(default_factory=dict)
    rows_before: int = 0
    rows_after: int = 0
    cols_before: int = 0
    cols_after: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    def as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "action": self.action,
            "timestamp": self.timestamp,
        }
        if self.details:
            d["details"] = self.details
        if self.rows_before or self.rows_after:
            d["rows_before"] = self.rows_before
            d["rows_after"] = self.rows_after
        if self.cols_before or self.cols_after:
            d["cols_before"] = self.cols_before
            d["cols_after"] = self.cols_after
        return d


class DataLineage:
    """Tracks and serializes data transformation history."""

    def __init__(self, *, source_filename: Optional[str] = None):
        self._source = source_filename
        self._entries: List[LineageEntry] = []
        self._snapshots: Dict[str, str] = {}  # label -> sha256

    @property
    def entries(self) -> List[Dict[str, Any]]:
        return [e.as_dict() for e in self._entries]

    def record(
        self,
        action: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        df_before: Optional[pd.DataFrame] = None,
        df_after: Optional[pd.DataFrame] = None,
    ) -> None:
        """Record a transformation step."""
        entry = LineageEntry(
            action=action,
            details=details or {},
            rows_before=len(df_before) if df_before is not None else 0,
            rows_after=len(df_after) if df_after is not None else 0,
            cols_before=len(df_before.columns) if df_before is not None else 0,
            cols_after=len(df_after.columns) if df_after is not None else 0,
        )
        self._entries.append(entry)

    def record_snapshot(self, label: str, df: pd.DataFrame) -> str:
        """Record a hash snapshot of the DataFrame at a given stage."""
        h = hashlib.sha256(
            df.to_csv(index=False).encode("utf-8")
        ).hexdigest()
        self._snapshots[label] = h
        self._entries.append(LineageEntry(
            action="snapshot",
            details={"label": label, "sha256": h, "rows": len(df), "cols": len(df.columns)},
        ))
        return h

    def to_document(self) -> Dict[str, Any]:
        """Serialize full lineage as a JSON-compatible document."""
        return {
            "schema": "clinimetria.data_lineage",
            "version": 1,
            "source": self._source,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "total_steps": len(self._entries),
            "snapshots": dict(self._snapshots),
            "steps": self.entries,
        }

    def save(self, path: str) -> None:
        """Save lineage to a JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_document(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "DataLineage":
        """Load lineage from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        lineage = cls(source_filename=doc.get("source"))
        for step in doc.get("steps", []):
            entry = LineageEntry(
                action=step.get("action", ""),
                details=step.get("details", {}),
                rows_before=step.get("rows_before", 0),
                rows_after=step.get("rows_after", 0),
                cols_before=step.get("cols_before", 0),
                cols_after=step.get("cols_after", 0),
                timestamp=step.get("timestamp", ""),
            )
            lineage._entries.append(entry)
        lineage._snapshots = dict(doc.get("snapshots", {}))
        return lineage

    def summary_text(self, *, is_ru: bool = True) -> str:
        """Generate human-readable summary for reports."""
        if not self._entries:
            return "Трансформации не применялись." if is_ru else "No transformations applied."

        lines = []
        for i, e in enumerate(self._entries, 1):
            action = e.action
            detail_parts = []
            if e.rows_before and e.rows_after and e.rows_before != e.rows_after:
                detail_parts.append(f"rows: {e.rows_before}→{e.rows_after}")
            if e.cols_before and e.cols_after and e.cols_before != e.cols_after:
                detail_parts.append(f"cols: {e.cols_before}→{e.cols_after}")
            for k, v in (e.details or {}).items():
                if k in ("label", "sha256"):
                    continue
                if isinstance(v, (str, int, float, bool)):
                    detail_parts.append(f"{k}={v}")
            detail_str = f" ({', '.join(detail_parts)})" if detail_parts else ""
            lines.append(f"{i}. {action}{detail_str}")

        header = "Этапы подготовки данных:" if is_ru else "Data preparation steps:"
        return header + "\n" + "\n".join(lines)
