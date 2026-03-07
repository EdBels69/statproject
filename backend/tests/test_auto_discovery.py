import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.copilot.clinical_utils import discover_longitudinal_groups


def test_discover_longitudinal_groups_finds_expected_patterns():
    df = pd.DataFrame(
        {
            "group": ["A", "B", "A"],
            "HGB_V1": [10.1, 11.2, 9.8],
            "HGB_V2": [10.9, 11.8, 10.2],
            "PLT_V1": [230, 240, 250],
            "PLT_V3": [220, 235, 245],
            "comment": ["x", "y", "z"],
        }
    )

    groups = discover_longitudinal_groups(df, ["V1", "V2", "V3"])

    assert "HGB" in groups
    assert groups["HGB"]["V1"] == "HGB_V1"
    assert groups["HGB"]["V2"] == "HGB_V2"

    assert "PLT" in groups
    assert set(groups["PLT"].keys()) == {"V1", "V3"}


def test_discover_longitudinal_groups_returns_empty_on_none_visits():
    df = pd.DataFrame({"value": [1, 2, 3]})
    assert discover_longitudinal_groups(df, None) == {}
