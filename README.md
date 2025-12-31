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
   - Optional: `DND_DEFAULT_MODEL` (defaults to `gpt-5.2`)

2. Start:
   ```bash
   docker compose up --build
   ```

3. Open:
   - http://127.0.0.1:8000/campaigns

### Run LiteLLM alongside the app (standalone stack)

If you want to run the web app on your host (via `uvicorn`) but still use a Dockerized LiteLLM proxy, use:

```bash
docker compose -f docker-compose.litellm.yml up
```

Then start the web app normally and point it at the proxy:
- Set `LITELLM_BASE_URL=http://localhost:4000`
- If you set `LITELLM_MASTER_KEY`, also set `LITELLM_API_KEY` to the same value

### LiteLLM env vars used by the app

The AI generator supports a LiteLLM proxy when `LITELLM_BASE_URL` (or `LITELLM_PROXY_URL`) is set.
- `LITELLM_BASE_URL`: e.g. `http://localhost:4000`
- `LITELLM_API_KEY`: proxy key (or leave blank if proxy is unsecured locally)
- `DND_DEFAULT_MODEL`: model name/alias (example: `gpt-5.2` or a LiteLLM model alias)

### Optional: Flowchart rendering (Graphviz)

Campaign pack generation always saves the decision flow as source files (`.mmd` and `.dot`).
If Graphviz is installed (the `dot` command is on your PATH), it will also render a printable flowchart:
- `decision_flow_*.png`
- `decision_flow_*.pdf`

## Task runner (Taskfile)

This repo includes a `Taskfile.yml` for common workflows.

1. Install Task (Taskfile.dev):
   - Windows (Chocolatey): `choco install go-task`
   - Windows (Scoop): `scoop install task`

2. Run tasks:
   - `task test`
   - `task web:dev`
   - `task stack`

The first time you run a task, it will create/update a local `.env` and prompt for missing keys.

## Local model alternatives (Ollama + Stable Diffusion)

### Ollama (LLM)

The compose stacks include an `ollama` service and a LiteLLM config that exposes `llama3.3` through the LiteLLM proxy.

1. Start the stack (full or LiteLLM-only):
   - Full: `docker compose up --build`
   - LiteLLM-only: `docker compose -f docker-compose.litellm.yml up`

2. Pull the model once:
   - `docker exec -it dnd_tools-ollama-1 ollama pull llama3.3`
     (container name may differ; use `docker ps` to confirm)

3. Set `DND_DEFAULT_MODEL=llama3.3` to use it via LiteLLM.

### Stable Diffusion (images/maps)

Both compose files also include an optional ComfyUI sidecar (profile `sd`):
- Start it with: `docker compose --profile sd up --build`
- It exposes a UI on `http://localhost:8188`

Campaign pack generation can optionally call ComfyUI automatically when configured:
- Set `COMFYUI_BASE_URL=http://localhost:8188`
- Set `COMFYUI_CHECKPOINT` to a checkpoint filename available in ComfyUI (models/checkpoints)
- Optional controls: `COMFYUI_MAX_IMAGES`, `COMFYUI_MODE` (`location|scene|both`), `COMFYUI_WIDTH/HEIGHT`, `COMFYUI_STEPS`, `COMFYUI_CFG`

For ~8GB VRAM/RAM constraints, prefer SD1.5/SD-turbo style models and keep resolutions modest.

## Project Structure

- `src/`: Source code for tools.
  - `image_processing/`: Image manipulation scripts.
  - `map_making/`: Map generation logic.
  - `ai_tools/`: AI-powered generators.
- `data/`: Directory for input/output images and maps.
- `tests/`: Unit tests.
