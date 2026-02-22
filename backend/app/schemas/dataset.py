from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal

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
    head_col_offset: int = 0
    head_col_limit: int = 0
    stats_sampled: bool = False
    stats_sample_rows: Optional[int] = None
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


class StudyDesignEndpointGroupEntry(BaseModel):
    endpoint: str
    columns: List[str] = Field(default_factory=list)
    timepoints: List[str] = Field(default_factory=list)


class StudyDesignDesignUpdate(BaseModel):
    design_type: Optional[str] = None
    repeated_measures: Optional[bool] = None
    group_column: Optional[str] = None
    time_column: Optional[str] = None
    subject_column: Optional[str] = None
    endpoint_groups: Optional[List[StudyDesignEndpointGroupEntry]] = None
    id_like_columns: Optional[List[str]] = None
    outcomes: Optional[List[str]] = None
    categorical_outcomes: Optional[List[str]] = None
    predictors: Optional[List[str]] = None


class StudyDesignUpdateAction(BaseModel):
    actor: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    expected_revision: Optional[int] = None
    design: Optional[StudyDesignDesignUpdate] = None
    analysis_policy: Optional[Dict[str, Any]] = None
    notes: List[str] = Field(default_factory=list)


class DesignReviewAction(BaseModel):
    actor: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class DesignReviewDocument(BaseModel):
    dataset_id: str
    version: int = 1
    confirmed: bool = False
    confirmed_at: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_source: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_by: Optional[str] = None
    revoke_reason: Optional[str] = None
    revoke_source: Optional[str] = None
    updated_at: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    artifact_exists: bool = False


class AnalysisSetAction(BaseModel):
    actor: Optional[str] = None
    source: Optional[str] = None
    mode: Literal["complete_case", "simple_impute"] = "complete_case"
    enforce: Literal["models", "all"] = "models"
    required_non_missing: List[str] = Field(default_factory=list)
    impute_columns: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AnalysisSetDocument(BaseModel):
    dataset_id: str
    analysis_set_id: Optional[str] = None
    version: int = 1
    mode: Optional[str] = None
    enforce: Optional[str] = None
    required_non_missing: List[str] = Field(default_factory=list)
    impute_columns: List[str] = Field(default_factory=list)
    n_total: Optional[int] = None
    n_selected: Optional[int] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    created_source: Optional[str] = None
    updated_at: Optional[str] = None
    fingerprint: Dict[str, Any] = Field(default_factory=dict)
    artifact_exists: bool = False


class InteractiveCleaningOperation(BaseModel):
    operation_id: Optional[str] = None
    column: Optional[str] = None
    action: str
    enabled: bool = True
    notes: Optional[str] = None


class InteractiveCleaningApplyRequest(BaseModel):
    actor: Optional[str] = None
    source: Optional[str] = None
    operations: List[InteractiveCleaningOperation] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class InteractiveCleaningApplyResponse(BaseModel):
    dataset_id: str
    applied_count: int = 0
    skipped_count: int = 0
    operations: List[Dict[str, Any]] = Field(default_factory=list)
    profile: DatasetProfile
