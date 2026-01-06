import pytest
import os
import shutil
import sys
from fastapi import UploadFile
from io import BytesIO

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.dataset_service import DatasetService
from app.services.analysis_service import AnalysisService
from app.schemas.analysis import AnalysisRequest

@pytest.mark.asyncio
async def test_analysis_service_flow():
    # Setup
    ds_service = DatasetService()
    an_service = AnalysisService()
    
    # Create Dummy Data (Group A vs B)
    dummy_csv = "group,value\nA,10\nA,12\nA,11\nB,20\nB,22\nB,21"
    file = UploadFile(filename="test_analysis.csv", file=BytesIO(dummy_csv.encode()))
    
    # 1. Upload
    upload_res = await ds_service.upload_dataset(file)
    dataset_id = upload_res.id
    
    try:
        # 2. Analyze
        req = AnalysisRequest(
            dataset_id=dataset_id,
            target_column="value",
            features=["group"]
        )
        
        res = await an_service.run_single_analysis(req)
        
        # Verify
        assert res.method.id is not None
        assert res.p_value is not None
        assert res.p_value < 0.05 # Should be significant
        assert "t-test" in res.method.name.lower() or "rank" in res.method.name.lower()
        
        print(f"Analysis Verified: {res.method.name}, P={res.p_value}")
        
    finally:
        # Cleanup
        shutil.rmtree(os.path.join(ds_service.data_dir, dataset_id))
        print("Cleanup done.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analysis_service_flow())
