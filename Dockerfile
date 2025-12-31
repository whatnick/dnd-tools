FROM python:3.12-slim

WORKDIR /app

# Install uv (fast, consistent installs)
RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN uv sync --frozen || uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
