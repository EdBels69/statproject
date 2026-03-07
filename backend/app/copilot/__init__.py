# Copilot - Chat-First Statistical Analysis
"""
Copilot Module: Natural language → Statistical Analysis → Report

Architecture:
    User: "Compare groups by outcome, check dynamics of labs V1→V2"
        ↓
    [engine.py] - Understands task, generates Python code
        ↓  
    [executor.py] - Safely executes code in sandbox
        ↓
    [report.py] - Generates DOCX with results
        ↓
    User: "Add survival analysis" → Iterate
"""

from .router import router

__all__ = ["router"]
