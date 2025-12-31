from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class ComfyUIImageRef:
    filename: str
    subfolder: str
    type: str


def _base_url() -> str | None:
    url = os.getenv("COMFYUI_BASE_URL")
    if not url:
        return None
    return url.rstrip("/")


def is_configured() -> bool:
    return _base_url() is not None


def _url(path: str) -> str:
    base = _base_url()
    if not base:
        raise RuntimeError("COMFYUI_BASE_URL is not set")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def build_txt2img_workflow(
    *,
    positive: str,
    negative: str,
    checkpoint: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    seed: int,
    filename_prefix: str,
    sampler_name: str = "euler",
    scheduler: str = "normal",
) -> dict[str, Any]:
    """A minimal ComfyUI txt2img workflow using common built-in nodes."""
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]}},
    }


def queue_prompt(*, workflow: dict[str, Any]) -> str:
    r = requests.post(_url("/prompt"), json={"prompt": workflow}, timeout=30)
    r.raise_for_status()
    data = r.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"Unexpected ComfyUI response: {data}")
    return str(prompt_id)


def get_history(prompt_id: str) -> dict[str, Any] | None:
    r = requests.get(_url(f"/history/{prompt_id}"), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def wait_for_result_image(
    *,
    prompt_id: str,
    timeout_s: int = 600,
    poll_s: float = 1.0,
) -> ComfyUIImageRef:
    """Wait until the prompt appears in history and contains an output image."""
    deadline = time.time() + timeout_s
    last_seen: dict[str, Any] | None = None

    while time.time() < deadline:
        hist = get_history(prompt_id)
        if hist and prompt_id in hist:
            last_seen = hist[prompt_id]
            outputs = (last_seen.get("outputs") or {})
            # Find any images
            for _node_id, out in outputs.items():
                images = out.get("images") if isinstance(out, dict) else None
                if not images:
                    continue
                img = images[0]
                return ComfyUIImageRef(
                    filename=img.get("filename", ""),
                    subfolder=img.get("subfolder", ""),
                    type=img.get("type", "output"),
                )

        time.sleep(poll_s)

    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}. Last: {last_seen}")


def download_image(*, ref: ComfyUIImageRef, dest_path: Path) -> None:
    if not ref.filename:
        raise RuntimeError("ComfyUI image ref missing filename")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    r = requests.get(
        _url("/view"),
        params={"filename": ref.filename, "subfolder": ref.subfolder, "type": ref.type},
        timeout=60,
    )
    r.raise_for_status()
    dest_path.write_bytes(r.content)
