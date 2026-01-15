from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class ColumnInfo(BaseModel):
    name: str
    type: str  # numeric, categorical, datetime, text
    missing_count: int
    unique_count: int
    example: Optional[Any] = None

class DatasetProfile(BaseModel):
    row_count: int
    col_count: int
    columns: List[ColumnInfo]
    head: List[Dict[str, Any]]  # Current page rows
    page: int = 1
    total_pages: int = 1

class DatasetUpload(BaseModel):
    id: str
    filename: str
    profile: DatasetProfile

class DatasetReparse(BaseModel):
    header_row: int = 0
    sheet_name: Optional[str] = None

class ModificationAction(BaseModel):
    type: str = Field(..., description="rename_col, drop_col, change_type, update_cell, drop_row")
    # Args depend on type
    column: Optional[str] = None
    new_name: Optional[str] = None
    new_type: Optional[str] = None # numeric, categorical, datetime, text
    row_index: Optional[int] = None
    value: Optional[Any] = None

class DatasetModification(BaseModel):
    actions: List[ModificationAction]

class QualityIssue(BaseModel):
    column: Optional[str] = None
    type: str # constant, near_constant, outliers, missing, etc.
    severity: str # high, medium, low
    message: str
    suggestion: Optional[str] = None

class QualityReport(BaseModel):
    dataset_id: str
    issues: List[QualityIssue]
    summary: Optional[str] = None


class VariableMappingEntry(BaseModel):
    role: Optional[str] = None
    group_var: bool = False
    subgroup: Optional[str] = None
    timepoint: Optional[str] = None
    display_name: Optional[str] = None
    data_type: Optional[str] = None
    include_descriptive: bool = True
    include_comparison: bool = True


class VariableMappingUpdate(BaseModel):
    mapping: Dict[str, VariableMappingEntry] = Field(default_factory=dict)


class VariableMappingDocument(BaseModel):
    dataset_id: str
    mapping: Dict[str, VariableMappingEntry] = Field(default_factory=dict)
