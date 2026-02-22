from typing import List, Dict, Any, Optional, Tuple

class StudyDesignEngine:
    """
    Expert System that translates high-level 'Study Goals' into executable 'Analysis Protocols'.
    Acts as the 'Methodologist' role.
    """

    def suggest_protocol(self, goal: str, variables: Dict[str, Any], metadata: Dict[str, Any], template_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point.
        goal: 'compare_groups', 'relationship', 'survival', 'prediction'
        variables: { 'target': 'Hb', 'group': 'Treatment', 'time': 'Month' }
        metadata: { 'Hb': { 'is_normal': False, 'type': 'numeric' } }
        
        Returns: A fully-formed Protocol JSON ready for the Engine.
        """
        steps: List[Dict[str, Any]] = []
        name = "Generated Study"

        variables = variables if isinstance(variables, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}

        dataset_title = (
            variables.get("dataset_title")
            or variables.get("title")
            or variables.get("filename")
            or ""
        )

        if bool(variables.get("auto")):
            auto_protocol = self._design_from_title_and_metadata(dataset_title, metadata, variables)
            if isinstance(auto_protocol, dict) and auto_protocol.get("steps"):
                return {
                    "name": auto_protocol.get("name") or name,
                    "goal": auto_protocol.get("goal") or goal,
                    "steps": auto_protocol.get("steps") or [],
                    "required_visualization": "dashboard_v1",
                }
        
        if goal == "compare_groups":
            target = variables.get("target")
            group = variables.get("group")
            time_col = variables.get("time") # Optional for dynamic
            
            if time_col:
                # DYNAMIC (Repeated Measures)
                name = f"Dynamic Analysis of {target} by {group}"
                steps = self._design_dynamic_comparison(target, group, time_col, metadata)
            else:
                # STATIC (Cross-sectional)
                name = f"Comparison of {target} by {group}"
                steps = self._design_static_comparison(target, group, metadata)

            if template_id == "compare_quick":
                steps = [s for s in steps if s.get("id") != "desc_stats"]

        elif goal == "relationship":
            target = variables.get("target")
            predictor = variables.get("predictor")
            name = f"Correlation: {target} vs {predictor}"
            steps = self._design_correlation(target, predictor, metadata)

        elif goal in {"association", "predict"}:
            target = variables.get("target")
            exposure = variables.get("predictor") or variables.get("exposure")
            covariates = variables.get("covariates")
            if not isinstance(covariates, list):
                covariates = []

            if target and exposure:
                name = f"Association: {target} ~ {exposure}"
                steps = self._design_association(target, exposure, covariates, metadata)

        return {
            "name": name,
            "goal": goal,
            "steps": steps,
            "required_visualization": "dashboard_v1"
        }

    def _design_from_title_and_metadata(self, dataset_title: str, meta: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        title_l = str(dataset_title or "").strip().lower()
        topic = str(variables.get("topic") or variables.get("hypothesis") or "углеводный обмен").strip().lower()

        cols_meta = meta if isinstance(meta, dict) else {}
        cols = [str(c) for c in cols_meta.keys()]

        exposure_candidates = self._rank_columns(cols, cols_meta, self._carb_keywords(topic))
        outcome_candidates = self._rank_columns(cols, cols_meta, self._outcome_keywords(title_l), prefer_categorical=True)

        exposure = self._pick_exposure(exposure_candidates, cols_meta)
        if exposure:
            outcome_candidates = [c for c in outcome_candidates if str(c) != str(exposure)]
        outcomes = self._pick_outcomes(outcome_candidates, cols_meta)

        covariates = self._pick_covariates(cols, cols_meta, exclude={exposure, *outcomes})

        binary_categorical = [
            c
            for c in outcomes
            if self._kind(cols_meta.get(c) or {}) == "categorical"
            and self._unique_count(cols_meta.get(c) or {}) == 2
        ]
        numeric_outcomes = [c for c in outcomes if self._kind(cols_meta.get(c) or {}) == "numeric"]
        other_outcomes = [c for c in outcomes if c not in set(binary_categorical) and c not in set(numeric_outcomes)]

        primary_outcome = (
            binary_categorical[0]
            if binary_categorical
            else (numeric_outcomes[0] if numeric_outcomes else (other_outcomes[0] if other_outcomes else None))
        )

        steps: List[Dict[str, Any]] = []
        name_parts: List[str] = []
        if primary_outcome:
            name_parts.append(str(primary_outcome))
        if exposure:
            name_parts.append(str(exposure))
        name = "Влияние факторов на исходы госпитализации"
        if name_parts:
            name = f"Влияние {name_parts[-1]} на {name_parts[0]}"

        if exposure and primary_outcome:
            steps.append(
                {
                    "id": "primary_compare",
                    "type": "compare",
                    "target": primary_outcome,
                    "group": exposure,
                    "method": {"id": "auto"},
                }
            )

            outcome_kind = self._kind(cols_meta.get(primary_outcome) or {})
            outcome_unique = self._unique_count(cols_meta.get(primary_outcome) or {})
            allow_regression = (outcome_kind == "numeric") or (outcome_kind == "categorical" and outcome_unique == 2)
            if allow_regression:
                kind = "logistic" if (outcome_kind == "categorical" and outcome_unique == 2) else "linear"
                predictors = [exposure] + [c for c in covariates if c and c != exposure]
                predictors = predictors[:15]
                steps.append(
                    {
                        "id": "adjusted_model",
                        "type": "regression",
                        "target": primary_outcome,
                        "predictors": predictors,
                        "kind": kind,
                    }
                )

        secondary = [o for o in outcomes if o and o != primary_outcome and o != exposure]
        for i, out in enumerate(secondary[:2], start=1):
            if exposure and out:
                steps.append(
                    {
                        "id": f"secondary_compare_{i}",
                        "type": "compare",
                        "target": out,
                        "group": exposure,
                        "method": {"id": "auto"},
                    }
                )

        numeric_for_corr = [
            c
            for c in [exposure, *outcomes]
            if c and self._kind(cols_meta.get(c) or {}) == "numeric"
        ]
        numeric_for_corr = list(dict.fromkeys(numeric_for_corr))
        if len(numeric_for_corr) >= 3:
            steps.append(
                {
                    "id": "corr_map",
                    "type": "clustered_correlation",
                    "variables": numeric_for_corr[:18],
                    "method": "spearman",
                    "show_p_values": True,
                }
            )

        if not steps:
            fallbacks = self._rank_columns(cols, cols_meta, ["исход", "outcome", "летал", "death"], prefer_categorical=True)
            group_fallback = self._pick_group_like_column(cols, cols_meta)
            target_fallback = fallbacks[0] if fallbacks else (cols[0] if cols else None)
            if target_fallback and group_fallback:
                steps = self._design_static_comparison(target_fallback, group_fallback, cols_meta)
                name = f"Comparison of {target_fallback} by {group_fallback}"

        return {"name": name, "goal": "association", "steps": steps}

    def _design_association(self, target: str, exposure: str, covariates: List[str], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        steps.append(
            {
                "id": "primary_compare",
                "type": "compare",
                "target": target,
                "group": exposure,
                "method": {"id": "auto"},
            }
        )

        kind = "linear"
        target_kind = self._kind(meta.get(target) or {})
        target_unique = self._unique_count(meta.get(target) or {})
        if target_kind == "categorical" and target_unique == 2:
            kind = "logistic"

        predictors = [exposure] + [c for c in covariates if c and c != exposure]
        predictors = predictors[:15]
        steps.append(
            {
                "id": "adjusted_model",
                "type": "regression",
                "target": target,
                "predictors": predictors,
                "kind": kind,
            }
        )
        return steps

    def _rank_columns(
        self,
        cols: List[str],
        cols_meta: Dict[str, Any],
        keywords: List[str],
        *,
        prefer_categorical: bool = False,
    ) -> List[str]:
        scored: List[Tuple[float, str]] = []
        keys = [str(k).lower() for k in keywords if str(k).strip()]
        for col in cols:
            name = str(col)
            name_l = name.lower()
            score = 0.0
            for k in keys:
                if k and k in name_l:
                    score += 1.0
            if score <= 0:
                continue
            if prefer_categorical and self._kind(cols_meta.get(name) or {}) == "categorical":
                score += 0.25
            u = self._unique_count(cols_meta.get(name) or {})
            if prefer_categorical and 2 <= u <= 12:
                score += 0.25
            scored.append((score, name))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [name for _, name in scored]

    def _pick_exposure(self, candidates: List[str], cols_meta: Dict[str, Any]) -> Optional[str]:
        for c in candidates[:20]:
            m = cols_meta.get(c) or {}
            kind = self._kind(m)
            u = self._unique_count(m)
            if kind == "categorical" and 2 <= u <= 12:
                return c
        for c in candidates[:20]:
            m = cols_meta.get(c) or {}
            if self._kind(m) == "numeric":
                return c
        return candidates[0] if candidates else None

    def _pick_outcomes(self, candidates: List[str], cols_meta: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        shortlist = candidates[:25]

        for c in shortlist:
            m = cols_meta.get(c) or {}
            if self._kind(m) != "categorical":
                continue
            if self._unique_count(m) == 2:
                out.append(c)

        for c in shortlist:
            if c in out:
                continue
            m = cols_meta.get(c) or {}
            if self._kind(m) != "categorical":
                continue
            u = self._unique_count(m)
            if 3 <= u <= 12:
                out.append(c)

        for c in shortlist:
            if c in out:
                continue
            if self._kind(cols_meta.get(c) or {}) == "numeric":
                out.append(c)
        return out[:6]

    def _pick_covariates(self, cols: List[str], cols_meta: Dict[str, Any], *, exclude: set) -> List[str]:
        exclude_n = {str(x) for x in exclude if x}
        cov_kw = self._covariate_keywords()
        ranked = self._rank_columns(cols, cols_meta, cov_kw)
        picked: List[str] = []

        for c in ranked:
            if c in exclude_n:
                continue
            if self._is_safe_covariate(c, cols_meta):
                picked.append(c)
            if len(picked) >= 10:
                break

        if len(picked) < 10:
            for c in cols:
                if c in exclude_n or c in picked:
                    continue
                if self._is_safe_covariate(c, cols_meta):
                    picked.append(c)
                if len(picked) >= 10:
                    break

        return picked

    def _is_safe_covariate(self, col: str, cols_meta: Dict[str, Any]) -> bool:
        m = cols_meta.get(col) or {}
        kind = self._kind(m)
        u = self._unique_count(m)
        if kind == "numeric":
            return True
        if kind == "categorical" and 2 <= u <= 15:
            return True
        return False

    def _pick_group_like_column(self, cols: List[str], cols_meta: Dict[str, Any]) -> Optional[str]:
        for col in cols:
            name_l = str(col).lower()
            if any(k in name_l for k in ["group", "группа", "arm", "cohort", "treatment", "рандом"]):
                u = self._unique_count(cols_meta.get(col) or {})
                if 2 <= u <= 20:
                    return str(col)
        for col in cols:
            u = self._unique_count(cols_meta.get(col) or {})
            if 2 <= u <= 12 and self._kind(cols_meta.get(col) or {}) == "categorical":
                return str(col)
        return None

    def _kind(self, meta: Dict[str, Any]) -> str:
        t = str((meta or {}).get("type") or "").lower()
        if any(x in t for x in ["int", "float", "double", "numeric", "number"]):
            return "numeric"
        if "bool" in t:
            return "categorical"
        if any(x in t for x in ["category", "object", "string"]):
            return "categorical"
        if "datetime" in t:
            return "datetime"
        return "categorical"

    def _unique_count(self, meta: Dict[str, Any]) -> int:
        v = (meta or {}).get("unique_count")
        try:
            if v is None:
                return 0
            return int(v)
        except Exception:
            return 0

    def _carb_keywords(self, topic: str) -> List[str]:
        base = [
            "глюк",
            "glucose",
            "hba1c",
            "a1c",
            "гликир",
            "диаб",
            "diabet",
            "сахар",
            "insulin",
            "инсулин",
            "keton",
            "кетон",
        ]
        if "углев" in topic or "carb" in topic:
            return base + ["carb", "углев", "углевод"]
        return base

    def _outcome_keywords(self, title_l: str) -> List[str]:
        base = [
            "исход",
            "outcome",
            "летал",
            "death",
            "смерт",
            "умер",
            "выпис",
            "discharge",
            "icu",
            "реаним",
            "ивл",
            "vent",
            "тяжест",
            "severity",
            "длитель",
            "length",
            "los",
            "stay",
            "госпитал",
        ]
        if "covid" in title_l or "ковид" in title_l:
            return base + ["sat", "spo2", "кт", "pcr", "d-dimer", "д-димер", "ddimer"]
        return base

    def _covariate_keywords(self) -> List[str]:
        return [
            "возраст",
            "age",
            "пол",
            "sex",
            "gender",
            "bmi",
            "имт",
            "вес",
            "рост",
            "кур",
            "smok",
            "вакцин",
            "vacc",
            "гиперт",
            "htn",
            "давлен",
            "ожир",
            "asth",
            "астм",
            "copd",
            "хобл",
            "онкол",
            "cancer",
            "берем",
            "pregn",
            "креат",
            "creat",
            "сат",
            "spo2",
            "пульс",
            "pulse",
        ]

    def _design_static_comparison(self, target: str, group: str, meta: Dict) -> List[Dict]:
        """
        Logic for T-Test / ANOVA / Non-parametric equivalents.
        """
        steps = []
        
        # 1. Descriptive Stats (Table 1 equivalent)
        steps.append({
            "id": "desc_stats",
            "type": "descriptive_compare",
            "target": target,
            "group": group
        })
        
        # 2. Hypothesis Testing
        # Check normalization from metadata to suggest method
        target_meta = meta.get(target, {})
        is_normal = target_meta.get("normality", {}).get("is_normal", True) # Default to True if unknown
        
        # Note: We can force a method, or let engine.select_test decide dynamically.
        # "Methodological Brain" prefers to be explicit here if possible, but engine.py has good runtime logic.
        # Let's rely on engine.py's robust 'compare' dispatch for now, but generic 'compare' is enough.
        
        method_category = "parametric" if is_normal else "non_parametric"
        
        steps.append({
            "id": "hypothesis_test",
            "type": "compare",
            "target": target,
            "group": group,
            "assumptions_checked": ["normality", "homogeneity"],
            "method": {
                "id": "auto",
                "name": "Auto-Detect Test",
                "category": method_category,
                "params": {"target": target, "group": group}
            }
        })
        
        return steps

    def _design_dynamic_comparison(self, target: str, group: str, time_col: str, meta: Dict) -> List[Dict]:
        """
        Logic for Longitudinal Analysis (Repeated Measures).
        """
        steps = []
        
        # 1. Overall Trend (All Groups) - e.g. RM ANOVA or Friedmann
        steps.append({
            "id": "time_trend_overall",
            "type": "compare_dynamic", # New capability needed in Engine
            "target": target,
            "time": time_col,
            "group": group
        })
        
        # 2. Post-hoc: Compare groups at EACH timepoint
        # We generate a sub-step for the Engine to expand, or hardcode generic instruction
        steps.append({
             "id": "timepoint_comparison",
             "type": "batch_compare_by_factor", # "Loop over Time"
             "target": target,
             "group": group,
             "split_by": time_col
        })
        
        return steps

    def _design_correlation(self, target: str, predictor: str, meta: Dict) -> List[Dict]:
        return [{
            "id": "corr_analysis",
            "type": "correlation",
            "target": target,
            "group": predictor
        }]

    def list_templates(self, goal: Optional[str] = None) -> List[Dict[str, str]]:
        templates = [
            {
                "id": "compare_full",
                "goal": "compare_groups",
                "name": "Full comparison",
                "description": "Descriptives + hypothesis test (auto)",
            },
            {
                "id": "compare_quick",
                "goal": "compare_groups",
                "name": "Quick comparison",
                "description": "Only hypothesis test (auto)",
            },
            {
                "id": "correlation_auto",
                "goal": "relationship",
                "name": "Correlation (auto)",
                "description": "Auto-select Pearson/Spearman",
            },
            {
                "id": "covid_glucose_outcomes_auto",
                "goal": "association",
                "name": "COVID + углеводный обмен → исходы",
                "description": "Авто-выбор экспозиции/исходов/ковариат по колонкам",
            },
        ]

        if goal:
            return [t for t in templates if t.get("goal") == goal]
        return templates
