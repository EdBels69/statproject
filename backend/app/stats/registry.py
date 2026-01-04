from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

from app.schemas.analysis import StatMethod
from app.stats.engine import run_analysis


@dataclass
class IODescriptor:
    name: str
    kind: str  # e.g., target, group, predictor
    dtype: Optional[str] = None
    description: Optional[str] = None


@dataclass
class MethodDescriptor:
    method: StatMethod
    inputs: List[IODescriptor]
    outputs: Dict[str, str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    packages: List[str] = field(default_factory=list)
    executor: Callable[..., Dict[str, Any]] = lambda *args, **kwargs: {}


class StatsRegistry:
    def __init__(self) -> None:
        self._methods: Dict[str, MethodDescriptor] = {}

    def register(self, descriptor: MethodDescriptor) -> None:
        self._methods[descriptor.method.id] = descriptor

    def list_methods(self) -> List[MethodDescriptor]:
        return list(self._methods.values())

    def get(self, method_id: str) -> Optional[MethodDescriptor]:
        return self._methods.get(method_id)

    def get_method(self, method_id: str) -> Optional[StatMethod]:
        descriptor = self.get(method_id)
        return descriptor.method if descriptor else None

    def run(self, method_id: str, df, **kwargs) -> Dict[str, Any]:
        descriptor = self.get(method_id)
        if not descriptor:
            raise KeyError(f"Method {method_id} not registered")
        return descriptor.executor(df=df, **kwargs)


stats_registry = StatsRegistry()
METHODS: Dict[str, StatMethod] = {}


def _register(method: StatMethod, *, inputs: List[IODescriptor], outputs: Dict[str, str], parameters: Dict[str, Any], packages: List[str], executor: Callable[..., Dict[str, Any]]) -> None:
    METHODS[method.id] = method
    stats_registry.register(
        MethodDescriptor(
            method=method,
            inputs=inputs,
            outputs=outputs,
            parameters=parameters,
            packages=packages,
            executor=executor,
        )
    )


def _default_group_executor(method_id: str, *, paired: bool = False) -> Callable[..., Dict[str, Any]]:
    def _executor(df, *, target: str, group: str, is_paired: bool = paired, **kwargs):
        return run_analysis(df, method_id, target, group, is_paired=is_paired, **kwargs)
    return _executor


def _default_two_var_executor(method_id: str) -> Callable[..., Dict[str, Any]]:
    def _executor(df, *, x: str, y: str, **kwargs):
        return run_analysis(df, method_id, x, y, **kwargs)
    return _executor


def _default_regression_executor(method_id: str) -> Callable[..., Dict[str, Any]]:
    def _executor(df, *, target: str, predictors: List[str]):
        return run_analysis(df, method_id, target, predictors[0] if predictors else None, predictors=predictors)
    return _executor


def _register_defaults() -> None:
    _register(
        StatMethod(
            id="t_test_ind",
            name="Student's t-test (Independent)",
            description="Compares means of two independent groups. Assumes normal distribution.",
            type="parametric",
            min_groups=2,
            max_groups=2
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric", description="Continuous outcome"),
            IODescriptor(name="group", kind="group", dtype="categorical", description="Grouping variable")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={"is_paired": False},
        packages=["scipy"],
        executor=_default_group_executor("t_test_ind")
    )
    _register(
        StatMethod(
            id="mann_whitney",
            name="Mann-Whitney U Test",
            description="Compares distributions of two independent groups. Non-parametric (does not assume normality).",
            type="non-parametric",
            min_groups=2,
            max_groups=2
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={},
        packages=["scipy"],
        executor=_default_group_executor("mann_whitney")
    )
    _register(
        StatMethod(
            id="t_test_rel",
            name="Paired t-test",
            description="Compares means of two dependent (paired) groups. Assumes normal distribution of differences.",
            type="parametric",
            min_groups=2,
            max_groups=2
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="group", kind="pair", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={"is_paired": True},
        packages=["scipy"],
        executor=_default_group_executor("t_test_rel", paired=True)
    )
    _register(
        StatMethod(
            id="wilcoxon",
            name="Wilcoxon Signed-Rank Test",
            description="Compares two dependent (paired) groups. Non-parametric.",
            type="non-parametric",
            min_groups=2,
            max_groups=2
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="group", kind="pair", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={"is_paired": True},
        packages=["scipy"],
        executor=_default_group_executor("wilcoxon", paired=True)
    )
    _register(
        StatMethod(
            id="chi_square",
            name="Chi-Square Test of Independence",
            description="Tests association between two categorical variables.",
            type="categorical",
            min_groups=2,
            max_groups=100
        ),
        inputs=[
            IODescriptor(name="x", kind="categorical", dtype="categorical"),
            IODescriptor(name="y", kind="categorical", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float"},
        parameters={},
        packages=["scipy"],
        executor=_default_two_var_executor("chi_square")
    )
    _register(
        StatMethod(
            id="pearson",
            name="Pearson Correlation",
            description="Measures linear correlation between two numeric variables. Assumes normality.",
            type="correlation",
            min_groups=0,
            max_groups=0
        ),
        inputs=[
            IODescriptor(name="x", kind="numeric", dtype="numeric"),
            IODescriptor(name="y", kind="numeric", dtype="numeric")
        ],
        outputs={"p_value": "float", "stat_value": "float", "regression": "dict"},
        parameters={},
        packages=["scipy"],
        executor=_default_two_var_executor("pearson")
    )
    _register(
        StatMethod(
            id="spearman",
            name="Spearman Correlation",
            description="Measures monotonic correlation (rank-based). Non-parametric.",
            type="correlation",
            min_groups=0,
            max_groups=0
        ),
        inputs=[
            IODescriptor(name="x", kind="numeric", dtype="numeric"),
            IODescriptor(name="y", kind="numeric", dtype="numeric")
        ],
        outputs={"p_value": "float", "stat_value": "float", "regression": "dict"},
        parameters={},
        packages=["scipy"],
        executor=_default_two_var_executor("spearman")
    )
    _register(
        StatMethod(
            id="anova",
            name="One-Way ANOVA",
            description="Compares means of three or more independent groups. Assumes normal distribution and homogeneity of variances.",
            type="parametric",
            min_groups=3,
            max_groups=100
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={},
        packages=["scipy"],
        executor=_default_group_executor("anova")
    )
    _register(
        StatMethod(
            id="kruskal",
            name="Kruskal-Wallis H-test",
            description="Non-parametric alternative to ANOVA. Compares distributions of three or more independent groups.",
            type="non-parametric",
            min_groups=3,
            max_groups=100
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={},
        packages=["scipy"],
        executor=_default_group_executor("kruskal")
    )
    _register(
        StatMethod(
            id="survival_km",
            name="Kaplan-Meier Survival Analysis",
            description="Estimates survival probability over time. Includes Log-Rank test to compare groups.",
            type="non-parametric",
            min_groups=2,
            max_groups=20
        ),
        inputs=[
            IODescriptor(name="duration", kind="numeric", dtype="numeric"),
            IODescriptor(name="event", kind="categorical", dtype="categorical"),
            IODescriptor(name="group", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float", "plot_data": "list"},
        parameters={},
        packages=["lifelines"],
        executor=lambda df, *, duration, event, group=None: run_analysis(df, "survival_km", duration, event, group_col=group)
    )
    _register(
        StatMethod(
            id="linear_regression",
            name="Linear Regression",
            description="Predicts a continuous outcome based on one or more predictors.",
            type="parametric",
            min_groups=1,
            max_groups=20
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="predictors", kind="predictor", dtype="mixed", description="Predictor columns")
        ],
        outputs={"p_value": "float", "stat_value": "float", "coefficients": "list"},
        parameters={},
        packages=["statsmodels"],
        executor=_default_regression_executor("linear_regression")
    )
    _register(
        StatMethod(
            id="logistic_regression",
            name="Logistic Regression",
            description="Predicts a binary outcome (Yes/No) based on one or more predictors.",
            type="parametric",
            min_groups=1,
            max_groups=20
        ),
        inputs=[
            IODescriptor(name="target", kind="categorical", dtype="categorical"),
            IODescriptor(name="predictors", kind="predictor", dtype="mixed")
        ],
        outputs={"p_value": "float", "stat_value": "float", "coefficients": "list"},
        parameters={},
        packages=["statsmodels"],
        executor=_default_regression_executor("logistic_regression")
    )
    _register(
        StatMethod(
            id="fisher",
            name="Fisher's Exact Test",
            description="Tests association between two categorical variables (better for small samples).",
            type="categorical",
            min_groups=2,
            max_groups=2
        ),
        inputs=[
            IODescriptor(name="x", kind="categorical", dtype="categorical"),
            IODescriptor(name="y", kind="categorical", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float"},
        parameters={},
        packages=["scipy"],
        executor=lambda *args, **kwargs: {"error": "Not implemented"}
    )
    _register(
        StatMethod(
            id="rm_anova",
            name="Repeated Measures ANOVA",
            description="Compares means of the same subjects across three or more time points/conditions.",
            type="parametric",
            min_groups=3,
            max_groups=100
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="subject", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float"},
        parameters={},
        packages=["statsmodels"],
        executor=lambda *args, **kwargs: {"error": "Not implemented"}
    )
    _register(
        StatMethod(
            id="mixed_model",
            name="Linear Mixed Models (LMM)",
            description="Advanced model for nested/clustered data and unbalanced designs. Essential for complex clinical trials.",
            type="parametric",
            min_groups=2,
            max_groups=100
        ),
        inputs=[
            IODescriptor(name="target", kind="numeric", dtype="numeric"),
            IODescriptor(name="grouping_factor", kind="group", dtype="categorical")
        ],
        outputs={"p_value": "float", "stat_value": "float"},
        parameters={},
        packages=["statsmodels"],
        executor=lambda *args, **kwargs: {"error": "Not implemented"}
    )


_register_defaults()


def get_method(method_id: str) -> StatMethod:
    return METHODS.get(method_id)


def run_registered_method(method_id: str, df, **kwargs) -> Dict[str, Any]:
    return stats_registry.run(method_id, df, **kwargs)
