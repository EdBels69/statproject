from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

class StudyType(str, Enum):
    RCT = "rct"
    OBSERVATIONAL = "observational"
    META_ANALYSIS = "meta"

class Hypothesis(BaseModel):
    h0: str = Field(..., description="Null hypothesis")
    h1: str = Field(..., description="Alternative hypothesis")
    primary: bool = Field(False, description="Is this the primary hypothesis?")
    rationale: Optional[str] = Field(None, description="Why this hypothesis is important")

class StudyConfig(BaseModel):
    title: str = Field(..., description="Full title of the study")
    objective: str = Field(..., description="Main objective of the study")
    study_type: StudyType = Field(StudyType.RCT, description="Type of the study design")
    
    hypotheses: List[Hypothesis] = Field(default_factory=list, description="List of study hypotheses")
    
    group_column: str = Field(..., description="Column name for grouping (e.g. 'Group')")
    subject_id_column: str = Field(..., description="Column name for subject ID")
    
    visits: List[str] = Field(default_factory=list, description="List of visits in order (e.g. ['V1', 'V2'])")
    
    alpha: float = Field(0.05, description="Significance level")
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
