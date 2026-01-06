from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List

from app.schemas.dataset import (
    DatasetUpload, DatasetProfile, DatasetReparse, DatasetModification, 
    DatasetListItem, CleanCommand, PrepApplyRequest,
    DataPreviewRequest, DataPreviewResponse, SubsetRequest
)
from app.services.dataset_service import DatasetService
from app.services.data_manager import DataManagerService
import os

router = APIRouter()

DATA_DIR = "workspace/datasets"

# Dependency Injection
def get_service():
    return DatasetService()

def get_data_manager():
    return DataManagerService()

@router.get("", response_model=List[DatasetListItem])
async def list_datasets(service: DatasetService = Depends(get_service)):
    return await service.list_datasets()

@router.post("", response_model=DatasetUpload)
async def upload_dataset(file: UploadFile = File(...), service: DatasetService = Depends(get_service)):
    return await service.upload_dataset(file)

@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(dataset_id: str, page: int = 1, limit: int = 100, service: DatasetService = Depends(get_service)):
    return service.get_dataset(dataset_id, page, limit)

@router.post("/{dataset_id}/reparse", response_model=DatasetProfile)
def reparse_dataset(dataset_id: str, request: DatasetReparse, service: DatasetService = Depends(get_service)):
    return service.reparse_dataset(dataset_id, request)

@router.post("/{dataset_id}/clean_column", response_model=DatasetProfile)
def clean_column(dataset_id: str, cmd: CleanCommand, service: DatasetService = Depends(get_service)):
    return service.clean_column(dataset_id, cmd)

@router.get("/{dataset_id}/prep/analyze")
def analyze_dataset_prep(dataset_id: str, service: DatasetService = Depends(get_service)):
    return service.get_analysis_prep(dataset_id)

@router.post("/{dataset_id}/prep/apply", response_model=DatasetProfile)
def apply_dataset_prep(dataset_id: str, req: PrepApplyRequest, service: DatasetService = Depends(get_service)):
    return service.apply_prep(dataset_id, req)

@router.post("/{dataset_id}/modify", response_model=DatasetProfile)
def modify_dataset(dataset_id: str, modification: DatasetModification, service: DatasetService = Depends(get_service)):
    return service.modify_dataset(dataset_id, modification)

@router.get("/{dataset_id}/scan_report")
def get_scan_report(dataset_id: str, service: DatasetService = Depends(get_service)):
    return service.get_scan_report(dataset_id)

@router.post("/{dataset_id}/preview", response_model=DataPreviewResponse)
def preview_data(dataset_id: str, req: DataPreviewRequest, manager: DataManagerService = Depends(get_data_manager)):
    return manager.get_preview(dataset_id, req.limit, req.offset, req.filters)

@router.post("/{dataset_id}/subset", response_model=DatasetListItem)
def create_subset(dataset_id: str, req: SubsetRequest, manager: DataManagerService = Depends(get_data_manager)):
    return manager.create_subset(dataset_id, req)

@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, service: DatasetService = Depends(get_service)):
    return service.delete_dataset(dataset_id)

@router.post("/{dataset_id}/auto_classify")
def auto_classify_variables(dataset_id: str, service: DatasetService = Depends(get_service)):
    """Automatically classify variables based on column names."""
    return service.auto_classify_variables(dataset_id)