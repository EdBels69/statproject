import pandas as pd
import numpy as np

def detect_constant_columns(df):
    """
    Returns a list of columns that contain only 1 unique value.
    """
    constant_cols = []
    for col in df.columns:
        # Check if the number of unique values is 1 (handling potential NaNs)
        if df[col].nunique(dropna=False) == 1:
            constant_cols.append(col)
    return constant_cols

def detect_near_constant_columns(df, threshold=0.95):
    """
    Returns a dictionary of columns that reach a dominant value threshold.
    """
    near_constant = {}
    for col in df.columns:
        counts = df[col].value_counts(normalize=True, dropna=False)
        if not counts.empty and counts.iloc[0] >= threshold:
            near_constant[str(col)] = str(counts.index[0])
    return near_constant

def detect_outliers_iqr(df):
    """
    Detects outliers using the Interquartile Range (IQR) method.
    Returns a dictionary {column_name: [row_indices]}.
    """
    outliers_dict = {}
    
    # Select only numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        # Calculate Q1 (25th percentile) and Q3 (75th percentile)
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        
        # Calculate IQR
        IQR = Q3 - Q1
        
        # Define bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Find indices where values are outside bounds
        outlier_indices = df[(df[col] < lower_bound) | (df[col] > upper_bound)].index.tolist()
        
        if outlier_indices:
            outliers_dict[col] = outlier_indices
            
    return outliers_dict

def perform_auto_cleaning(df, method="mean"):
    """
    Fills NaN values in the DataFrame based on the specified method.
    Default is 'mean' for numeric columns.
    """
    df_cleaned = df.copy()
    
    # Handle numeric columns
    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if method == "mean":
            fill_value = df_cleaned[col].mean()
        elif method == "median":
            fill_value = df_cleaned[col].median()
        elif method == "mode":
            fill_value = df_cleaned[col].mode().iloc[0] if not df_cleaned[col].mode().empty else 0
        else:
            fill_value = 0 # Fallback
            
        df_cleaned[col].fillna(fill_value, inplace=True)
        
    # Handle non-numeric columns (e.g., fill with mode or 'Unknown')
    non_numeric_cols = df_cleaned.select_dtypes(exclude=[np.number]).columns
    for col in non_numeric_cols:
        # Using mode for categorical, or 'Unknown' if mode fails
        mode_val = df_cleaned[col].mode()
        if not mode_val.empty:
            df_cleaned[col].fillna(mode_val[0], inplace=True)
        else:
            df_cleaned[col].fillna("Unknown", inplace=True)
            
    return df_cleaned

def calculate_skewness(df):
    """
    Calculates the skewness of numeric columns in the DataFrame.
    Returns a dictionary {column_name: skewness_value}.
    """
    skewness_dict = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        skewness_dict[col] = df[col].skew()
        
    return skewness_dict