import pandas as pd
import numpy as np
import os

# Ensure directory exists
output_dir = "backend/workspace/datasets"
if not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

# 1. 50 Variables, 100 Samples
n = 100
data = {f"feature_{i}": np.random.normal(0, 1, n) for i in range(50)}

# 2. Add Missing Values
data["feature_0"][0:10] = np.nan

# 3. Clean Group (Control/Treatment)
data["group_clean"] = ["Control"] * 50 + ["Treatment"] * 50

# 4. Concatenated Group (Trigger Warning)
data["group_messy"] = ["ControlControl"] * 50 + ["TreatmentTreatment"] * 50

# 5. Too Many Groups (Trigger Warning)
data["group_many"] = [f"Group_{i}" for i in range(100)]

df = pd.DataFrame(data)
output_path = os.path.join(output_dir, "stress_test.csv")
df.to_csv(output_path, index=False)
print(f"Generated {output_path}")
