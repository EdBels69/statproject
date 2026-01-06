
from typing import Dict

def render_custom_plot(plot_data: Dict, params: Dict) -> str:
    """
    Regenerates a plot image based on saved plot coordinates and custom parameters.
    params: {
        "title": str,
        "xlabel": str,
        "ylabel": str,
        "theme": str ("default", "seaborn", "dark", "ggplot"),
        "color": str (hex or name)
    }
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    import io
    import base64
    
    # Apply Theme
    theme = params.get("theme", "default")
    if theme == "seaborn":
        sns.set_theme()
    elif theme == "dark":
        plt.style.use('dark_background')
    elif theme == "ggplot":
        plt.style.use('ggplot')
    else:
        plt.style.use('default')
        
    is_survival = isinstance(plot_data, list)
    plt.figure(figsize=(10, 6 if is_survival else 6))
    
    # Dispatch based on type
    p_type = "survival" if is_survival else plot_data.get("type", "generic")
    
    # 1. Survival Plot
    if isinstance(plot_data, list): # Survival is List[Dict]
        for series in plot_data:
            plt.step(series["time"], series["prob"], where="post", label=series.get("group", "Overall"))
        plt.legend()
        plt.ylim(0, 1.05)
        
    # 2. Scatter / ROC (Dictionary)
    elif p_type == "scatter":
        plt.scatter(plot_data["x"], plot_data["y"], alpha=0.7, color=params.get("color", "blue"))
        # Add fit line if desired? For now just scatter
        min_val = min(min(plot_data["x"]), min(plot_data["y"]))
        max_val = max(max(plot_data["x"]), max(plot_data["y"]))
        plt.plot([min_val, max_val], [min_val, max_val], 'r--')
        
    elif p_type == "roc":
        auc = plot_data.get("auc", 0)
        plt.plot(plot_data["x"], plot_data["y"], lw=2, label=f'ROC curve (AUC = {auc:.2f})', color=params.get("color", "darkorange"))
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.legend(loc="lower right")
        
    # Apply Labels using Params OR default
    plt.title(params.get("title", "Custom Plot"))
    plt.xlabel(params.get("xlabel", "X Axis"))
    plt.ylabel(params.get("ylabel", "Y Axis"))
    
    plt.tight_layout()
    
    # Save
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')
