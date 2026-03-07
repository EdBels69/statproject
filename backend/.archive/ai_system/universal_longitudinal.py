import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List, Optional
import io
import base64


def to_native(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_native(v) for v in obj]
    elif isinstance(obj, (np.bool_, np.bool8)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return to_native(obj.tolist())
    elif pd.isna(obj):
        return None
    else:
        return obj


class UniversalLongitudinalPipeline:
    """
    The 'Heavy Lifter' engine: performs comprehensive statistical analysis 
    mimicking the 'Run Diamag Full' logic but adaptable to any dataset config.
    
    Now supports:
    - Longitudinal analysis (if endpoints have multiple timepoints)
    - Cross-sectional analysis (if no longitudinal structure detected)
    - Both numeric and categorical variables
    """

    def __init__(self, df: pd.DataFrame, config: Dict[str, Any]):
        """
        config: {
            "group_col": str,
            "visits": [v1, v2...],
            "endpoints": [ { "family_name": "UPDRS", "columns": {"V1": "UPDRS V1", ...} } ],
            "subject_col": str (optional),
            "output_dir": str (optional)
        }
        """
        self.df = df
        self.config = config
        self.results = {}
        self.artifacts = []  # List of {"type": "image", "path": "..."}

    def run(self) -> Dict[str, Any]:
        """
        Executes the full pipeline: Descriptive -> Normality -> Tests -> Plots.
        """
        group_col = self.config.get("group_col")
        if not group_col or group_col not in self.df.columns:
            return {"error": f"Group column '{group_col}' not found in data"}

        all_endpoints_results = {}
        all_single_vars_results = {}
        
        # 1. Longitudinal Endpoints (families with V1/V2/etc)
        for family in self.config.get("endpoints", []):
            family_name = family.get("family_name", "Unknown")
            col_map = family.get("columns", {})  # {V1: ColName, V2: ColName}
            
            if col_map:
                res = self._analyze_endpoint_family(family_name, col_map, group_col)
                all_endpoints_results[family_name] = res

        # 2. Cross-sectional analysis for ALL OTHER columns (not in families)
        family_cols = set()
        for fam in self.config.get("endpoints", []):
            for col in fam.get("columns", {}).values():
                family_cols.add(col)
        
        other_cols = [c for c in self.df.columns if c not in family_cols and c != group_col]
        
        for col in other_cols:
            res = self._analyze_single_variable(col, group_col)
            if res:
                all_single_vars_results[col] = res

        # Convert all numpy types to native Python types for JSON serialization
        return to_native({
            "endpoints": all_endpoints_results,
            "single_variables": all_single_vars_results,
            "generated_plots": self.artifacts
        })

    def _analyze_single_variable(self, col: str, group_col: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single (non-longitudinal) variable against the group column.
        """
        if col not in self.df.columns:
            return None
            
        is_categorical = self._is_categorical_col(col)
        
        result = {
            "type": "categorical" if is_categorical else "numeric",
            "descriptive": {},
            "test": {}
        }
        
        try:
            if is_categorical:
                # Frequency table
                ct = pd.crosstab(self.df[group_col], self.df[col])
                # Convert to serializable format
                freq_dict = {}
                for group_name in ct.index:
                    freq_dict[str(group_name)] = {str(k): int(v) for k, v in ct.loc[group_name].items()}
                result["descriptive"] = freq_dict
                result["test"] = self._compare_categorical(self.df, col, group_col)
            else:
                # Numeric descriptive per group
                desc_by_group = {}
                for grp in self.df[group_col].dropna().unique():
                    grp_data = self.df[self.df[group_col] == grp][col]
                    desc_by_group[str(grp)] = self._calc_descriptive(grp_data)
                result["descriptive"] = desc_by_group
                result["test"] = self._compare_groups(self.df, col, group_col)
        except Exception as e:
            result["error"] = str(e)
            
        return result

    def _analyze_endpoint_family(self, name: str, col_map: Dict[str, str], group_col: str):
        """
        Analyze one endpoint family (e.g. UPDRS) across visits.
        """
        visits = sorted(col_map.keys())  # Ensure order V1, V2...
        
        family_res = {
            "descriptive": {},
            "tests": {}
        }
        
        if not visits:
            return family_res
            
        first_col = col_map[visits[0]]
        is_categorical = self._is_categorical_col(first_col)

        # 1. Descriptive & Normality per Visit
        for v in visits:
            col = col_map.get(v)
            if not col or col not in self.df.columns:
                continue
                
            if is_categorical:
                # Frequency Table (convert to serializable format)
                try:
                    ct = pd.crosstab(self.df[group_col], self.df[col])
                    freq_dict = {}
                    for group_name in ct.index:
                        freq_dict[str(group_name)] = {str(k): int(val) for k, val in ct.loc[group_name].items()}
                    family_res["descriptive"][v] = {"type": "frequency", "data": freq_dict}
                except Exception as e:
                    family_res["descriptive"][v] = {"type": "error", "message": str(e)}
                
                # Chi-Square / Fisher
                test_res = self._compare_categorical(self.df, col, group_col)
                family_res["tests"][v] = test_res
            else:
                # Numeric Stats (per group)
                desc_by_group = {}
                for grp in self.df[group_col].dropna().unique():
                    grp_data = self.df[self.df[group_col] == grp][col]
                    desc_by_group[str(grp)] = self._calc_descriptive(grp_data)
                family_res["descriptive"][v] = desc_by_group
                
                # Hypothesis Test (Group Comparison at this Visit)
                test_res = self._compare_groups(self.df, col, group_col)
                family_res["tests"][v] = test_res

        # 2. Longitudinal Plot
        if not is_categorical and len(visits) > 1:
            self._plot_longitudinal(name, col_map, group_col, visits)
        
        return family_res

    def _is_categorical_col(self, col: str) -> bool:
        if col not in self.df.columns:
            return False
        s = self.df[col]
        if pd.api.types.is_numeric_dtype(s):
            return s.nunique() < 10  # heuristic
        return True

    def _compare_categorical(self, df: pd.DataFrame, target: str, group: str) -> Dict[str, Any]:
        """
        Chi-Square Test of Independence.
        """
        try:
            ct = pd.crosstab(df[group], df[target])
            # Check for small counts -> Fisher (only 2x2)
            if ct.shape == (2, 2) and ct.min().min() < 5:
                # Fisher
                odds, p = stats.fisher_exact(ct)
                return {"method": "Fisher Exact", "p_value": float(p), "significant": p < 0.05}
            else:
                # Chi2
                chi2, p, dof, ex = stats.chi2_contingency(ct)
                return {"method": "Chi-Square", "p_value": float(p), "significant": p < 0.05}
        except Exception as e:
            return {"method": "Error", "p_value": 1.0, "error": str(e), "significant": False}

    def _calc_descriptive(self, series: pd.Series) -> Dict[str, float]:
        # Force numeric, coerce errors to NaN
        clean = pd.to_numeric(series, errors='coerce').dropna()
        
        if len(clean) == 0:
            return {
                "n": 0, "mean": 0, "std": 0, "median": 0, "q1": 0, "q3": 0, "min": 0, "max": 0, "shapiro_p": 1.0
            }
        
        # Normality check
        try:
            stat, p_norm = stats.shapiro(clean) if 3 < len(clean) < 5000 else (0, 1.0)
        except:
            p_norm = 1.0
        
        return {
            "n": int(len(clean)),
            "mean": float(clean.mean()),
            "std": float(clean.std()) if len(clean) > 1 else 0.0,
            "median": float(clean.median()),
            "q1": float(clean.quantile(0.25)),
            "q3": float(clean.quantile(0.75)),
            "min": float(clean.min()),
            "max": float(clean.max()),
            "shapiro_p": float(p_norm)
        }

    def _compare_groups(self, df: pd.DataFrame, target: str, group: str) -> Dict[str, Any]:
        """
        Auto-selects T-Test/ANOVA or Mann-Whitney/Kruskal.
        """
        try:
            # Force numeric conversion
            numeric_target = pd.to_numeric(df[target], errors='coerce')
            valid_df = df[[group]].copy()
            valid_df['_target'] = numeric_target
            valid_df = valid_df.dropna()
            
            groups = valid_df[group].unique()
            if len(groups) < 2:
                return {"error": "Not enough groups", "method": "None", "p_value": 1.0, "significant": False}
                
            # Collect arrays
            arrays = [valid_df[valid_df[group] == g]['_target'].values for g in groups]
            arrays = [a for a in arrays if len(a) > 0]
            
            if len(arrays) < 2:
                return {"error": "Not enough data", "method": "None", "p_value": 1.0, "significant": False}

            # Normality check (simple: if any group is non-normal < 0.05 -> Non-Parametric)
            is_normal = True
            for a in arrays:
                if 3 < len(a) < 5000:
                    try:
                        _, p = stats.shapiro(a)
                        if p < 0.05:
                            is_normal = False
                            break
                    except:
                        pass
            
            test_name = ""
            p_value = 1.0
            
            if len(groups) == 2:
                if is_normal:
                    test_name = "T-Test (Ind)"
                    _, p_value = stats.ttest_ind(arrays[0], arrays[1])
                else:
                    test_name = "Mann-Whitney"
                    _, p_value = stats.mannwhitneyu(arrays[0], arrays[1], alternative='two-sided')
            else:
                if is_normal:
                    test_name = "ANOVA"
                    _, p_value = stats.f_oneway(*arrays)
                else:
                    test_name = "Kruskal-Wallis"
                    _, p_value = stats.kruskal(*arrays)

            return {
                "method": test_name,
                "p_value": float(p_value),
                "significant": p_value < 0.05
            }
        except Exception as e:
            return {"method": "Error", "p_value": 1.0, "error": str(e), "significant": False}

    def _plot_longitudinal(self, name: str, col_map: Dict[str, str], group_col: str, visits: List[str]):
        """
        Generates a boxplot across visits grouped by Arm.
        """
        try:
            # Melt data for plotting
            data_list = []
            for v in visits:
                col = col_map.get(v)
                if not col or col not in self.df.columns: 
                    continue
                temp = self.df[[group_col, col]].copy()
                temp.columns = ["Group", "Value"]
                temp["Value"] = pd.to_numeric(temp["Value"], errors='coerce')
                temp["Visit"] = v
                temp = temp.dropna()
                data_list.append(temp)
            
            if not data_list:
                return

            long_df = pd.concat(data_list)
            
            plt.figure(figsize=(10, 6))
            sns.boxplot(data=long_df, x="Visit", y="Value", hue="Group", palette="Set2")
            plt.title(f"Dynamics: {name}")
            plt.grid(True, alpha=0.3)
            
            # Save to buffer -> base64 (or file if we had a path)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close()
            
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.artifacts.append({
                "type": "plot",
                "name": name,
                "image_base64": b64
            })
            
        except Exception as e:
            print(f"Plotting error for {name}: {e}")
