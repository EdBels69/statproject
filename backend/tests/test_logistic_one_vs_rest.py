import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.stats.engine import run_analysis


def test_logistic_one_vs_rest_runs():
    df = pd.DataFrame(
        {
            "outcome": ["A", "B", "C", "C", "A", "B", "C", "A"],
            "age": [30, 40, 50, 60, 35, 42, 55, 38],
        }
    )

    res = run_analysis(
        df,
        "logistic_regression",
        "outcome",
        "age",
        predictors=["age"],
        one_vs_rest=True,
        positive_label="C",
    )
    assert res.get("method") == "logistic_regression"
    assert res.get("coefficients")
