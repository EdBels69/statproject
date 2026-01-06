import pandas as pd
import json
import numpy as np

class DataSampler:
    """
    Optimizes large DataFrames for LLM context windows (e.g., Gemini 1.5 Flash).
    Strategy: 'Smart Sampling' - preserve structure and boundaries, discard bulk.
    """

    @staticmethod
    def create_llm_context(df: pd.DataFrame, max_tokens: int = 8000) -> str:
        """
        Creates a JSON-string context representation of the dataset.
        """
        # 1. Schema Info
        context = {
            "summary": {
                "rows": len(df),
                "columns": len(df.columns),
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
            },
            "columns": []
        }

        # 2. Column Profiles (The "Schema")
        for col in df.columns:
            col_data = df[col]
            dtype = str(col_data.dtype)
            
            info = {
                "name": str(col),
                "type": dtype,
                "null_count": int(col_data.isnull().sum())
            }

            # Add "Outliers" / Boundaries
            if pd.api.types.is_numeric_dtype(col_data):
                info["min"] = float(col_data.min()) if not col_data.empty else None
                info["max"] = float(col_data.max()) if not col_data.empty else None
                info["mean"] = float(col_data.mean()) if not col_data.empty else None
            elif pd.api.types.is_object_dtype(col_data) or pd.api.types.is_categorical_dtype(col_data):
                # For high cardinality, show top 5 + count
                if col_data.nunique() < 20:
                    info["categories"] = col_data.dropna().unique().tolist()
                else:
                    info["sample_values"] = col_data.dropna().sample(min(5, len(col_data))).tolist()

            context["columns"].append(info)

        # 3. Data Snippet (Head + Tail)
        # We prefer a markdown table for the LLM to 'see' the data structure
        head_rows = df.head(10)
        tail_rows = df.tail(5)
        
        # Combine if small, else separate
        if len(df) <= 15:
            snippet_df = df
        else:
            snippet_df = pd.concat([head_rows, tail_rows])
        
        # Convert to Markdown for efficiency in token representation (cleaner than CSV usually)
        snippet_md = snippet_df.to_markdown(index=False)

        final_prompt = f"""
DATASET SUMMARY:
{json.dumps(context['summary'], indent=2)}

COLUMN SCHEMA:
{json.dumps(context['columns'], indent=2)}

DATA SNIPPET (Head 10 + Tail 5):
{snippet_md}
"""
        return final_prompt

    @staticmethod
    def chunk_dataframe(df: pd.DataFrame, chunk_size: int = 100):
        """
        Yields chunks of the dataframe for iterative processing if strict row-by-row analysis is needed.
        """
        for i in range(0, len(df), chunk_size):
            yield df.iloc[i:i + chunk_size]
