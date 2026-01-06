import io
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any, List
from pathlib import Path
from app.schemas.analysis import AnalysisResult

# Configure matplotlib for non-interactive backend
plt.switch_backend('Agg')

TEMPLATE_DIR = Path(__file__).parent / "templates"

def generate_plot_image(plot_data: List[Dict[str, Any]], method_id: str) -> str:
    """
    Generates a matplotlib plot based on plot_data and returns base64 string.
    """
    if not plot_data:
        return ""
    
    # Convert to DataFrame
    df = pd.DataFrame(plot_data)
    
    plt.figure(figsize=(8, 6))
    
    # Set style
    sns.set_theme(style="whitegrid")
    
    is_parametric = method_id in ["t_test_ind", "t_test_rel"]
    
    # Scatter Plot with Jitter
    # We use stripplot for categorical scatter
    ax = sns.stripplot(
        data=df, 
        x="group", 
        y="value", 
        jitter=True, 
        alpha=0.6, 
        palette="viridis",
        size=8
    )
    
    # Overlay Boxplot (optional, for summary) or specific lines?
    # Let's add a light boxplot for context
    sns.boxplot(
        data=df,
        x="group",
        y="value",
        showfliers=False,
        boxprops={'facecolor':'none', 'edgecolor':'grey'},
        width=0.4,
        ax=ax
    )

    plt.title(f"Distribution by Group ({method_id})")
    plt.xlabel("Group")
    plt.ylabel("Value")
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return image_base64

def render_report(
    analysis_result: AnalysisResult,
    target_col: str,
    group_col: str,
    dataset_name: str = "Dataset"
) -> str:
    """
    Renders the HTML report using Jinja2.
    """
    
    # Generate Plot
    plot_img = ""
    if analysis_result.plot_data:
        try:
            plot_img = generate_plot_image(analysis_result.plot_data, analysis_result.method.id)
        except Exception as e:
            print(f"Error generating plot: {e}")

    # Prepare Context
    context = {
        "title": "Stat Analyzer Report",
        "dataset_name": dataset_name,
        "target_col": target_col,
        "group_col": group_col,
        "result": analysis_result,
        "image_base64": plot_img,
        "method_name": analysis_result.method.name,
        "method_desc": analysis_result.method.description, 
        "p_value_fmt": f"{analysis_result.p_value:.4f}" if analysis_result.p_value >= 0.001 else "< 0.001"
    }
    
    # Render Template
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("report.html")
    return template.render(**context)
