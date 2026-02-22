"""
PDF Exporter - converts DOCX to PDF using LibreOffice headless.
Falls back to basic python-docx2pdf if LibreOffice is not available.
"""
import subprocess
import tempfile
import os
import shutil
from typing import Optional


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert DOCX bytes to PDF bytes."""
    # Try LibreOffice first (best quality)
    lo_path = _find_libreoffice()
    if lo_path:
        return _convert_with_libreoffice(docx_bytes, lo_path)
    
    # Fallback: try docx2pdf
    try:
        from docx2pdf import convert
        return _convert_with_docx2pdf(docx_bytes)
    except ImportError:
        pass
    
    raise RuntimeError(
        "PDF conversion requires LibreOffice or docx2pdf. "
        "Install LibreOffice: brew install --cask libreoffice"
    )


def _find_libreoffice() -> Optional[str]:
    """Find LibreOffice binary on macOS."""
    paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        shutil.which("libreoffice"),
        shutil.which("soffice"),
    ]
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _convert_with_libreoffice(docx_bytes: bytes, lo_path: str) -> bytes:
    """Convert using LibreOffice headless."""
    with tempfile.TemporaryDirectory() as tmp:
        docx_path = os.path.join(tmp, "report.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        
        result = subprocess.run(
            [lo_path, "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
            capture_output=True, timeout=60
        )
        
        pdf_path = os.path.join(tmp, "report.pdf")
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr.decode()}")
        
        with open(pdf_path, "rb") as f:
            return f.read()


def _convert_with_docx2pdf(docx_bytes: bytes) -> bytes:
    """Convert using docx2pdf (requires MS Word on macOS)."""
    # docx2pdf requires a file path, not bytes
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        docx_path = os.path.join(tmp, "report.docx")
        pdf_path = os.path.join(tmp, "report.pdf")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        
        with open(pdf_path, "rb") as f:
            return f.read()
