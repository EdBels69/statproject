import pytest
import pandas as pd
import numpy as np
import os
import shutil
import sys
from fastapi import UploadFile
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.dataset_service import DatasetService
from app.services.data_manager import DataManagerService
from app.schemas.dataset import FilterCondition, SubsetRequest, DataPreviewRequest

@pytest.mark.asyncio
async def test_datamanager():
    ds = DatasetService()
    dm = DataManagerService()
    
    # 1. Create Dataset
    # 100 people: 50 Males, 50 Females.
    # Ages: 20-80
    data = []
    for i in range(50):
        data.append({"ID": i, "Sex": "Male", "Age": 60}) # All Males 60
    for i in range(50):
        data.append({"ID": i+50, "Sex": "Female", "Age": 30}) # All Females 30
        
    df = pd.DataFrame(data)
    csv_content = df.to_csv(index=False).encode()
    
    file = UploadFile(filename="datagrid_test.csv", file=BytesIO(csv_content))
    up_res = await ds.upload_dataset(file)
    dataset_id = up_res.id
    new_id = None
    
    try:
        # 2. Test Preview with Filter (Sex = Male)
        filters = [
            FilterCondition(column="Sex", operator="eq", value="Male")
        ]
        
        preview = dm.get_preview(dataset_id, limit=10, filters=filters)
        assert preview.total_rows == 50 # Should match 50 males
        assert len(preview.rows) == 10
        assert preview.rows[0]["Sex"] == "Male"
        
        # 3. Test Numeric Filter (Age > 40)
        # Should also be 50 males (Age 60)
        filters_num = [
            FilterCondition(column="Age", operator="gt", value=40)
        ]
        preview_num = dm.get_preview(dataset_id, filters=filters_num)
        assert preview_num.total_rows == 50
        
        # 4. Create Subset
        req = SubsetRequest(
            new_name="Males Only",
            filters=filters
        )
        subset_res = dm.create_subset(dataset_id, req)
        new_id = subset_res.id
        
        # 5. Verify Subset
        subset_df = dm._load_data(new_id)
        assert len(subset_df) == 50
        assert all(subset_df["Sex"] == "Male")
        
        print("DataManager verified!")
        
    finally:
        shutil.rmtree(os.path.join(ds.data_dir, dataset_id))
        if new_id:
            shutil.rmtree(os.path.join(ds.data_dir, new_id))
        
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_datamanager())
