"""
PDF Report Generator with AI interpretations.
Converts Word report to PDF using python-docx and basic HTML→PDF pipeline.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from io import BytesIO
import tempfile
import subprocess
import os

from .base import AbstractGenerator
from .word_report import WordReportGenerator
from app.configs import StudyConfig


class PDFReportGenerator(AbstractGenerator):
    """
    Generates PDF report with AI interpretations.
    Uses Word→PDF conversion pipeline.
    """

    def __init__(self, study_config: StudyConfig, results: Dict[str, Any]):
        super().__init__(study_config, results)
        self._word_generator = WordReportGenerator(study_config, results)

    def generate(self, output_path: str) -> str:
        """
        Generate PDF by first creating Word doc, then converting to PDF.
        """
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp Word file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_docx = tmp.name

        try:
            # Generate Word document with AI interpretations
            self._word_generator.generate(tmp_docx)

            # Convert to PDF
            pdf_bytes = self._convert_docx_to_pdf(tmp_docx)

            if pdf_bytes:
                out_path.write_bytes(pdf_bytes)
                return str(out_path.resolve())
            else:
                # Fallback: return docx path if PDF conversion failed
                import shutil
                fallback_docx = out_path.with_suffix(".docx")
                shutil.copy(tmp_docx, fallback_docx)
                return str(fallback_docx.resolve())
        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_docx)
            except Exception:
                pass

    def generate_bytes(self) -> bytes:
        """
        Generate PDF and return as bytes for API response.
        """
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result_path = self.generate(tmp_path)
            return Path(result_path).read_bytes()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _convert_docx_to_pdf(self, docx_path: str) -> Optional[bytes]:
        """
        Convert DOCX to PDF using available tools.
        Tries multiple methods in order of preference.
        """
        # Method 1: Try docx2pdf (Windows/Mac with MS Office or LibreOffice)
        pdf_bytes = self._try_docx2pdf(docx_path)
        if pdf_bytes:
            return pdf_bytes

        # Method 2: Try LibreOffice command line
        pdf_bytes = self._try_libreoffice(docx_path)
        if pdf_bytes:
            return pdf_bytes

        # Method 3: Try unoconv
        pdf_bytes = self._try_unoconv(docx_path)
        if pdf_bytes:
            return pdf_bytes

        return None

    def _try_docx2pdf(self, docx_path: str) -> Optional[bytes]:
        """Try using docx2pdf library."""
        try:
            from docx2pdf import convert
            pdf_path = docx_path.replace(".docx", ".pdf")
            convert(docx_path, pdf_path)
            if os.path.exists(pdf_path):
                data = Path(pdf_path).read_bytes()
                os.unlink(pdf_path)
                return data
        except Exception:
            pass
        return None

    def _try_libreoffice(self, docx_path: str) -> Optional[bytes]:
        """Try using LibreOffice for conversion."""
        try:
            out_dir = os.path.dirname(docx_path)
            result = subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", out_dir,
                    docx_path
                ],
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0:
                pdf_path = docx_path.replace(".docx", ".pdf")
                if os.path.exists(pdf_path):
                    data = Path(pdf_path).read_bytes()
                    os.unlink(pdf_path)
                    return data
        except Exception:
            pass
        return None

    def _try_unoconv(self, docx_path: str) -> Optional[bytes]:
        """Try using unoconv for conversion."""
        try:
            pdf_path = docx_path.replace(".docx", ".pdf")
            result = subprocess.run(
                ["unoconv", "-f", "pdf", "-o", pdf_path, docx_path],
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0 and os.path.exists(pdf_path):
                data = Path(pdf_path).read_bytes()
                os.unlink(pdf_path)
                return data
        except Exception:
            pass
        return None

    def _prepare_data(self) -> Dict[str, Any]:
        """Prepare data (delegated to WordReportGenerator)."""
        return self._word_generator._prepare_data()
