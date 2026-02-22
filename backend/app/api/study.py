from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import json
from pathlib import Path

from app.configs import StudyConfig
# from app.core.deps import get_current_user # Auth placeholder

router = APIRouter(prefix="/study", tags=["study"])

DATASETS_DIR = Path("backend/workspace/datasets") # Should come from config

def _get_study_config_path(dataset_id: str) -> Path:
    return DATASETS_DIR / dataset_id / "study_config.json"

@router.get("/{dataset_id}/config", response_model=StudyConfig)
async def get_study_config(dataset_id: str):
    """
    Get study configuration for a specific dataset.
    """
    config_path = _get_study_config_path(dataset_id)
    
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Study config not found")
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StudyConfig(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")

@router.post("/{dataset_id}/config", response_model=StudyConfig)
async def save_study_config(dataset_id: str, config: StudyConfig):
    """
    Save or update study configuration.
    """
    dataset_dir = DATASETS_DIR / dataset_id
    if not dataset_dir.exists():
         raise HTTPException(status_code=404, detail="Dataset not found")
         
    config_path = _get_study_config_path(dataset_id)
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config.model_dump_json(indent=2))
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")

@router.post("/{dataset_id}/suggest-hypotheses")
async def suggest_hypotheses(dataset_id: str):
    """
    Generate hypothesis suggestions from dataset structure (Mock/AI).
    """
    # Placeholder for AI logic
    return {
        "suggestions": [
            {
                "h0": "There is no difference between groups",
                "h1": "There is a significant difference",
                "primary": True
            }
        ]
    }
