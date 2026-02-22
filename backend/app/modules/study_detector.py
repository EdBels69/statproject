import re
from typing import Dict, Any, Tuple, List, Optional

import pandas as pd


class StudyDetector:
    def detect(self, df: pd.DataFrame) -> Dict[str, Any]:
        columns = [str(c) for c in df.columns]
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []
        datetime_cols: List[str] = []

        for col in columns:
            s = df[col]
            if pd.api.types.is_datetime64_any_dtype(s.dtype):
                datetime_cols.append(col)
            elif pd.api.types.is_numeric_dtype(s.dtype):
                numeric_cols.append(col)
            else:
                categorical_cols.append(col)

        group_candidates = []
        for col in columns:
            s = df[col]
            n, unique, ratio = self._column_profile(s)
            if n == 0:
                continue
            score = self._score_group_candidate(col, unique, ratio)
            if score > 0:
                group_candidates.append(
                    {
                        "column": col,
                        "score": score,
                        "unique": unique,
                        "ratio": ratio,
                    }
                )

        group_candidates.sort(key=lambda x: (-x["score"], x["unique"], x["column"]))
        group_column = group_candidates[0]["column"] if group_candidates else None

        id_column = self._detect_id_column(df)

        timepoints: List[Dict[str, Any]] = []
        endpoints: Dict[str, Dict[str, Any]] = {}
        for col in columns:
            base, label = self._extract_timepoint(col)
            if not label:
                continue
            timepoints.append({"column": col, "label": label, "endpoint": base})
            if base not in endpoints:
                endpoints[base] = {"endpoint": base, "columns": [], "timepoints": []}
            endpoints[base]["columns"].append(col)
            endpoints[base]["timepoints"].append(label)

        endpoint_groups = list(endpoints.values())
        for item in endpoint_groups:
            item["timepoints"] = self._sort_timepoints(item["timepoints"])
            item["columns"] = self._sort_endpoint_columns(item["columns"], item["timepoints"])

        recommendations = self._build_recommendations(
            df,
            group_column,
            numeric_cols,
            categorical_cols,
            endpoint_groups,
        )

        return {
            "group_column": group_column,
            "group_candidates": group_candidates,
            "id_column": id_column,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "datetime_columns": datetime_cols,
            "timepoints": timepoints,
            "endpoint_groups": endpoint_groups,
            "recommendations": recommendations,
        }

    def _column_profile(self, s: pd.Series) -> Tuple[int, int, float]:
        non_null = s.dropna()
        n = int(len(non_null))
        if n == 0:
            return 0, 0, 0.0
        unique = int(non_null.nunique(dropna=True))
        ratio = float(unique) / float(max(1, n))
        return n, unique, ratio

    def _score_group_candidate(self, name: str, unique: int, ratio: float) -> int:
        if unique < 2:
            return 0
        score = 0
        name_l = str(name).strip().lower()
        keywords = [
            "группа",
            "групп",
            "group",
            "treatment",
            "arm",
            "cohort",
            "категор",
            "category",
            "класс",
            "тип",
            "рандом",
            "random",
            "intervention",
        ]
        if any(k in name_l for k in keywords):
            score += 3
        if unique <= 6:
            score += 2
        elif unique <= 15:
            score += 1
        if ratio <= 0.2:
            score += 1
        return score

    def _detect_id_column(self, df: pd.DataFrame) -> Optional[str]:
        for col in df.columns:
            name_l = str(col).strip().lower()
            if not any(
                k in name_l
                for k in ["id", "subject", "patient", "participant", "испытуемый", "пациент", "участник", "код", "номер"]
            ):
                continue
            n, unique, ratio = self._column_profile(df[col])
            if n > 0 and ratio >= 0.9:
                return str(col)
        return None

    def _extract_timepoint(self, name: str) -> Tuple[str, Optional[str]]:
        text = str(name)
        pattern = re.compile(
            r"(?i)(?:^|[\s_\-])(?:(v|visit|визит|time|t|week|wk|month|mo|day|d|год|year|yr|неделя|месяц))\s*[_\-]?(\d+)(?:$|[\s_\-])"
        )
        m = pattern.search(text)
        if not m:
            return text.strip(), None
        prefix = m.group(1)
        num = m.group(2)
        label = f"{prefix.upper()}{num}"
        base = (text[: m.start()] + " " + text[m.end() :]).strip()
        base = re.sub(r"[\s_\-]+", " ", base).strip()
        if not base:
            base = text.strip()
        return base, label

    def _sort_timepoints(self, labels: List[str]) -> List[str]:
        def key_fn(x: str) -> Tuple[int, str]:
            m = re.search(r"(\d+)$", x)
            if not m:
                return (10**9, x)
            return (int(m.group(1)), x)

        unique = list(dict.fromkeys(labels))
        unique.sort(key=key_fn)
        return unique

    def _sort_endpoint_columns(self, columns: List[str], labels: List[str]) -> List[str]:
        label_set = {str(l) for l in labels}

        def score(col: str) -> Tuple[int, str]:
            for idx, label in enumerate(labels):
                if label.lower() in str(col).lower():
                    return (idx, col)
            return (len(labels) + 1, col)

        return sorted(list(dict.fromkeys(columns)), key=score)

    def _build_recommendations(
        self,
        df: pd.DataFrame,
        group_col: Optional[str],
        numeric_cols: List[str],
        categorical_cols: List[str],
        endpoint_groups: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        if group_col and endpoint_groups:
            endpoint = endpoint_groups[0]
            recommendations.append(
                {
                    "method_id": "mixed_effects",
                    "target": endpoint.get("endpoint"),
                    "group": group_col,
                    "timepoints": endpoint.get("timepoints"),
                    "reason": "Есть повторные измерения и группирующая переменная",
                }
            )

        if group_col and numeric_cols:
            n, unique, _ = self._column_profile(df[group_col])
            target = numeric_cols[0]
            if n > 0 and unique == 2:
                recommendations.append(
                    {
                        "method_id": "t_test_ind",
                        "target": target,
                        "group": group_col,
                        "alternatives": ["mann_whitney"],
                        "reason": "Две группы для сравнения средних",
                    }
                )
            elif n > 0 and unique > 2:
                recommendations.append(
                    {
                        "method_id": "anova",
                        "target": target,
                        "group": group_col,
                        "alternatives": ["kruskal", "anova_welch"],
                        "reason": "Более двух групп для сравнения",
                    }
                )

        if not group_col and len(numeric_cols) >= 2:
            recommendations.append(
                {
                    "method_id": "pearson",
                    "target": numeric_cols[0],
                    "group": numeric_cols[1],
                    "alternatives": ["spearman"],
                    "reason": "Пара числовых переменных для корреляции",
                }
            )

        if len(categorical_cols) >= 2:
            recommendations.append(
                {
                    "method_id": "chi_square",
                    "target": categorical_cols[0],
                    "group": categorical_cols[1],
                    "alternatives": ["fisher"],
                    "reason": "Две категориальные переменные",
                }
            )

        return recommendations
