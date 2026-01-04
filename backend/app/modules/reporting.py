import os
from datetime import datetime
from fpdf import FPDF
from typing import Dict, Any, List

class ClinicalReport(FPDF):
    def __init__(self):
        super().__init__()
        # Register Unicode font (Arial)
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.abspath(os.path.join(current_dir, '..', 'assets', 'fonts'))
        
        path_r = os.path.join(font_dir, 'Arial.ttf')
        path_b = os.path.join(font_dir, 'Arial-Bold.ttf')
        path_i = os.path.join(font_dir, 'Arial-Italic.ttf')
        
        if os.path.exists(path_r):
            self.add_font('Arial', '', path_r)
        
        if os.path.exists(path_b):
            self.add_font('Arial', 'B', path_b)
            
        if os.path.exists(path_i):
            self.add_font('Arial', 'I', path_i)
            
        if not os.path.exists(path_r):
            print(f"Warning: Primary font not found at {path_r}")

    def header(self):
        self.set_font('Arial', 'B', 15)
        self.set_text_color(79, 70, 229)
        self.cell(0, 10, 'Protocol Wizard | Clinical Analysis Report', border=False, align='L')
        self.set_font('Arial', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}', border=False, align='R')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Page {self.page_no()} | Confidential Clinical Document', align='C')

def generate_pdf_report(results: Dict[str, Any], variables: Dict[str, str], dataset_id: str) -> str:
    pdf = ClinicalReport()
    pdf.add_page()
    
    # 1. Study Summary
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, '1. Study Parameters', ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 7, f"Dataset ID: {dataset_id}", ln=True)
    pdf.cell(0, 7, f"Statistical Method: {results.get('method', 'Unknown')}", ln=True)
    
    mapping_str = ", ".join([f"{k}: {v}" for k, v in variables.items()])
    pdf.multi_cell(0, 7, f"Variable Mapping: {mapping_str}")
    pdf.ln(5)

    # 2. Statistical Results
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. Statistical Results', ln=True)
    pdf.set_font('Arial', '', 10)
    
    p_val = results.get('p_value', 0)
    p_str = "< 0.001" if p_val < 0.001 else f"{p_val:.4f}"
    
    pdf.cell(0, 7, f"P-Value: {p_str}", ln=True)
    pdf.cell(0, 7, f"Test Statistic: {results.get('stat_value', 0):.4f}", ln=True)
    pdf.set_font('Arial', 'B', 10)
    significance = "STATISTICALLY SIGNIFICANT" if results.get('significant') else "NOT STATISTICALLY SIGNIFICANT"
    pdf.set_text_color(34, 139, 34) if results.get('significant') else pdf.set_text_color(220, 38, 38)
    pdf.cell(0, 7, f"Result: {significance}", ln=True)
    pdf.set_text_color(30, 41, 59)
    pdf.ln(5)

    # 3. AI Interpretation
    if 'conclusion' in results and results['conclusion']:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, '3. AI-Powered Clinical Interpretation', ln=True)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, results['conclusion'])
        pdf.ln(5)

    # 4. Group Statistics
    if 'groups' in results and results['groups']:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, '4. Group-Level Statistics', ln=True)
        pdf.set_font('Arial', '', 9)
        
        groups = results['groups']
        for group_name, stats in groups.items():
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 6, f"Group: {group_name}", ln=True)
            pdf.set_font('Arial', '', 9)
            pdf.cell(0, 5, f"  N = {stats.get('n', 'N/A')}", ln=True)
            pdf.cell(0, 5, f"  Mean = {stats.get('mean', 'N/A'):.2f}", ln=True)
            if 'median' in stats:
                pdf.cell(0, 5, f"  Median = {stats['median']:.2f}", ln=True)
            if 'sd' in stats:
                pdf.cell(0, 5, f"  SD = {stats['sd']:.2f}", ln=True)
            pdf.ln(2)

    # Save
    output_dir = "temp_reports"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"report_{dataset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_dir, filename)
    pdf.output(filepath)
    
    return filepath

def cleanup_old_reports(max_age_hours: int = 24):
    """Delete PDF reports older than max_age_hours"""
    output_dir = "temp_reports"
    if not os.path.exists(output_dir):
        return
    
    now = datetime.now()
    deleted_count = 0
    
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if not os.path.isfile(filepath):
            continue
        
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        age_hours = (now - mtime).total_seconds() / 3600
        
        if age_hours > max_age_hours:
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {filename}: {e}")
    
    if deleted_count > 0:
        print(f"Cleaned up {deleted_count} old report(s)")
