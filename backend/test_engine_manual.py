import pandas as pd
import numpy as np
from app.stats.engine import select_test

# 1. Test T-test (Normal + 2 Groups)
df_normal = pd.DataFrame({
    'Group': ['A']*50 + ['B']*50,
    'Value': np.concatenate([np.random.normal(0, 1, 50), np.random.normal(1, 1, 50)])
})
test_1 = select_test(df_normal, 'Value', 'Group', {'Value': 'numeric', 'Group': 'categorical'})
print(f"Normal + 2 Groups -> Expected 't_test_ind', Got: '{test_1}'")

# 2. Test Mann-Whitney (Non-Normal + 2 Groups)
# Using log-normal distribution to force non-normality
df_non_normal = pd.DataFrame({
    'Group': ['A']*50 + ['B']*50,
    'Value': np.concatenate([np.random.lognormal(0, 1, 50), np.random.lognormal(1, 1, 50)])
})
test_2 = select_test(df_non_normal, 'Value', 'Group', {'Value': 'numeric', 'Group': 'categorical'})
# Note: With N=50, Shapiro might still pass sometimes, but likely Mann-Whitney or T-test dependent on randomness
print(f"Non-Normal + 2 Groups -> Expected 'mann_whitney', Got: '{test_2}'")

# 3. Test Correlation (Numeric vs Numeric)
df_corr = pd.DataFrame({
    'A': np.random.normal(0, 1, 50),
    'B': np.random.normal(0, 1, 50)
})
test_3 = select_test(df_corr, 'A', 'B', {'A': 'numeric', 'B': 'numeric'})
print(f"Numeric vs Numeric -> Expected 'pearson', Got: '{test_3}'")
