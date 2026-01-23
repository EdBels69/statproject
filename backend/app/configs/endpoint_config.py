from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional

class EndpointConfig(BaseModel):
    id: str = Field(..., description="Unique identifier for the endpoint")
    name: str = Field(..., description="Full human-readable name")
    short_name: str = Field(..., description="Short name for plots/tables")
    
    # Mapping of visits to column names in the dataset
    # e.g. {"V1": "score_v1", "V2": "score_v2"}
    column_pattern: Dict[str, str] = Field(default_factory=dict)
    
    direction: Literal["lower_is_better", "higher_is_better"] = Field(
        "lower_is_better", 
        description="Direction of improvement"
    )
    
    primary: bool = Field(False, description="Is this a primary outcome?")
    
    # Clinical significance
    responder_threshold_percent: Optional[float] = Field(
        None, 
        description="Percentage change threshold for responder analysis (e.g. 20.0 for 20%)"
    )
    responder_threshold_absolute: Optional[float] = Field(
        None, 
        description="Absolute change threshold for responder analysis"
    )
    
    min_val: Optional[float] = Field(None, description="Minimum possible value of the scale")
    max_val: Optional[float] = Field(None, description="Maximum possible value of the scale")
    
    description: Optional[str] = Field(None, description="Description of the scale/metric")
