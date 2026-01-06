
import pandas as pd
import os

file_path = "workspace/datasets/05184ba6-ca10-4a48-ad65-a022ce927fe4/Первичка.xlsx"
header_row = 3

try:
    df = pd.read_excel(file_path, header=header_row)
    print(f"Loaded with header={header_row}")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(df.head())
except Exception as e:
    print(e)
