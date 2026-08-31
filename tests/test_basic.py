import pytest
import os
from fastapi.testclient import TestClient

from src.web.app import app
from src.workflows.campaign_pack import write_campaign_pack_pdf

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


def test_healthz():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_campaign_pdf_resets_cursor_after_each_block(tmp_path):
    output = tmp_path / "campaign.pdf"
    write_campaign_pack_pdf(
        pack={
            "title": "Test Campaign",
            "premise": "A compact premise.",
            "tone": "Mysterious",
            "starting_location": "The observatory",
            "locations": [{"name": "Tower", "summary": "A tall tower.", "encounters": ["Storm"]}],
            "npcs": [{"name": "Elara", "race": "Human", "role": "Guide"}],
            "scenes": [
                {
                    "title": "Arrival",
                    "location": "Tower",
                    "setup": "The party arrives.",
                    "player_options": [{"label": "Enter", "outcome": "The door opens."}],
                }
            ],
            "handouts": [{"title": "Warning", "content": "Do not look down."}],
        },
        output_pdf=output,
    )
    assert output.stat().st_size > 0
