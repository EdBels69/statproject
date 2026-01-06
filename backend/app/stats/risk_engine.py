import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from scipy import stats
from app.schemas.analysis import RiskMetric

def calculate_risk_metrics(
    df: pd.DataFrame, 
    outcome_col: str, 
    exposure_col: str, 
    outcome_pos: str, 
    exposure_pos: str
) -> Dict[str, Any]:
    """
    Constructs a 2x2 table and calculates RR, OR, RD.
    Table structure:
                Outcome+  Outcome-
    Exposure+      a         b
    Exposure-      c         d
    """
    
    # Filter and Align
    data = df[[outcome_col, exposure_col]].dropna().astype(str)
    
    # Identify labels if not strictly provided
    # (In V1 we enforce provided labels, or take first if binary)
    
    # Create Binary Series
    y_true = (data[outcome_col] == outcome_pos).astype(int)
    x_true = (data[exposure_col] == exposure_pos).astype(int)
    
    # 2x2 Table
    #           Out+ (1)  Out- (0)
    # Exp+ (1)     a         b
    # Exp- (0)     c         d
    
    a = ((x_true == 1) & (y_true == 1)).sum()
    b = ((x_true == 1) & (y_true == 0)).sum()
    c = ((x_true == 0) & (y_true == 1)).sum()
    d = ((x_true == 0) & (y_true == 0)).sum()
    
    table = {
        "exposed": {"pos": int(a), "neg": int(b)},
        "control": {"pos": int(c), "neg": int(d)}
    }
    
    n1 = a + b # Total Exposed
    n0 = c + d # Total Control
    
    metrics = []
    
    # 1. Relative Risk (RR)
    # RR = (a / n1) / (c / n0)
    # Check for zeros
    if n1 > 0 and n0 > 0 and c > 0:
        rr = (a / n1) / (c / n0)
        # CI for ln(RR): SE = sqrt(1/a - 1/n1 + 1/c - 1/n0)
        try:
            se_rr = np.sqrt((1/a) - (1/n1) + (1/c) - (1/n0)) if a > 0 else 0
            ci_low = np.exp(np.log(rr) - 1.96 * se_rr)
            ci_high = np.exp(np.log(rr) + 1.96 * se_rr)
            
            metrics.append(RiskMetric(
                name="Relative Risk (RR)",
                value=float(rr),
                ci_lower=float(ci_low),
                ci_upper=float(ci_high),
                p_value=None,
                significant=not (ci_low <= 1 <= ci_high)
            ))
        except:
             pass

    # 2. Odds Ratio (OR)
    # OR = (a*d) / (b*c)
    if b*c > 0:
        or_val = (a*d) / (b*c)
        # CI for ln(OR): SE = sqrt(1/a + 1/b + 1/c + 1/d)
        try:
            se_or = np.sqrt(1/a + 1/b + 1/c + 1/d) if a>0 and b>0 and c>0 and d>0 else 0
            ci_low = np.exp(np.log(or_val) - 1.96 * se_or)
            ci_high = np.exp(np.log(or_val) + 1.96 * se_or)
            
            # Fisher exact p-value
            _, p_val = stats.fisher_exact([[a, b], [c, d]])
            
            metrics.append(RiskMetric(
                name="Odds Ratio (OR)",
                value=float(or_val),
                ci_lower=float(ci_low),
                ci_upper=float(ci_high),
                p_value=float(p_val),
                significant=float(p_val) < 0.05
            ))
        except:
            pass
            
    # 3. Risk Difference (RD) / Absolute Risk Reduction (ARR)
    if n1 > 0 and n0 > 0:
        r1 = a / n1
        r0 = c / n0
        rd = r1 - r0
        se_rd = np.sqrt( (r1*(1-r1)/n1) + (r0*(1-r0)/n0) )
        ci_low = rd - 1.96 * se_rd
        ci_high = rd + 1.96 * se_rd
        
        metrics.append(RiskMetric(
            name="Risk Difference (RD)",
            value=float(rd),
            ci_lower=float(ci_low),
            ci_upper=float(ci_high),
            significant=not (ci_low <= 0 <= ci_high)
        ))
        
        # NNT = 1 / |RD|
        if abs(rd) > 0:
            nnt = 1 / abs(rd)
            metrics.append(RiskMetric(
                name="Number Needed to Treat (NNT)",
                value=float(nnt),
                ci_lower=0, # CI for NNT is tricky (can flip), skipping for MVP
                ci_upper=0,
                significant=False
            ))
            
    return {
        "metrics": metrics,
        "contingency_table": table
    }
