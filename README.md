# D&D Tools

A modern Python environment for image processing, map making, and AI-powered Dungeons & Dragons tools.

## Features

- **Image Processing**: Tools for resizing, applying vintage filters, and adding borders to maps and character art.
- **Map Making**: Scripts to generate grid-based dungeon drafts and terrain.
- **AI Tools**: Generators for character backstories, plot hooks, and more using OpenAI/Anthropic.

## Setup

This project uses `uv` for dependency management.

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Environment Variables**:
   Copy `.env.example` to `.env` and add your API keys:
   ```bash
   cp .env.example .env
   ```

## Usage

### Image Processing
```python
from src.image_processing.utils import apply_sepia
apply_sepia("path/to/map.png", "path/to/vintage_map.png")
```

### Portrait PDF Generator
Generate A4 PDFs from a folder of character portraits:
```bash
uv run python src/image_processing/portrait_pdf_gen.py data/portraits -o output.pdf --cols 2 --rows 3
```

### Map Making
```bash
uv run python src/map_making/generator.py
```

### AI Tools
```python
from src.ai_tools.generator import DnDGenerator
gen = DnDGenerator()
print(gen.generate_character_backstory("Thokk", "Half-Orc", "Barbarian"))
```

## Web UI (FastAPI + HTMX)

This repo now includes a minimal, single-user, self-hosted campaign builder UI.

### Run locally (recommended for development)

1. Set up `.env` (copy from `.env.example` if you have it) and add at least one of:
   - `OPENAI_API_KEY` (if you want LiteLLM to call OpenAI)
   - `ANTHROPIC_API_KEY` (if you want LiteLLM to call Anthropic)

2. Start the web app:
   ```bash
   uv sync
   uv run uvicorn src.web.app:app --reload
   ```

3. Open:
   - http://127.0.0.1:8000/campaigns

### Run with LiteLLM proxy (docker-compose)

This is the intended "LiteLLM abstraction" setup. The web app talks to LiteLLM using an OpenAI-compatible API.

1. Set env vars (via `.env` or your shell):
   - `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`
   - Optional: `LITELLM_MASTER_KEY` (recommended if you expose ports)
   - Optional: `DND_DEFAULT_MODEL` (defaults to `gpt-4o`)

2. Start:
   ```bash
   docker compose up --build
   ```

3. Open:
   - http://127.0.0.1:8000/campaigns

### LiteLLM env vars used by the app

The AI generator supports a LiteLLM proxy when `LITELLM_BASE_URL` (or `LITELLM_PROXY_URL`) is set.
- `LITELLM_BASE_URL`: e.g. `http://localhost:4000`
- `LITELLM_API_KEY`: proxy key (or leave blank if proxy is unsecured locally)
- `DND_DEFAULT_MODEL`: model name/alias (example: `gpt-4o` or a LiteLLM model alias)

### Optional: Flowchart rendering (Graphviz)

Campaign pack generation always saves the decision flow as source files (`.mmd` and `.dot`).
If Graphviz is installed (the `dot` command is on your PATH), it will also render a printable flowchart:
- `decision_flow_*.png`
- `decision_flow_*.pdf`

## Project Structure

- `src/`: Source code for tools.
  - `image_processing/`: Image manipulation scripts.
  - `map_making/`: Map generation logic.
  - `ai_tools/`: AI-powered generators.
- `data/`: Directory for input/output images and maps.
- `tests/`: Unit tests.
