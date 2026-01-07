import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("backend"))

from app.modules.variable_classifier import classify_variables

columns = [
    {'name': 'Arm', 'type': 'categorical'},
    {'name': 'Subject_ID', 'type': 'text'},
    {'name': 'SBP_V1', 'type': 'numeric'},
    {'name': 'SBP_V2', 'type': 'numeric'},
    {'name': 'WeirdColumn', 'type': 'numeric'}
]

context = """
This study compares two groups (Arm A and B). 
We should exclude Subject_ID from analysis.
The main outcome is SBP measured at V1.
WeirdColumn is also a grouping variable for subgroup analysis.
"""

print("Testing context parsing...")
result = classify_variables(columns, context)

print("\nHINTS APPLIED:")
for name, cfg in result.items():
    if "AI" in str(cfg.get('reason', '')):
        print(f"{name}: {cfg['role']} ({cfg['reason']})")
    elif name == 'WeirdColumn': # Check if context caught this
        print(f"{name}: {cfg['role']} ({cfg['reason']})")

print("\nFull Result for WeirdColumn:")
print(result['WeirdColumn'])
