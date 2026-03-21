from typing import Dict, Any
from pathlib import Path
from .base import AbstractGenerator
from app.configs import StudyConfig

class WordReportGenerator(AbstractGenerator):
    """
    Generates standard scientific report in Word format.
    Uses 'reporting.py' logic under the hood (eventually).
    """
    
    def __init__(self, study_config: StudyConfig, results: Dict[str, Any], template_path: str = None):
        super().__init__(study_config, results)
        self.template_path = template_path or "backend/app/generators/templates/report_gost.docx"
        
    def generate(self, output_path: str) -> str:
        # Placeholder for migration:
        # This will eventually call ProtocolReport class or replace it
        
        # 1. Prepare data
        data = self._prepare_data()
        
        # 2. Logic to generate docx
        # ... implementation pending migration ...
        
        return output_path
        
    def _prepare_data(self) -> Dict[str, Any]:
        return {
            "title": self.study_config.title,
            "results": self.results
        }
