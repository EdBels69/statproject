from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
from app.configs import StudyConfig

class AbstractGenerator(ABC):
    """
    Abstract base class for document generators.
    """
    
    def __init__(self, study_config: StudyConfig, results: Dict[str, Any]):
        self.study_config = study_config
        self.results = results
        self.output_dir = Path("backend/workspace/temp") # Default, should happen elsewhere
        
    @abstractmethod
    def generate(self, output_path: str) -> str:
        """
        Generate the document.
        
        Args:
            output_path: Path where to save the file
            
        Returns:
            Absolute path to the generated file
        """
        pass
    
    @abstractmethod
    def _prepare_data(self) -> Dict[str, Any]:
        """
        Prepare data for the template.
        """
        pass
