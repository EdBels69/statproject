import json
import os
import httpx
from typing import Dict, Any, List, Optional
import pandas as pd
from app.api.datasets import get_dataframe, DATA_DIR
from app.core.config import settings
from .data_cleaner import DataCleaner
from .study_detector import StudyDetectorIsolated, StudyShape
from .universal_longitudinal import UniversalLongitudinalPipeline
from .llm_client import MyLLMClient
from .script_generator import AnalysisScriptGenerator
from .executor import ScriptExecutor
from .verifier import StatisticalVerifier
from .metadata_extractor import MetadataExtractor
from .column_standardizer import ColumnStandardizer
from .design_advisor import DesignAdvisor
# DiaMag-level advanced modules
from .advanced_statistics import (
    bayes_factor_from_p, interpret_bf10, holm_adjust,
    kruskal_wallis_test, pairwise_mann_whitney,
    descriptive_stats, wilcoxon_paired
)
from .responder_analyzer import ResponderAnalyzer
from .ai_content_generator import AIContentGenerator
# Mixed Effects Models
from app.stats.mixed_effects import MixedEffectsEngine



class AIAnalysisCoordinator:
    """
    High-Level Orchestrator
    """
    
    def __init__(self):
        self.cleaner = DataCleaner()
        self.detector = StudyDetectorIsolated()
        self.llm = MyLLMClient()
        self.script_gen = AnalysisScriptGenerator()
        self.executor = ScriptExecutor(timeout_seconds=300)
        self.verifier = StatisticalVerifier()
        # Advanced AI modules
        self.metadata_extractor = MetadataExtractor()
        self.column_standardizer = ColumnStandardizer()
        self.design_advisor = DesignAdvisor()
        # DiaMag-level modules
        self.responder_analyzer = ResponderAnalyzer()
        self.content_generator = AIContentGenerator()
        self.mixed_effects = MixedEffectsEngine()
    
    async def analyze_initial(self, dataset_id: str) -> Dict[str, Any]:
        """
        Step 1: Load, Clean, Detect, Draft Plan.
        """
        # 1. Load
        df = get_dataframe(dataset_id, DATA_DIR)
        
        # Validate DataFrame loaded correctly
        if df is None or df.empty:
            return {
                "error": f"Dataset '{dataset_id}' not found or empty",
                "dataset_id": dataset_id,
                "all_columns": [],
                "variable_manifest": [],
                "shape": None,
                "draft_config": {"group_col": None, "visits": [], "endpoints": []},
                "categorical_columns": []
            }
        
        # 2. Clean
        df_clean = self.cleaner.clean_dataset(df)
        
        # 3. Detect
        shape = self.detector.detect(df_clean)
        manifest = self.detector.scan_variables(df_clean)
        
        # 4. LLM Mapping (Draft Plan)
        draft_config = await self._ask_llm_for_config(df_clean, shape)
        
        # 5. Build list of categorical columns for manual group selection
        categorical_cols = [
            m["name"] for m in manifest 
            if m.get("inferred_type") in ("categorical", "id") and m.get("unique", 0) >= 2 and m.get("unique", 0) <= 20
        ]
        
        return {
            "dataset_id": dataset_id,
            "all_columns": list(df_clean.columns),
            "variable_manifest": manifest,
            "shape": shape.dict(),
            "draft_config": draft_config,
            "categorical_columns": categorical_cols  # For manual group selection dropdown
        }

    async def run_analysis(self, dataset_id: str, confirmed_config: Dict[str, Any], selected_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Step 2: Run the engine with confirmed config.
        If selected_columns is provided, only those columns will be analyzed.
        """
        df = get_dataframe(dataset_id, DATA_DIR)
        df_clean = self.cleaner.clean_dataset(df)
        
        # Filter to selected columns if provided
        if selected_columns:
            # Always keep the group column
            group_col = confirmed_config.get('group_col')
            cols_to_keep = list(set(selected_columns + ([group_col] if group_col else [])))
            # Only keep columns that exist in the dataframe
            cols_to_keep = [c for c in cols_to_keep if c in df_clean.columns]
            df_clean = df_clean[cols_to_keep]
        
        pipeline = UniversalLongitudinalPipeline(df_clean, confirmed_config)
        results = pipeline.run()
        
        return results
    
    async def run_analysis_with_script(
        self, 
        dataset_id: str, 
        confirmed_config: Dict[str, Any], 
        selected_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        NEW: Script-based analysis for transparency and reproducibility.
        
        This method:
        1. Generates executable Python script (no data in LLM context)
        2. Executes script safely with timeout
        3. Verifies results for hallucinations/anomalies
        4. Returns results + audit trail + verification
        """
        # Load and prepare data
        df = get_dataframe(dataset_id, DATA_DIR)
        df_clean = self.cleaner.clean_dataset(df)
        
        # Filter to selected columns if provided
        if selected_columns:
            group_col = confirmed_config.get('group_col')
            cols_to_keep = list(set(selected_columns + ([group_col] if group_col else [])))
            cols_to_keep = [c for c in cols_to_keep if c in df_clean.columns]
            df_clean = df_clean[cols_to_keep]
        
        # Convert to parquet for script loading (faster than CSV)
        import tempfile
        import os
        temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.parquet', delete=False)
        dataset_path = temp_file.name
        df_clean.to_parquet(dataset_path)
        temp_file.close()
        
        try:
            # Separate variables by type
            numeric_vars = []
            categorical_vars = []
            for col in df_clean.columns:
                if col == confirmed_config.get('group_col'):
                    continue
                if df_clean[col].dtype in ['int64', 'float64']:
                    numeric_vars.append(col)
                else:
                    categorical_vars.append(col)
            
            # 1. Generate script (LLM sees only metadata, not data!)
            script_code = self.script_gen.generate_comparison_script(
                dataset_path=dataset_path,
                group_col=confirmed_config['group_col'],
                numeric_vars=numeric_vars,
                categorical_vars=categorical_vars
            )
            
            # 2. Execute script
            exec_result = self.executor.execute(script_code)
            
            if not exec_result["success"]:
                return {
                    "error": exec_result["error"],
                    "script_code": script_code  # For debugging
                }
            
            # 3. Verify results
            verification = self.verifier.verify_results(exec_result["results"])
            
            # 4. Return complete transparent results
            return {
                "results": exec_result["results"],
                "audit_log": exec_result["audit_log"],
                "summary": exec_result["summary"],
                "verification": verification,
                "script_code": script_code,  # Full reproducibility
                "method": "script-based",  # Flag for frontend
                "transparent": True
            }
            
        finally:
            # Cleanup temp file
            if os.path.exists(dataset_path):
                os.unlink(dataset_path)

    async def analyze_with_ai_expert(self, dataset_id: str) -> Dict[str, Any]:
        """
        NEW: Advanced AI Expert Analysis
        
        This method:
        1. Extracts smart metadata (no data to LLM!)
        2. Standardizes column names
        3. Recommends optimal design
        4. Returns comprehensive analysis plan
        
        Handles tables up to 10000×10000 efficiently.
        """
        # 1. Load data
        df = get_dataframe(dataset_id, DATA_DIR)
        
        if df is None or df.empty:
            return {"error": f"Dataset '{dataset_id}' not found or empty"}
        
        # 2. Extract metadata (5KB instead of 2GB!)
        metadata = self.metadata_extractor.extract(df)
        
        # 3. Standardize column names (LLM-powered)
        try:
            standardized_mapping = await self.column_standardizer.standardize(metadata)
            
            # Apply renaming to metadata
            for col_meta in metadata["columns"]:
                original_name = col_meta["name"]
                if original_name in standardized_mapping:
                    col_meta["standardized_name"] = standardized_mapping[original_name]
                else:
                    col_meta["standardized_name"] = original_name
        except Exception as e:
            print(f"Column standardization failed: {e}")
            standardized_mapping = {c["name"]: c["name"] for c in metadata["columns"]}
            for col_meta in metadata["columns"]:
                col_meta["standardized_name"] = col_meta["name"]
        
        # 4. Get expert design recommendations (LLM-powered)
        try:
            design_recommendation = await self.design_advisor.recommend(
                metadata,
                standardized_mapping
            )
        except Exception as e:
            print(f"Design recommendation failed: {e}")
            design_recommendation = {
                "study_design": {"type": "unknown", "rationale": "Failed to analyze"},
                "variables": {},
                "recommended_analyses": [],
                "visualizations": []
            }
        
        # 5. Return comprehensive analysis
        return {
            "dataset_id": dataset_id,
            "metadata": {
                "shape": metadata["shape"],
                "structure": metadata.get("detected_structure"),
                "families": metadata.get("detected_families", []),
                "quality": metadata.get("quality_summary", {})
            },
            "standardized_columns": standardized_mapping,
            "design_recommendation": design_recommendation,
            "expert_mode": True
        }

    async def run_diamag_analysis(
        self,
        dataset_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        DiaMag-Level Comprehensive Analysis.
        
        Features:
        - Kruskal-Wallis with epsilon² effect size
        - Pairwise Mann-Whitney with Holm correction and BF10
        - Responder analysis with NNT
        - Wilcoxon paired tests with effect sizes
        - AI-generated interpretations
        
        Args:
            config: {
                "group_col": "Группа",
                "endpoints": [
                    {
                        "family_name": "UPDRS III",
                        "baseline_col": "УШОБП часть 3 V2",
                        "followup_cols": {"V3": "...", "V6": "..."},
                        "direction": "lower_is_better"
                    }
                ],
                "responder_threshold": 0.20  # 20%
            }
        """
        # 1. Load data
        df = get_dataframe(dataset_id, DATA_DIR)
        if df is None or df.empty:
            return {"error": f"Dataset '{dataset_id}' not found"}
        
        df_clean = self.cleaner.clean_dataset(df)
        
        group_col = config.get("group_col")
        endpoints = config.get("endpoints", [])
        threshold = config.get("responder_threshold", 0.20)
        
        if not group_col or group_col not in df_clean.columns:
            return {"error": f"Group column '{group_col}' not found"}
        
        results = {
            "dataset_id": dataset_id,
            "n_patients": len(df_clean),
            "groups": list(df_clean[group_col].dropna().unique()),
            "endpoints": {},
        }
        
        # 2. Analyze each endpoint
        for ep in endpoints:
            name = ep.get("family_name", "unnamed")
            baseline = ep.get("baseline_col")
            followup_cols = ep.get("followup_cols", {})
            direction = ep.get("direction", "lower_is_better")
            
            if not baseline or baseline not in df_clean.columns:
                results["endpoints"][name] = {"error": f"Baseline '{baseline}' not found"}
                continue
            
            ep_result = {
                "name": name,
                "direction": direction,
                "by_visit": {},
                "responders": {},
                "paired_change": {},
            }
            
            # 2a. Kruskal-Wallis at baseline
            kw_baseline = kruskal_wallis_test(df_clean, baseline, group_col)
            ep_result["baseline_kw"] = kw_baseline
            
            # 2b. Pairwise Mann-Whitney at baseline
            pw_baseline = pairwise_mann_whitney(df_clean, baseline, group_col)
            ep_result["baseline_pairwise"] = pw_baseline
            
            # 2c. Analyze each follow-up visit
            for visit, col in followup_cols.items():
                if col not in df_clean.columns:
                    continue
                
                visit_result = {}
                
                # Kruskal-Wallis
                kw = kruskal_wallis_test(df_clean, col, group_col)
                visit_result["kruskal"] = kw
                
                # Pairwise Mann-Whitney
                pw = pairwise_mann_whitney(df_clean, col, group_col)
                visit_result["pairwise"] = pw
                
                # Responder analysis
                resp = self.responder_analyzer.analyze_responders(
                    df_clean, baseline, col, group_col, threshold, direction
                )
                visit_result["responders"] = resp
                
                # Within-group paired change (Wilcoxon)
                paired_results = {}
                for group in results["groups"]:
                    group_df = df_clean[df_clean[group_col] == group]
                    wilc = wilcoxon_paired(
                        group_df[baseline],
                        group_df[col],
                        threshold_pct=threshold
                    )
                    paired_results[str(group)] = wilc
                visit_result["paired_change"] = paired_results
                
                ep_result["by_visit"][visit] = visit_result
            
            # 2d. Descriptive stats by group
            desc_by_group = {}
            for group in results["groups"]:
                group_df = df_clean[df_clean[group_col] == group]
                desc_by_group[str(group)] = descriptive_stats(group_df[baseline])
            ep_result["descriptive_baseline"] = desc_by_group
            
            # 2e. Mixed Effects Model (LMM) for Time×Group interaction
            subject_col = config.get("subject_col")
            if subject_col and subject_col in df_clean.columns and followup_cols:
                try:
                    # Convert wide to long format
                    all_cols = {baseline: "baseline"}
                    all_cols.update(followup_cols)
                    
                    long_rows = []
                    for visit_name, col_name in [("baseline", baseline)] + list(followup_cols.items()):
                        if col_name not in df_clean.columns:
                            continue
                        tmp = df_clean[[subject_col, group_col, col_name]].copy()
                        tmp.columns = ["subject", "group", "value"]
                        tmp["visit"] = visit_name
                        long_rows.append(tmp)
                    
                    if len(long_rows) >= 2:
                        long_df = pd.concat(long_rows, ignore_index=True)
                        long_df = long_df.dropna()
                        
                        lmm_result = self.mixed_effects.fit(
                            long_df,
                            outcome="value",
                            time_col="visit",
                            group_col="group",
                            subject_col="subject",
                            random_slope=False
                        )
                        ep_result["mixed_effects"] = lmm_result
                except Exception as e:
                    ep_result["mixed_effects"] = {"error": str(e)}
            
            results["endpoints"][name] = ep_result
        
        # 3. Generate AI interpretation (if at least one endpoint analyzed)
        if results["endpoints"]:
            try:
                context = {
                    "goals": ["Compare groups on clinical endpoints"],
                    "hypotheses": ["H0: No difference between groups"],
                    "n_patients": results["n_patients"],
                }
                content = await self.content_generator.generate_discussion(
                    results["endpoints"],
                    context,
                    chunk_size=2
                )
                results["ai_content"] = content
            except Exception as e:
                results["ai_content"] = {"error": str(e)}
        
        results["analysis_type"] = "diamag_comprehensive"
        return results



    async def _ask_llm_for_config(self, df: pd.DataFrame, shape: StudyShape) -> Dict[str, Any]:
        """
        Asks GLM-4-Flash to map columns to the config structure.
        """
        # Minimal Context
        cols = list(df.columns)
        
        prompt = f"""
        You are a Data Architect. Map the columns of this dataset to a standardized analysis configuration.
        
        Dataset Columns: {cols}
        Detected Shape: {shape.json()}
        
        Task:
        1. Identify the 'group_col' (e.g. Group, Arm).
        2. Identify 'visits' (e.g. V1, V2) if longitudinal.
        3. Group longitudinal columns into families (e.g. "UPDRS V1", "UPDRS V2" -> family "UPDRS").
        
        Return JSON ONLY:
        {{
            "group_col": "Name",
            "visits": ["V1", "V2", ...],
            "endpoints": [
                {{
                    "family_name": "UPDRS III",
                    "columns": {{ "V1": "ColName_V1", "V2": "ColName_V2" }}
                }}
            ]
        }}
        """
        
        try:
            # Direct HTTP call to avoid dependency loops or complex internal logic
            # Using GLM-4-Flash as requested
            api_key = settings.GLM_API_KEY
            base_url = settings.GLM_API_URL
            
            # Fix URL if needed
            if "paas/v4" in base_url and "chat/completions" not in base_url:
                 url = base_url + "/chat/completions"
            else:
                 url = base_url

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": os.getenv("LLM_MODEL_ID", "glm-4-flash"), # Configurable: set to 'glm-4.7-flash' if available
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Cleanup JSON
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content)
                
        except Exception as e:
            # Fallback: Return empty structure or what Detector found
            print(f"LLM Error: {e}")
            return {
                "group_col": shape.group_col,
                "visits": list(shape.visit_map.keys()),
                "endpoints": [
                    {"family_name": f["family_name"], "columns": f["columns"]} for f in shape.endpoint_families
                ]
            }
