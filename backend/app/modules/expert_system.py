from typing import List, Optional
from pydantic import BaseModel

class WizardRequest(BaseModel):
    goal: str  # "compare_groups", "relationship", "prediction", "survival"
    structure: str  # "independent", "paired", "longitudinal"
    data_type: str  # "numeric", "categorical", "rank"
    groups: str  # "2", ">2"
    normal_distribution: bool = True # Default assumption if unknown

class WizardRecommendation(BaseModel):
    method_id: str
    name: str
    description: str
    assumptions: List[str]

def recommend_method(req: WizardRequest) -> WizardRecommendation:
    # 1. Compare Groups
    if req.goal == "compare_groups":
        if req.structure == "independent":
            if req.groups == "2":
                if req.data_type == "numeric":
                    if req.normal_distribution:
                        return WizardRecommendation(
                            method_id="ttest_ind",
                            name="Student's T-Test",
                            description="Compares means of two independent groups.",
                            assumptions=["Normal distribution", "Homogeneity of variances"]
                        )
                    else:
                        return WizardRecommendation(
                            method_id="mannwhitney",
                            name="Mann-Whitney U Test",
                            description="Compares distributions of two independent groups (non-parametric).",
                            assumptions=["Independent samples"]
                        )
                elif req.data_type == "categorical":
                    return WizardRecommendation(
                        method_id="chi2",
                        name="Chi-Square Test",
                        description="Tests independence between two categorical variables.",
                        assumptions=["Expected cell counts > 5"]
                    )
            elif req.groups == ">2":
                if req.data_type == "numeric":
                    if req.normal_distribution:
                        return WizardRecommendation(
                            method_id="anova",
                            name="One-Way ANOVA",
                            description="Compares means of three or more independent groups.",
                            assumptions=["Normal distribution", "Homogeneity of variances"]
                        )
                    else:
                        return WizardRecommendation(
                            method_id="kruskal",
                            name="Kruskal-Wallis Test",
                            description="Compares distributions of three or more independent groups (non-parametric).",
                            assumptions=["Independent samples"]
                        )

        elif req.structure == "paired":
            if req.groups == "2":
                 if req.data_type == "numeric":
                    if req.normal_distribution:
                        return WizardRecommendation(
                            method_id="ttest_rel",
                            name="Paired T-Test",
                            description="Compares means of two related/paired groups.",
                            assumptions=["Differences are normally distributed"]
                        )
                    else:
                        return WizardRecommendation(
                            method_id="wilcoxon",
                            name="Wilcoxon Signed-Rank Test",
                            description="Compares distributions of two related groups (non-parametric).",
                            assumptions=["Symmetric distribution of differences"]
                        )

    # 2. Relationship / Correlation
    elif req.goal == "relationship":
        if req.data_type == "numeric":
             if req.normal_distribution:
                return WizardRecommendation(
                    method_id="pearson",
                    name="Pearson Correlation",
                    description="Measures linear relationship between two continuous variables.",
                    assumptions=["Normal distribution", "Linearity"]
                )
             else:
                return WizardRecommendation(
                    method_id="spearman",
                    name="Spearman Correlation",
                    description="Measures monotonic relationship between two ranked variables.",
                    assumptions=["Monotonicity"]
                )

    # Fallback
    return WizardRecommendation(
        method_id="consult_statistician",
        name="Consult a Statistician",
        description="Complex design detected. Please consult a statistician or check the 'Advanced' section.",
        assumptions=[]
    )
