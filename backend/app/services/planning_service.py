import math
from statsmodels.stats.power import (
    TTestIndPower, TTestPower, FTestAnovaPower, GofChisquarePower
)
from app.schemas.planning import PowerAnalysisRequest, PowerAnalysisResult

class PlanningService:
    """
    Standalone service for Sample Size and Power calculations.
    Does not depend on any Dataset or File Processing logic.
    """
    
    def calculate_sample_size(self, req: PowerAnalysisRequest) -> PowerAnalysisResult:
        n_total = 0
        n_per_group = 0
        desc = ""
        
        if req.test_type == "t_test_ind":
            analysis = TTestIndPower()
            # ratio is n2/n1. If 1, equal groups.
            # nobs1 is returned by solve_power
            n_per_group = analysis.solve_power(
                effect_size=req.effect_size, 
                alpha=req.alpha, 
                power=req.power, 
                ratio=req.ratio or 1.0, 
                alternative='two-sided'
            )
            n_per_group = math.ceil(n_per_group)
            n_total = n_per_group * (1 + (req.ratio or 1.0))
            desc = f"Independent T-Test (d={req.effect_size}, alpha={req.alpha}, power={req.power})"
            
        elif req.test_type == "t_test_paired":
            analysis = TTestPower()
            # Paired is treated as one-sample of differences
            n_per_group = analysis.solve_power(
                effect_size=req.effect_size, 
                alpha=req.alpha, 
                power=req.power, 
                alternative='two-sided'
            )
            n_per_group = math.ceil(n_per_group)
            n_total = n_per_group # Total pairs
            desc = f"Paired T-Test (d={req.effect_size}, pairs needed)"
            
        elif req.test_type == "anova":
            analysis = FTestAnovaPower()
            k = req.n_groups or 3
            # Statsmodels FTestAnovaPower returns the TOTAL sample size (nobs) by default logic??
            # Actually, let's look at the result: 157.
            # G*Power says Total 159. So it returns Total N (or very close to it).
            # Previous code assumed 'n_per_group'.
            
            n_total_calc = analysis.solve_power(
                effect_size=req.effect_size, 
                alpha=req.alpha, 
                power=req.power, 
                k_groups=k
            )
            n_total = math.ceil(n_total_calc)
            n_per_group = math.ceil(n_total / k)
            desc = f"One-Way ANOVA ({k} groups, f={req.effect_size})"
            
        elif req.test_type == "chi_square":
            analysis = GofChisquarePower()
            # Chi-square goodness of fit / association
            n_total = analysis.solve_power(
                effect_size=req.effect_size, 
                alpha=req.alpha, 
                power=req.power, 
                n_bins=(req.n_groups or 2) # degrees of freedom roughly
            )
            n_total = math.ceil(n_total)
            n_per_group = 0 # Not applicable directly/varies
            desc = f"Chi-Square Test (w={req.effect_size})"
        
        return PowerAnalysisResult(
            test_type=req.test_type,
            required_n=int(n_total),
            group_n=int(n_per_group),
            description=desc,
            parameters=req.dict()
        )
