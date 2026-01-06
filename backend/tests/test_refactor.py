import pytest
import os
import shutil
import pandas as pd
import sys
from fastapi import UploadFile
from io import BytesIO

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.dataset_service import DatasetService

@pytest.mark.asyncio
async def test_dataset_service_upload_flow():
    # Setup
    service = DatasetService()
    dummy_csv = "id,value\n1,10\n2,20\n3,30"
    file = UploadFile(filename="test.csv", file=BytesIO(dummy_csv.encode()))
    
    # Action: Upload
    result = await service.upload_dataset(file)
    
    # Verify
    assert result.filename == "test.csv"
    assert result.id is not None
    assert result.profile.row_count == 3
    assert result.profile.col_count == 2
    
    # Action: List
    datasets = await service.list_datasets()
    assert len(datasets) > 0
    assert any(d.id == result.id for d in datasets)
    
    # Action: Clean
    from app.schemas.dataset import CleanCommand
    clean_res = service.clean_column(result.id, CleanCommand(column="value", action="to_numeric"))
    assert clean_res.row_count == 3
    
    # Cleanup
    shutil.rmtree(os.path.join(service.data_dir, result.id))
    print("Refactor Verification Passed!")

if __name__ == "__main__":
    # Manually run async test if not using pytest runner directly
    import asyncio
    asyncio.run(test_dataset_service_upload_flow())
