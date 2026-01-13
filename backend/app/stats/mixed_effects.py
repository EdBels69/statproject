"""
Mixed Effects Models Engine
===========================
Memory-efficient implementation of Linear Mixed Models for Time×Group interaction analysis.
Optimized for MacBook M1 8GB constraints.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Literal
import gc
import warnings
from scipy import stats as scipy_stats

# Lazy imports to reduce startup time
def _get_statsmodels():
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import AnovaRM
    return smf, AnovaRM


class MixedEffectsEngine:
    """
    Linear Mixed Model implementation with Time×Group interaction.
    Supports:
    - Random intercept models
    - Random intercept + slope models
    - Covariates adjustment
    - Memory-efficient processing for large datasets
    """
    
    def __init__(self, max_memory_mb: int = 1200):
        self.max_memory = max_memory_mb * 1024 * 1024  # bytes
    
    def fit(
        self,
        df: pd.DataFrame,
        outcome: str,
        time_col: str,
        group_col: str,
        subject_col: str,
        covariates: List[str] = None,
        random_slope: bool = False,
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Fits Linear Mixed Model with Time×Group interaction.
        
        Parameters
        ----------
        outcome : str
            Dependent variable column name
        time_col : str
            Time/Visit variable column name
        group_col : str
            Treatment group column name
        subject_col : str
            Subject ID column name
        covariates : List[str], optional
            Additional covariates to include
        random_slope : bool
            If True, adds random slope for time
        alpha : float
            Significance level (default 0.05)
        
        Returns
        -------
        Dict with model results, coefficients, and interpretation
        """
        smf, _ = _get_statsmodels()
        
        # Prepare data
        required_cols = [outcome, time_col, group_col, subject_col]
        if covariates:
            required_cols.extend(covariates)
        
        # Filter to required columns and drop missing
        analysis_df = df[[c for c in required_cols if c in df.columns]].dropna().copy()
        
        if len(analysis_df) < 10:
            return {
                "error": "Insufficient data",
                "message": f"Only {len(analysis_df)} complete observations available"
            }
        
        # Ensure categorical types
        analysis_df[time_col] = analysis_df[time_col].astype('category')
        analysis_df[group_col] = analysis_df[group_col].astype('category')
        
        # Build formula: outcome ~ Time * Group + covariates
        fixed_effects = f"{outcome} ~ C({time_col}) * C({group_col})"
        if covariates:
            cov_terms = " + ".join(covariates)
            fixed_effects += f" + {cov_terms}"
        
        # Random effects
        re_formula = "~1" if not random_slope else f"~1 + C({time_col})"
        
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                model = smf.mixedlm(
                    fixed_effects,
                    data=analysis_df,
                    groups=analysis_df[subject_col],
                    re_formula=re_formula
                )
                result = model.fit(method='lbfgs', maxiter=500)
                
                return self._extract_results(
                    result, analysis_df, time_col, group_col, outcome, alpha
                )
                
        except Exception as e:
            return {
                "error": str(e),
                "suggestion": "Check data quality or reduce model complexity"
            }
        finally:
            gc.collect()
    
    def _extract_results(
        self, 
        result, 
        analysis_df: pd.DataFrame,
        time_col: str, 
        group_col: str, 
        outcome: str,
        alpha: float
    ) -> Dict[str, Any]:
        """Extract and format model results"""
        
        params = result.params
        pvalues = result.pvalues
        
        # Identify term types
        interaction_terms = [
            p for p in params.index 
            if f"C({time_col})" in p and f"C({group_col})" in p
        ]
        
        time_terms = [
            p for p in params.index 
            if f"C({time_col})" in p and f"C({group_col})" not in p
        ]
        
        group_terms = [
            p for p in params.index 
            if f"C({group_col})" in p and f"C({time_col})" not in p
        ]
        
        # Interaction analysis
        interaction_pvalues = {
            term: float(pvalues[term]) 
            for term in interaction_terms
            if term in pvalues
        }
        
        min_interaction_p = min(interaction_pvalues.values()) if interaction_pvalues else 1.0
        interaction_significant = min_interaction_p < alpha

        estimated_means: Dict[str, Any] = {}
        try:
            grouped = (
                analysis_df
                .groupby([group_col, time_col], observed=False)[outcome]
                .agg(['mean', 'count', 'std'])
                .reset_index()
            )

            for _, row in grouped.iterrows():
                g = str(row[group_col])
                t = str(row[time_col])
                mean = float(row['mean']) if row['mean'] == row['mean'] else None
                n = int(row['count']) if row['count'] == row['count'] else 0
                sd = float(row['std']) if row['std'] == row['std'] else None

                se = (sd / np.sqrt(n)) if (sd is not None and n > 1) else None
                tcrit = float(scipy_stats.t.ppf(1 - alpha / 2, df=n - 1)) if n > 1 else None

                ci_lower = float(mean - tcrit * se) if (mean is not None and se is not None and tcrit is not None) else None
                ci_upper = float(mean + tcrit * se) if (mean is not None and se is not None and tcrit is not None) else None

                if g not in estimated_means:
                    estimated_means[g] = {}

                estimated_means[g][t] = {
                    'estimate': mean,
                    'ci_lower': ci_lower,
                    'ci_upper': ci_upper,
                    'n': n
                }
        except Exception:
            estimated_means = {}
        
        # Build coefficient table
        coef_table = []
        try:
            conf_int = result.conf_int()
            for idx in params.index:
                coef_table.append({
                    "term": str(idx),
                    "coefficient": float(params[idx]),
                    "std_error": float(result.bse[idx]) if idx in result.bse.index else None,
                    "z_value": float(result.tvalues[idx]) if idx in result.tvalues.index else None,
                    "p_value": float(pvalues[idx]) if idx in pvalues.index else None,
                    "ci_lower": float(conf_int.loc[idx, 0]) if idx in conf_int.index else None,
                    "ci_upper": float(conf_int.loc[idx, 1]) if idx in conf_int.index else None,
                    "significant": pvalues[idx] < alpha if idx in pvalues.index else False
                })
        except Exception:
            # Fallback if conf_int fails
            for idx in params.index:
                coef_table.append({
                    "term": str(idx),
                    "coefficient": float(params[idx]),
                    "p_value": float(pvalues[idx]) if idx in pvalues.index else None,
                    "significant": pvalues[idx] < alpha if idx in pvalues.index else False
                })
        
        return {
            "method": "Linear Mixed Model",
            "outcome": outcome,
            "formula": f"{outcome} ~ Time * Group + (1|Subject)",
            "n_observations": int(result.nobs),
            "n_subjects": int(getattr(result, 'ngroups', 0)) or len(set(result.model.groups)),
            
            # Main effects
            "main_effect_time": {
                "terms": time_terms,
                "significant": any(pvalues.get(t, 1.0) < alpha for t in time_terms)
            },
            "main_effect_group": {
                "terms": group_terms,
                "significant": any(pvalues.get(t, 1.0) < alpha for t in group_terms)
            },
            
            # Interaction (key result)
            "interaction": {
                "terms": interaction_terms,
                "p_values": interaction_pvalues,
                "min_p_value": min_interaction_p,
                "significant": interaction_significant,
                "interpretation": self._interpret_interaction(
                    interaction_significant, min_interaction_p
                )
            },

            "interaction_p_value": min_interaction_p,
            
            # Model fit
            "fit": {
                "log_likelihood": float(result.llf),
                "aic": float(result.aic) if hasattr(result, 'aic') else None,
                "bic": float(result.bic) if hasattr(result, 'bic') else None
            },

            "model_statistics": {
                "log_likelihood": float(result.llf),
                "aic": float(result.aic) if hasattr(result, 'aic') else None,
                "bic": float(result.bic) if hasattr(result, 'bic') else None
            },

            "estimated_means": estimated_means,
            
            # Coefficients
            "coefficients": coef_table
        }
    
    def _interpret_interaction(self, significant: bool, p_value: float) -> str:
        """Generate human-readable interpretation"""
        if significant:
            return (
                f"Статистически значимое взаимодействие Время×Группа (p={p_value:.4f}). "
                f"Траектории изменения показателя различаются между группами."
            )
        else:
            return (
                f"Взаимодействие Время×Группа не достигло статистической значимости "
                f"(p={p_value:.4f}). Траектории изменения не различаются значимо."
            )


class RepeatedMeasuresEngine:
    """
    Repeated Measures ANOVA implementation.
    For simpler within-subject designs without mixed effects.
    """
    
    def fit(
        self,
        df: pd.DataFrame,
        outcome_cols: List[str],
        subject_col: str,
        group_col: str = None,
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Fits Repeated Measures ANOVA.
        
        Parameters
        ----------
        outcome_cols : List[str]
            Column names for each timepoint (wide format)
        subject_col : str
            Subject ID column
        group_col : str, optional
            Between-subjects grouping factor
        alpha : float
            Significance level
        
        Returns
        -------
        Dict with ANOVA table and results
        """
        _, AnovaRM = _get_statsmodels()
        
        # Convert wide to long format
        id_vars = [subject_col]
        if group_col:
            id_vars.append(group_col)
        
        long_df = df.melt(
            id_vars=id_vars,
            value_vars=outcome_cols,
            var_name='Time',
            value_name='Value'
        ).dropna()
        
        long_df['Value'] = pd.to_numeric(long_df['Value'], errors='coerce')
        long_df = long_df.dropna()
        
        if len(long_df) < 10:
            return {"error": "Insufficient data for RM-ANOVA"}
        
        try:
            if group_col:
                aovrm = AnovaRM(
                    long_df, 
                    'Value', 
                    subject_col, 
                    within=['Time'],
                    between=[group_col]
                )
            else:
                aovrm = AnovaRM(
                    long_df, 
                    'Value', 
                    subject_col, 
                    within=['Time']
                )
            
            result = aovrm.fit()
            anova_table = result.anova_table
            
            # Extract key results
            time_row = anova_table.loc['Time'] if 'Time' in anova_table.index else None
            interaction_row = None
            if group_col and f'Time:{group_col}' in anova_table.index:
                interaction_row = anova_table.loc[f'Time:{group_col}']
            
            return {
                "method": "Repeated Measures ANOVA",
                "n_subjects": long_df[subject_col].nunique(),
                "n_timepoints": len(outcome_cols),
                
                "time_effect": {
                    "F": float(time_row['F Value']) if time_row is not None else None,
                    "p_value": float(time_row['Pr > F']) if time_row is not None else None,
                    "significant": time_row['Pr > F'] < alpha if time_row is not None else False
                } if time_row is not None else None,
                
                "interaction": {
                    "F": float(interaction_row['F Value']) if interaction_row is not None else None,
                    "p_value": float(interaction_row['Pr > F']) if interaction_row is not None else None,
                    "significant": interaction_row['Pr > F'] < alpha if interaction_row is not None else False
                } if interaction_row is not None else None,
                
                "anova_table": anova_table.to_dict() if hasattr(anova_table, 'to_dict') else str(anova_table),
                
                "note": "Sphericity not tested. Consider Greenhouse-Geisser correction if violated."
            }
            
        except Exception as e:
            return {"error": str(e)}
        finally:
            gc.collect()


# Convenience function
def run_mixed_effects(
    df: pd.DataFrame,
    outcome: str,
    time_col: str,
    group_col: str,
    subject_col: str,
    covariates: List[str] = None,
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Quick function to run Mixed Effects analysis.
    
    Example
    -------
    >>> result = run_mixed_effects(
    ...     df, 
    ...     outcome="UPDRS_Part3",
    ...     time_col="Visit",
    ...     group_col="Group",
    ...     subject_col="PatientID"
    ... )
    >>> print(result["interaction"]["significant"])
    True
    """
    engine = MixedEffectsEngine()
    return engine.fit(
        df, outcome, time_col, group_col, subject_col, 
        covariates=covariates, alpha=alpha
    )
