import os
import pandas as pd
import numpy as np
import base64
import io
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List

class ProtocolReport:
    """
    Generates a comprehensive HTML report from a Protocol Analysis Run.
    V2 Report Engine supporting multi-step protocols.
    """
    
    def __init__(self, run_data: Dict, dataset_name: str = "Dataset"):
        self.data = run_data # The full results.json
        self.dataset_name = dataset_name
        self.html_parts = []
        
    def generate_html(self) -> str:
        self._add_header()
        
        results = self.data.get("results", {})
        
        # 1. Look for Table 1 (Descriptive)
        # Sort keys to preserve order if possible, or rely on step IDs if logical
        for step_id, res in results.items():
            if res.get("type") == "table_1":
                self._add_table_one(res, step_id)
                
        # 2. Look for Hypothesis Tests
        for step_id, res in results.items():
            if res.get("type") in ["compare", "hypothesis_test", "correlation", "regression", "survival"]:
                self._add_analysis_section(res, step_id)
            elif res.get("type") == "batch_compare_by_factor":
                 self._add_longitudinal_section(res, step_id)

        self._add_footer()
        return "\n".join(self.html_parts)

    def _add_header(self):
        # Professional Print-Friendly CSS
        css = """
        <style>
            body { font-family: 'Times New Roman', Times, serif; line-height: 1.5; color: #000; max-width: 900px; margin: 0 auto; padding: 40px; }
            h1 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #000; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 30px; letter-spacing: -0.5px; }
            h2 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #000; margin-top: 40px; border-bottom: 1px solid #000; padding-bottom: 5px; font-size: 1.4em; }
            h3 { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #10B981; font-size: 1.1em; margin-top: 25px; text-transform: uppercase; letter-spacing: 0.05em; }
            .card { background: #fff; border: none; padding: 0; margin-bottom: 40px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 1em; }
            th, td { padding: 8px 10px; border-bottom: 1px solid #ccc; text-align: left; }
            th { background-color: #fff; font-weight: bold; color: #000; border-bottom: 2px solid #000; text-transform: uppercase; font-size: 0.85em; letter-spacing: 0.05em; }
            tr:last-child td { border-bottom: 1px solid #ccc; }
            .stat-val { font-family: 'Courier New', monospace; font-weight: 600; }
            .sig-yes { color: #000; font-weight: bold; border-bottom: 2px solid #10B981; }
            .sig-no { color: #666; font-style: italic; }
            .plot-container { text-align: center; margin-top: 20px; background: #fff; padding: 10px; border: 1px solid #eee; }
            img { max-width: 100%; height: auto; }
            .ai-box { background: #f9f9f9; border-left: 3px solid #10B981; padding: 15px; margin-top: 20px; font-style: italic; color: #333; }
            .meta-info { color: #666; font-size: 0.9em; margin-bottom: 30px; font-family: sans-serif; }
            @media print { 
                body { padding: 0; max-width: 100%; } 
                .card { break-inside: avoid; }
            }
        </style>
        """
        self.html_parts.append(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analysis Report - {self.dataset_name}</title>
            {css}
        </head>
        <body>
            <h1>Statistical Analysis Report</h1>
            <div class="meta-info">
                <p><strong>Protocol:</strong> {self.data.get('protocol_name', 'Custom Analysis')}</p>
                <p><strong>Dataset:</strong> {self.dataset_name}</p>
                <p><strong>Date Generated:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        """)

    def _add_table_one(self, res: Dict, step_id: str):
        stats = res.get("data", {})
        if not stats: return
        
        groups = [k for k in stats.keys() if k != 'overall']
        
        html = f"""
        <div class="card">
            <h2>Table 1: Descriptive Statistics</h2>
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%">Characteristic</th>
                        {''.join([f'<th>{g} (n={stats[g]["count"]})</th>' for g in groups])}
                        <th>Overall (n={stats['overall']['count']})</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        metrics = [
            ("Mean (SD)", lambda s: f"{s['mean']:.2f} ({s['std']:.2f})"),
            ("95% CI (Mean)", lambda s: f"[{s.get('ci_95_low', 0):.2f}, {s.get('ci_95_high', 0):.2f}]"),
            ("Median [Q1, Q3]", lambda s: f"{s['median']:.2f} [{s['q1']:.2f}, {s['q3']:.2f}]"),
            ("IQR", lambda s: f"{s.get('iqr', 0):.2f}"),
            ("Range (Min-Max)", lambda s: f"{s['min']:.2f} - {s['max']:.2f}"),
            ("Normality (Shapiro p)", lambda s: f"{s['shapiro_p']:.3f} {'(!)' if s['shapiro_p'] < 0.05 else ''}")
        ]
        
        for name, formatter in metrics:
            row = f"<tr><td>{name}</td>"
            for g in groups:
                 row += f"<td>{formatter(stats[g])}</td>"
            row += f"<td>{formatter(stats['overall'])}</td></tr>"
            html += row
            
        html += """
                </tbody>
            </table>
        </div>
        """
        self.html_parts.append(html)

    def _add_analysis_section(self, res: Dict, step_id: str):
        sig_class = "sig-yes" if res.get("significant") else "sig-no"
        sig_text = "SIGNIFICANT" if res.get("significant") else "Not Significant"
        
        method_name = res.get('method', {}).get('name', 'Statistical Test')
        p_val = res.get('p_value', 1.0)
        p_display = "< 0.001" if p_val < 0.001 else f"{p_val:.4f}"
        
        html = f"""
        <div class="card">
            <h2>Analysis Step: {step_id}</h2>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h3>{method_name}</h3>
                    <table style="width: auto; margin-top: 10px;">
                        <tr>
                            <td><strong>P-Value:</strong></td>
                            <td><span class="stat-val {sig_class}">{p_display}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Statistic:</strong></td>
                            <td>{res.get('stats', 0):.3f}</td>
                        </tr>
                        <tr>
                            <td><strong>Result:</strong></td>
                            <td>{sig_text}</td>
                        </tr>
                    </table>
                </div>
            </div>
        """
        
        # Generate Plot
        img_b64 = self._generate_plot_image(res)
        if img_b64:
            html += f'<div class="plot-container"><img src="data:image/png;base64,{img_b64}" alt="Analysis Plot" /></div>'
            
        if res.get("narrative"):
            html += f'<div class="ai-box"><strong>Interpretation:</strong><br>{res["narrative"]}</div>'
        elif res.get("conclusion"):
            html += f'<div class="ai-box"><strong>Conclusion:</strong><br>{res["conclusion"]}</div>'
            
        html += "</div>"
        self.html_parts.append(html)

    def _add_longitudinal_section(self, res: Dict, step_id: str):
        html = f"""
        <div class="card">
            <h2>Longitudinal Analysis: {step_id}</h2>
            <p style="margin-bottom: 15px;">Analysis split by: <strong>{res.get('split_by')}</strong></p>
            <table>
                <thead>
                    <tr>
                        <th>Timepoint / Split</th>
                        <th>Method</th>
                        <th>P-Value</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for slice_key, slice_res in res.get("slices", {}).items():
            is_sig = slice_res.get("significant", False)
            p_val = slice_res.get('p_value', 1.0)
            p_display = "< 0.001" if p_val < 0.001 else f"{p_val:.4f}"
            
            html += f"""
                <tr>
                    <td><strong>{slice_key}</strong></td>
                    <td>{slice_res.get('method', {}).get('name', '-')}</td>
                    <td><span class="stat-val { 'sig-yes' if is_sig else 'sig-no' }">{p_display}</span></td>
                    <td>{ 'Difference Detected' if is_sig else 'No Difference' }</td>
                </tr>
            """
            
        html += "</tbody></table></div>"
        self.html_parts.append(html)

    def _add_footer(self):
        self.html_parts.append("""
        <div style="margin-top: 50px; color: #888; text-align: center; font-size: 0.8em; border-top: 1px solid #eee; padding-top: 20px;">
            Generated by AI Biostatistics Platform &bull; Antigravity Agent
        </div>
        </body></html>
        """)

    def _generate_plot_image(self, res: Dict) -> str:
        """
        Uses matplotlib/seaborn to render the plot stats into a base64 string.
        """
        try:
            plt.figure(figsize=(8, 5))
            sns.set_style("ticks") # Minimalist ticks
            sns.set_context("paper")
            
            plot_data = res.get("plot_data", [])
            
            if plot_data:
                # Reconstruct DataFrame for plotting
                df_plot = pd.DataFrame(plot_data)
                
                # Determine Plot Type based on method
                method_type = res.get("method", {}).get("type", "parametric")
                
                if "group" in df_plot.columns and "value" in df_plot.columns:
                    # Boxplot + Strip for group comparison (Grayscale)
                    sns.boxplot(x="group", y="value", data=df_plot, showfliers=False, color="#e5e5e5", width=0.5, linewidth=1.5)
                    sns.stripplot(x="group", y="value", data=df_plot, color="black", size=4, alpha=0.6)
                    plt.title("Comparison", fontsize=12, fontweight='bold')
                    sns.despine()
                    
                elif "x" in df_plot.columns and "y" in df_plot.columns:
                    # Scatter plot for correlation/regression
                    sns.scatterplot(x="x", y="y", data=df_plot, color="black", alpha=0.7)
                    sns.regplot(x="x", y="y", data=df_plot, scatter=False, color="#333", line_kws={"linewidth": 2})
                    plt.title("Correlation", fontsize=12, fontweight='bold')
                    sns.despine()
                    
                elif "probability" in df_plot.columns and "time" in df_plot.columns:
                     # Survival Plot
                     groups = df_plot["group"].unique()
                     ls = ['-', '--', '-.', ':']
                     for i, g in enumerate(groups):
                         sub = df_plot[df_plot["group"] == g]
                         line_style = ls[i % len(ls)]
                         plt.step(sub["time"], sub["probability"], where="post", label=f"Group {g}", color="black", linestyle=line_style)
                     plt.ylim(0, 1.05)
                     plt.legend(frameon=False)
                     plt.title("Kaplan-Meier Curve", fontsize=12, fontweight='bold')
                     sns.despine()
            
            else:
                 # Fallback if no raw data, try plot_stats
                 plot_stats = res.get("plot_stats", {})
                 if plot_stats:
                     # Bar chart
                     groups = list(plot_stats.keys())
                     means = [s["mean"] for s in plot_stats.values()]
                     sems = [s["sem"] for s in plot_stats.values()]
                     
                     plt.bar(groups, means, yerr=sems, capsize=5, color="#d4d4d4", edgecolor="black", alpha=0.8)
                     plt.title("Comparison (Mean ± SEM)", fontsize=12, fontweight='bold')
                     sns.despine()
                 else:
                     plt.text(0.5, 0.5, 'No Visualization Available', 
                              ha='center', va='center', transform=plt.gca().transAxes)
            
            # Save to buffer
            buf = io.BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format='png', dpi=100)
            plt.close()
            return base64.b64encode(buf.getvalue()).decode('utf-8')
            
        except Exception as e:
            print(f"Plotting failed: {e}")
            return ""

def render_protocol_report(run_data: Dict, dataset_name: str) -> str:
    report = ProtocolReport(run_data, dataset_name)
    return report.generate_html()

def render_report(analysis_result: Any, target_col: str, group_col: str, dataset_name: str) -> str:
    """
    Renders a report for a single analysis result by wrapping it in a protocol structure.
    """
    # Convert Pydantic object to dict if needed
    if hasattr(analysis_result, "dict"): 
        res_dict = analysis_result.dict()
    elif isinstance(analysis_result, dict):
        res_dict = analysis_result
    else:
        # Fallback empty
        res_dict = {}

    # Wrap in "step" structure for ProtocolReport
    mock_run = {
        "protocol_name": f"Analysis: {target_col} vs {group_col}",
        "results": {
            "step_1": {
                **res_dict,
                "type": "hypothesis_test",
                # Ensure keys required by _add_analysis_section exist
                "method": res_dict.get("method"),
                "significant": res_dict.get("significant"),
                "p_value": res_dict.get("p_value"),
                "conclusion": res_dict.get("conclusion"),
                "stats": res_dict.get("stat_value")
            }
        }
    }
    report = ProtocolReport(mock_run, dataset_name)
    return report.generate_html()

# Keep minimal backward compat for old direct calls if any
def generate_pdf_report(results, variables, dataset_id):
    return ""
