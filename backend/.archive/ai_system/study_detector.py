import re
import pandas as pd
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class StudyShape(BaseModel):
    group_col: Optional[str] = None
    subject_col: Optional[str] = None
    time_col: Optional[str] = None # Explicit time column if exists
    visit_map: Dict[str, str] = {} # canonical "V1" -> "Weeks 0" mapping if derived from cols
    endpoint_families: List[Dict[str, Any]] = [] # Families of outcomes across time
    structure: str = "generic" # "longitudinal", "cross_sectional", "pre_post"

class StudyDetectorIsolated:
    """
    Robustly identifies the study design structure from a cleaned DataFrame.
    """

    def detect(self, df: pd.DataFrame) -> StudyShape:
        columns = [str(c) for c in df.columns]
        
        # 1. Find Group
        group_col = self._detect_group_column(df, columns)
        
        # 2. Find Subject ID
        subject_col = self._detect_id_column(df, columns)
        
        # 3. Find Time/Visits structure based on columns pattern (Wide Format)
        # e.g. "UPDRS V1", "UPDRS V2"
        endpoint_families, visit_map = self._detect_wide_format_families(columns)
        
        # 4. Determine Structure
        structure = "cross_sectional"
        if endpoint_families or visit_map:
            structure = "longitudinal"
        
        # 5. Check for explicit Time column (Long Format) - simpler check
        time_col = None
        if not endpoint_families:
             time_col = self._detect_time_column(df, columns)
             if time_col and subject_col and df.groupby([subject_col, time_col]).size().max() == 1:
                 structure = "longitudinal_long"

        return StudyShape(
            group_col=group_col,
            subject_col=subject_col,
            time_col=time_col,
            visit_map=visit_map,
            endpoint_families=endpoint_families,
            structure=structure
        )

    def scan_variables(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Scans all columns to determine usability and type (Numeric vs Categorical).
        """
        manifest = []
        for col in df.columns:
            s = df[col]
            unique_count = s.nunique()
            missing_count = int(s.isna().sum())
            total = len(df)
            dtype = str(s.dtype)
            
            # Type Inference
            inferred_type = "unknown"
            
            if pd.api.types.is_numeric_dtype(s):
                # Low unique numeric might be categorical (e.g. 0/1, 1-5 scale)
                if unique_count <= 10 and unique_count < total * 0.1:
                    inferred_type = "categorical" # Ordinal/Nominal encoded as int
                else:
                    inferred_type = "numeric"
            else:
                # Text/Object
                if unique_count <= 30 and unique_count < total * 0.8:
                     inferred_type = "categorical"
                elif unique_count == total:
                     inferred_type = "id"
                else:
                     inferred_type = "text"

            manifest.append({
                "name": str(col),
                "inferred_type": inferred_type,
                "unique": unique_count,
                "missing": missing_count,
                "missing_pct": round((missing_count / total) * 100, 1) if total > 0 else 0,
                "example": str(s.dropna().iloc[0]) if not s.dropna().empty else ""
            })
        
        return manifest

    def _detect_group_column(self, df: pd.DataFrame, columns: List[str]) -> Optional[str]:
        candidates = []
        for col in columns:
            if df[col].nunique() < 2 or df[col].nunique() > 8:
                continue
                
            score = 0
            name_lower = col.lower()
            
            # Strong Keywords (exact match)
            strong_keywords = [
                "group", "arm", "treatment", "группа", "терапия",
                "исход", "outcome", "status", "статус", "диагноз"
            ]
            if name_lower in strong_keywords:
                score += 10
            # Partial match for strong keywords
            elif any(k in name_lower for k in strong_keywords):
                score += 8
                
            # Weak Keywords
            elif any(k in name_lower for k in ["grp", "cohort", "категория", "тип", "type", "class", "класс"]):
                score += 5
                
            # Content check: binary outcomes, control/treatment patterns
            try:
                values = df[col].dropna().astype(str).str.lower().unique()
                # Control/Placebo patterns
                if any(v in ["control", "placebo", "контроль", "плацебо"] for v in values):
                    score += 5
                # Binary outcome patterns (common in clinical trials)
                if any(v in ["да", "нет", "yes", "no", "0", "1", "выжил", "умер", "живой", "мертвый"] for v in values):
                    score += 3
            except:
                pass
            
            if score > 0:
                candidates.append((score, col))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1] if candidates else None

    def _detect_id_column(self, df: pd.DataFrame, columns: List[str]) -> Optional[str]:
        for col in columns:
            name_lower = col.lower()
            if any(k in name_lower for k in ["id", "subject", "patient", "participant", "№", "номер"]):
                # High unique check
                if df[col].nunique() > len(df) * 0.5:
                    return col
        return None

    def _detect_wide_format_families(self, columns: List[str]) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Enhanced detection with 3 pattern types:
        1. Visit/Time numbers: V1, M0, T1,  М0 (Russian month)
        2. Timepoints: Pre, Post, Baseline, Followup
        3. Pure number suffix: Score_0, Score_3
        """
        # Pattern 1: V/T/W/M + number
        pattern_visit_number = re.compile(
            r"[\s_\-]+(V|T|W|M|В|Т|М|Визит|Visit|Time|Week|Month|Месяц|Неделя|Point|Этап)\s?(\d+)($|[\s_\-])",
            re.IGNORECASE
        )
        
        # Pattern 2: Pre/Post/Baseline/Followup
        pattern_timepoint = re.compile(
            r"(Pre|Post|Baseline|Followup|До|После|Исходно|Final|End|Start|Begin)($|[\s_\-])",
            re.IGNORECASE
        )
        
        # Pattern 3: Pure numbers at end (Score_0, Score_3, Score_6)
        pattern_number_suffix = re.compile(r"[_\s](\d+)$")
        
        base_map = {}  # base_name -> {visit_label: col_name}
        
        for col in columns:
            # Skip ID columns
            if col.lower() in ["id", "subject_id", "patient_id"]:
                continue
            
            suffix = None
            base = None
            
            # Try Pattern 1: V1, M0, М1 (Russian month), etc.
            m1 = pattern_visit_number.search(col)
            if m1:
                prefix = m1.group(1).upper()
                # Normalize Russian letters
                if prefix == 'М':  # Russian M
                    prefix = 'M'
                elif prefix == 'В':  # Russian V
                    prefix = 'V'
                elif prefix == 'Т':  # Russian T
                    prefix = 'T'
                elif prefix in ['VISIT', 'ВИЗИТ']:
                    prefix = 'V'
                elif prefix in ['TIME']:
                    prefix = 'T'
                elif prefix in ['WEEK', 'НЕДЕЛЯ']:
                    prefix = 'W'
                elif prefix in ['MONTH', 'МЕСЯЦ']:
                    prefix = 'M'
                elif prefix in ['POINT', 'ЭТАП']:
                    prefix = 'P'
                
                number = m1.group(2)
                suffix = f"{prefix}{number}"
                base = col[:m1.start()].strip(" _-")
            
            # Try Pattern 2: Pre/Post/Baseline
            elif pattern_timepoint.search(col):
                m2 = pattern_timepoint.search(col)
                timepoint = m2.group(1).capitalize()
                # Normalize Russian
                if timepoint in ['До', 'Исходно', 'Start', 'Begin']:
                    timepoint = 'Pre'
                elif timepoint in ['После', 'Final', 'End']:
                    timepoint = 'Post'
                
                suffix = timepoint
                base = col[:m2.start()].strip(" _-")
            
            # Try Pattern 3: Pure number suffix
            elif pattern_number_suffix.search(col):
                m3 = pattern_number_suffix.search(col)
                number = m3.group(1)
                # Only if number is <= 2 digits (likely timepoint, not ID)
                if len(number) <= 2:
                    suffix = f"T{number}"
                    base = col[:m3.start()]
            
            if suffix and base and len(base) >= 2:
                base = base.strip(" _-")
                base_map.setdefault(base, {})[suffix] = col
        
        # Build families (at least 2 timepoints)
        families = []
        all_visits = set()
        
        for base_name, visits in base_map.items():
            if len(visits) >= 2:
                families.append({
                    "family_name": base_name,
                    "columns": visits
                })
                all_visits.update(visits.keys())
        
        # Sort visits intelligently
        def visit_sort_key(v):
            # Extract number if present
            match = re.search(r'(\d+)', v)
            if match:
                return (0, int(match.group(1)))
            # Pre/Baseline = early, Post/Final = late
            if v in ['Pre', 'Baseline']:
                return (0, -1)
            if v in ['Post', 'Final']:
                return (0, 999)
            return (1, 0)
        
        visit_list = sorted(list(all_visits), key=visit_sort_key)
        visit_map = {v: v for v in visit_list}
        
        return families, visit_map

    def _detect_time_column(self, df: pd.DataFrame, columns: List[str]) -> Optional[str]:
        for col in columns:
             if col.lower() in ["visit", "time", "timepoint", "визит", "неделя", "месяц"]:
                 if df[col].nunique() < 20: 
                     return col
        return None
