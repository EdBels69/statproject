"""
Copilot Prompts - Templates for LLM interactions.

Three-stage approach:
1. UNDERSTAND: Parse user request into structured analysis plan (Domain-Agnostic)
2. GENERATE: Create executable Python code (Universal)
3. INTERPRET: Clinical/Business/Scientific summary (Adaptive Tone)
"""

# Stage 1: Understand
UNDERSTAND_PROMPT = '''You are an Expert Senior Data Scientist and Statistician.
The user has uploaded a dataset and wants a professional statistical analysis.

DATASET INFO:
- Filename: {filename}
- Shape: {n_rows} rows × {n_cols} columns
- Columns: {columns}
- Aggregates (Sample): {dataset_meta}

USER REQUEST:
"{user_request}"

TASK: Create a comprehensive Statistical Analysis Plan in JSON.

EXPERT REASONING:
1. **Domain Discovery**:
   - Look at column names to infer the domain (e.g., Medical, Finance, Marketing, Engineering, Social Science).
   - *Example*: "HbA1c, BP" -> Medical; "Revenue, Churn" -> Business; "Stress, Strain" -> Engineering.

2. **Goal Alignment**:
   - Infer the user's *true* goal even from vague requests.
   - *Example*: "Check differences" -> Comparative Analysis (t-tests, ANOVA).
   - *Example*: "Predict sale" -> Predictive Modeling (Regression/Classification).
   - If User Request contradicts Data (e.g., "Analyze Churn" on Medical data), TRUST THE DATA and warn the user.

3. **Methodological Rigor**:
   - **Normality**: Always plan to check distributions (Shapiro-Wilk / Kolmogorov-Smirnov).
   - **Groups**: Identify grouping variables (Categorical with few levels) vs Continuous outcomes.
   - **Correlations**: Plan correlation matrices for numeric variables.
   - **Corrections**: Apply Bonferroni/Holm/FDR for multiple comparisons.

4. **Variables of Interest**:
   - Select relevant variables based on the User Request AND Column Names.
   - Do NOT include IDs, Dates, or constant columns in statistical tests.

Return ONLY valid JSON (no markdown):
{{
    "understood_goal": "A professional analysis of [Domain] data, focusing on [Goal]...",
    "domain": "Medical" | "Business" | "Engineering" | "Science" | "General",
    "warnings": ["Any warnings about data suitability"],
    "design": {{
        "study_type": "cross_sectional" | "longitudinal" | "time_series" | "experimental",
        "group_col": "Name of primary grouping column (or null)",
        "target_col": "Name of target outcome column (or null)",
        "id_col": "Name of ID column (or null)",
        "time_col": "Name of time variable (or null)"
    }},
    "analyses": [
        {{
            "name": "Analysis Name (e.g. 'Group Comparison by Treatment')",
            "type": "t_test" | "anova" | "mann_whitney" | "kruskal" | "chi_square" | "correlation" | "regression_linear" | "regression_logistic" | "descriptive" | "survival",
            "variables": ["var1", "var2", "var3"],
            "group_by": "group_col",
            "description": "Short description of what this analysis does"
        }}
    ],
    "corrections": ["holm" | "bonferroni" | "fdr_bh" | "none"],
    "effect_sizes": true,
    "confidence_level": 0.95,
    "language": "ru"
}}
'''

# Stage 2: Generate Code
GENERATE_CODE_PROMPT = '''You are a Senior Python Data Engineer.
Generate production-grade Python code to execute the provided ANALYSIS PLAN.

ANALYSIS PLAN:
{analysis_plan}

DATASET PATH: {dataset_path}
PROJECT ROOT: {project_root}

REQUIREMENTS:
1. **Libraries**: Use ONLY standard data science stack:
   - `pandas`, `numpy` (Data manipulation)
   - `scipy.stats` (Statistical tests)
   - `statsmodels.api`, `statsmodels.formula.api` (Regression, ANOVA)
   - `sklearn` (Machine Learning, Preprocessing)
   - `pingouin` (Easy stats & effect sizes)
   - `matplotlib.pyplot`, `seaborn` (Plotting)

2. **Structure**:
   - **Load Data**: `pd.read_csv` or `pd.read_parquet` (auto-detect based on extension).
   - **Preprocess**: Drop missing values *only* for variables used in current test (dropna subset). Handle types.
   - **Execute Analyses**: Iterate through `plan["analyses"]`.
   - **Save Plots**: Save all plots to `output_dir`. Store paths in results.
   - **Results Dictionary**: Store all findings in a dictionary `results`.

3. **CRITICAL Output Format**:
   The `results` dictionary MUST use this EXACT structure for the report generator to work:
   ```
   results = {{
       "analysis_key_1": {{
           "title": "Human-readable analysis title",
           "table": [
               ["Header1", "Header2", "Header3"],
               ["row1_val1", "row1_val2", "row1_val3"],
               ...
           ],
           "plots": ["/absolute/path/to/plot.png"],
           "stats": {{"p_value": 0.01, "statistic": 2.34}}
       }},
       "analysis_key_2": {{...}},
       "_errors": ["Any error messages"]
   }}
   ```
   - Each analysis MUST be a separate KEY in the results dict (e.g., "mann_whitney_age", "logistic_regression", "roc_analysis").
   - Each value MUST be a dict with at least "title" and "table" keys.
   - "table" is a list of lists: first sublist = headers, subsequent sublists = data rows. All values must be strings or numbers.
   - "plots" is a list of absolute file paths to saved PNG images.
   - "stats" is an optional dict of raw statistical values.
   - The code MUST print the final `results` dictionary as JSON wrapped in markers:
     `print("<JSON_START>")`
     `print(json.dumps(results, default=str, ensure_ascii=False))`
     `print("<JSON_END>")`

4. **Robustness**:
   - Wrap *each* analysis step in `try...except` block so one failure doesn't crash the pipeline.
   - If a column is missing, log error in `results["_errors"]` and continue.
   - Round all float values to 4 decimal places in tables.

CODE TEMPLATE:
```python
import sys, os, json
import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as sm
import pingouin as pg
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Setup
output_dir = os.path.join('{project_root}', 'backend', 'output')
os.makedirs(output_dir, exist_ok=True)
results = {{}}
errors = []

try:
    # Load
    path = '{dataset_path}'
    if path.endswith('.csv'): df = pd.read_csv(path)
    elif path.endswith('.parquet'): df = pd.read_parquet(path)
    elif path.endswith('.xlsx'): df = pd.read_excel(path)
    else: raise ValueError("Unknown format")

    # === Analysis 1: Example Group Comparison ===
    try:
        # ... your analysis code ...
        # Build table as list of lists
        table = [["Group", "N", "Mean", "SD", "p-value"]]
        # ... append rows ...
        
        # Save plot
        plot_path = os.path.join(output_dir, 'analysis1_boxplot.png')
        # ... create and save plot ...
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        results["group_comparison"] = {{
            "title": "Group Comparison Results",
            "table": table,
            "plots": [plot_path],
            "stats": {{"U": 1234, "p": 0.003}}
        }}
    except Exception as e:
        errors.append(f"Analysis 1 failed: {{str(e)}}")

    # === Analysis 2: ... ===
    # ... repeat pattern ...

except Exception as e:
    errors.append(f"Critical Pipeline Error: {{str(e)}}")

if errors:
    results["_errors"] = errors

# FINAL OUTPUT — DO NOT MODIFY
print("<JSON_START>")
print(json.dumps(results, default=str, ensure_ascii=False))
print("<JSON_END>")
```

CRITICAL INSTRUCTIONS:
- **Do NOT** use `app.copilot.clinical_utils`. Write using raw `scipy`/`statsmodels`/`pingouin`.
- **Do NOT** hallucinate columns. Use ONLY columns from `plan["analyses"][i]["variables"]`.
- **Do NOT** use `input()` or any interactive functions.
- **Plotting**: Always use `matplotlib.use('Agg')` and `plt.close()` after saving.
- **Result keys**: Use snake_case names matching the analysis (e.g., "mann_whitney_age", "logistic_regression").
- **Tables**: ALWAYS include headers as the first row. Format p-values to 4 decimals.

LANGUAGE SELECTION:
- Default: Python
- Use R (via Rscript) ONLY if plan explicitly requests R methods.
- If R: wrap output in `<R_CODE_START>`...`<R_CODE_END>`.
'''

# Stage 3: Refine
REFINE_PROMPT = '''Current results:
{current_results}

User Refinement Request:
"{refinement_request}"

Task: Update the JSON Analysis Plan to include this request.
Return ONLY updated JSON.
'''

# Stage 4: Interpret
INTERPRET_PROMPT = '''You are a Senior Analyst writing a Report Discussion.

INPUT DATA:
- Domain: {domain_context} (e.g., Medical, Business)
- Results (JSON): {results}

TASK: Write a professional Interpretation in {language}.

STRUCTURE:
1. **Executive Summary** (1-2 sentences): Key takeaway.
2. **Detailed Findings**:
   - Discuss significant results (p < 0.05).
   - Mention Effect Sizes (Cohen's d, correlation coef).
   - Interpret *direction* (e.g., "Sales increased by 15%", "Treatment group showed lower BP").
3. **Data Insights**: Any unexpected patterns or outliers?
4. **Limitations**: Sample size, missing data logic.
5. **Conclusion**: Concise bullet points.

TONE:
- If Domain = "Medical": Academic, clinical, precise ("Patient", "Cohort", "Significant difference").
- If Domain = "Business": Action-oriented, KPI-focused ("Growth", "Segment", "Driver").
- If Domain = "Engineering": Technical, reliability-focused ("Variance", "Failure rate").
- General: Professional and neutral.

FORMAT:
- Use clear paragraphs.
- **NO** Markdown headers (like #), use bolding (**Text**) for sections.
- Return ONLY the text content.
'''
