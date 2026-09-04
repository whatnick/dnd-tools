# D&D Tools

A modern Python environment for image processing, map making, and AI-powered Dungeons & Dragons tools.

See [ROADMAP.md](ROADMAP.md) for the planned connected services, character and
monster generation, encounter assistance, visual pipeline, and campaign
management milestones.

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

### Campaign image providers

Both compose files also include an optional ComfyUI sidecar (profile `sd`):
- Start it with: `docker compose --profile sd up --build`
- It exposes a UI on `http://localhost:8188`

Campaign pack generation can optionally call ComfyUI automatically when configured:
- Set `COMFYUI_BASE_URL=http://localhost:8188`
- Set `COMFYUI_CHECKPOINT` to a checkpoint filename available in ComfyUI (models/checkpoints)
- Optional controls: `COMFYUI_WIDTH/HEIGHT`, `COMFYUI_STEPS`, `COMFYUI_CFG`

[Nano Banana 2 MCP](https://github.com/whatnick/nano-banana-2-mcp-rs) is
supported as a second, independent provider:

- Set `NANO_BANANA_MCP_URL=http://localhost:3000/mcp`.
- Configure `GEMINI_API_KEY` on the MCP service, not on D&D Tools.
- Tune `NANO_BANANA_RESOLUTION`, `NANO_BANANA_ASPECT_RATIO`, and
  `NANO_BANANA_THINKING` as needed.

Use `CAMPAIGN_IMAGE_PROVIDERS=auto`, `comfyui`, `nano-banana`, `both`, or
`none`. Shared controls are `CAMPAIGN_IMAGE_MODE` (`location|scene|both`) and
`CAMPAIGN_IMAGE_MAX_IMAGES`. Both providers consume the same visual briefs and
store provider, prompt, and generation settings with each campaign artifact.
A failure in one provider creates a provider-specific warning without failing
the campaign or stopping the other provider.

For ~8GB VRAM/RAM constraints, prefer SD1.5/SD-turbo style models and keep resolutions modest.

## Local kind deployment

The complete campaign-generation stack can run in a local
[kind](https://kind.sigs.k8s.io/) cluster. It includes D&D Tools, LiteLLM,
Ollama, the `qwen2.5:3b` campaign model, Nano Banana's Streamable HTTP MCP
service, and persistent volumes for application data and model files.

Prerequisites:

- Docker Desktop using the WSL2 Linux engine
- `kubectl`
- `kind`
- At least 20 GB of free disk space
- A local checkout of `nano-banana-2-mcp-rs` at
  `\\wsl.localhost\Ubuntu-22.04\home\tisham\dev\nano-banana-2-mcp-rs`, or
  `NANO_BANANA_SOURCE` set to its path

Deploy and validate:

```powershell
task kind:deploy
task kind:validate
task kind:acceptance
```

Open <http://127.0.0.1:8000/campaigns>. LiteLLM and cluster Ollama are also
exposed locally on ports `4000` and `11435` for diagnostics. Port `11435`
avoids conflicting with a host installation of Ollama on its usual `11434`.
The quick validation checks health and model inference; acceptance validation
checks MCP discovery, generates a complete campaign, and verifies every
downloadable artifact.

Nano Banana starts without a Gemini key so discovery and MCP integration can be
tested without making paid image calls. To enable it:

```powershell
kubectl create secret generic nano-banana-mcp --namespace dnd-tools `
  --from-literal=GEMINI_API_KEY="$env:GEMINI_API_KEY"
kubectl --namespace dnd-tools rollout restart deployment/nano-banana-mcp
kubectl --namespace dnd-tools set env deployment/dnd-tools `
  CAMPAIGN_IMAGE_PROVIDERS=nano-banana
```

Set the last value to `both` when a reachable ComfyUI service and checkpoint
are also configured. The D&D Tools pod receives only the MCP URL; the Gemini
credential remains isolated in the image-service pod.

The kind deployment deliberately runs Ollama without a Kubernetes GPU resource
request. Docker Desktop supports the laptop GPU for standalone Linux
containers, but does not reliably pass that GPU into kind's containerized node.
The small local model remains practical on the available CPU and RAM. A native
Linux Kubernetes GPU node can add `nvidia.com/gpu: 1` to the Ollama container.
Campaign generation is bounded to 2,600 output tokens and requests JSON mode so
local models cannot run indefinitely while producing malformed prose.

## Project Structure

- `src/`: Source code for tools.
  - `image_processing/`: Image manipulation scripts.
  - `map_making/`: Map generation logic.
  - `ai_tools/`: AI-powered generators.
- `data/`: Directory for input/output images and maps.
- `tests/`: Unit tests.
