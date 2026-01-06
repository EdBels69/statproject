import pytest
import os
import shutil
import sys
import pandas as pd
from fastapi import UploadFile
from io import BytesIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.dataset_service import DatasetService
from app.services.analysis_service import AnalysisService
from app.schemas.analysis import RiskAnalysisRequest

@pytest.mark.asyncio
async def test_epi_risk():
    ds = DatasetService()
    ans = AnalysisService()
    
    # Synthetic Cohort: Smoke(Yes/No) vs Cancer(Pos/Neg)
    # Group=Smoke=Yes: 40 Pos, 60 Neg -> Risk = 0.4
    # Group=Smoke=No:  10 Pos, 90 Neg -> Risk = 0.1
    # RR = 4.0
    
    data = []
    # Exposed Group
    data.extend([{"Smoke": "Yes", "Cancer": "Pos"}] * 40)
    data.extend([{"Smoke": "Yes", "Cancer": "Neg"}] * 60)
    # Control Group
    data.extend([{"Smoke": "No", "Cancer": "Pos"}] * 10)
    data.extend([{"Smoke": "No", "Cancer": "Neg"}] * 90)
    
    df = pd.DataFrame(data)
    csv_content = df.to_csv(index=False).encode()
    
    # 1. Upload
    file = UploadFile(filename="epi_cohrot.csv", file=BytesIO(csv_content))
    up_res = await ds.upload_dataset(file)
    dataset_id = up_res.id
    
    try:
        # 2. Run Risk Analysis
        req = RiskAnalysisRequest(
            dataset_id=dataset_id,
            target_column="Cancer",
            group_column="Smoke",
            target_positive_val="Pos",
            group_exposure_val="Yes"
        )
        
        res = await ans.run_risk_analysis(req)
        
        # 3. Assertions
        metrics = {m.name: m for m in res.metrics}
        
        rr = metrics.get("Relative Risk (RR)")
        assert rr is not None
        assert abs(rr.value - 4.0) < 0.1
        assert rr.significant == True
        
        or_val = metrics.get("Odds Ratio (OR)")
        assert or_val is not None
        assert abs(or_val.value - 6.0) < 0.2
        
        print(f"Epi Test Passed: RR={rr.value:.2f}, OR={or_val.value:.2f}")
        
    finally:
        shutil.rmtree(os.path.join(ds.data_dir, dataset_id))

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_epi_risk())
