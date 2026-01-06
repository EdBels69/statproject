import pytest
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.planning_service import PlanningService
from app.schemas.planning import PowerAnalysisRequest

def test_power_calculation():
    service = PlanningService()
    
    # 1. T-Test Ind (Classic Example)
    # d=0.5 (medium), alpha=0.05, power=0.8
    # Standard result is ~64 per group (Total 128)
    req = PowerAnalysisRequest(
        test_type="t_test_ind",
        effect_size=0.5,
        alpha=0.05,
        power=0.8
    )
    res = service.calculate_sample_size(req)
    
    print(f"T-Test Power: N_total={res.required_n}, N_group={res.group_n}")
    
    assert res.group_n in [63, 64, 65]
    assert res.required_n in [126, 128, 130]
    
    # 2. ANOVA
    # 3 groups, f=0.25 (medium), alpha=0.05, power=0.8
    # Standard is Total ~159 (~53 per group)
    req_anova = PowerAnalysisRequest(
        test_type="anova",
        effect_size=0.25,
        alpha=0.05,
        power=0.8,
        n_groups=3
    )
    res_anova = service.calculate_sample_size(req_anova)
    
    print(f"ANOVA Power: N_total={res_anova.required_n}")
    
    assert res_anova.required_n > 150 and res_anova.required_n < 170

if __name__ == "__main__":
    test_power_calculation()
