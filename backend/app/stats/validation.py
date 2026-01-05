from typing import Dict, Iterable, List, Union

import pandas as pd

from app.schemas.analysis import IODescriptor, StatMethod


def infer_dtype(series: pd.Series) -> str:
    """Map a pandas Series to an IODescriptor dtype."""
    non_null = series.dropna()
    if non_null.empty:
        return "any"

    if pd.api.types.is_bool_dtype(series):
        return "binary"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_numeric_dtype(series):
        # Treat low-cardinality numeric as binary (e.g., 0/1)
        return "binary" if non_null.nunique(dropna=True) <= 2 else "numeric"

    # Object/string-like -> categorical by default
    unique = non_null.nunique(dropna=True)
    if unique <= 2:
        return "binary"
    return "categorical"


def _matches(expected: str, actual: str) -> bool:
    if expected == "any":
        return True
    if expected == "numeric_or_categorical":
        return actual in {"numeric", "categorical", "binary"}
    if expected == "categorical":
        return actual in {"categorical", "binary"}
    return expected == actual


def _as_iterable(value: Union[str, Iterable[str]]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [v for v in value if v]


def validate_inputs(
    method: StatMethod,
    df: pd.DataFrame,
    mapping: Dict[str, Union[str, List[str]]],
) -> List[str]:
    """
    Validate incoming column mapping against method IODescriptors.
    Returns a list of human-readable errors.
    """
    errors: List[str] = []

    for descriptor in method.inputs:
        mapped_values = _as_iterable(mapping.get(descriptor.name))

        if descriptor.required and not mapped_values:
            errors.append(f"Input '{descriptor.name}' is required for {method.name}.")
            continue

        if not descriptor.multiple and len(mapped_values) > 1:
            errors.append(
                f"Input '{descriptor.name}' accepts a single column, "
                f"but {len(mapped_values)} were provided."
            )
            continue

        for col in mapped_values:
            if col not in df.columns:
                errors.append(
                    f"Column '{col}' mapped to '{descriptor.name}' was not found in the dataset."
                )
                continue

            actual_dtype = infer_dtype(df[col])
            if not _matches(descriptor.dtype, actual_dtype):
                errors.append(
                    f"Input '{descriptor.name}' expects {descriptor.dtype} data, "
                    f"but column '{col}' is {actual_dtype}."
                )

    return errors
