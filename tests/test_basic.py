import pytest
import os

def test_project_structure():
    """Check if the basic project structure exists."""
    assert os.path.exists("src/image_processing")
    assert os.path.exists("src/map_making")
    assert os.path.exists("src/ai_tools")

def test_imports():
    """Check if main dependencies can be imported."""
    import PIL
    import cv2
    import numpy
    import matplotlib
    import openai
    import anthropic
    import fpdf
    import typer
    assert True

def test_cli_help():
    """Check if the CLI tools can be invoked."""
    import subprocess
    result = subprocess.run(["uv", "run", "python", "src/image_processing/portrait_pdf_gen.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Generate a PDF with character portraits" in result.stdout
