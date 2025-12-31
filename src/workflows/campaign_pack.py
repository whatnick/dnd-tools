from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from src.ai_tools.generator import DnDGenerator


_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction for LLM responses."""
    text = text.strip()

    # Direct JSON
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    # ```json ... ```
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return json.loads(m.group(1))

    # Fallback: find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("Model did not return JSON")


def _mermaid_flowchart(nodes: list[dict[str, Any]]) -> str:
    lines = ["graph TD"]
    for n in nodes:
        node_id = n.get("id")
        label = (n.get("text") or "").replace("\n", " ")
        if not node_id:
            continue
        safe_label = label.replace("\"", "'")
        lines.append(f"  {node_id}[\"{safe_label}\"]")

    for n in nodes:
        src = n.get("id")
        for opt in n.get("options", []) or []:
            dst = opt.get("next")
            label = (opt.get("label") or "").replace("\n", " ")
            if src and dst:
                safe_label = label.replace("\"", "'")
                lines.append(f"  {src} -->|\"{safe_label}\"| {dst}")

    return "\n".join(lines) + "\n"


def _dot_flowchart(nodes: list[dict[str, Any]]) -> str:
    """Create a Graphviz DOT flowchart for the decision graph."""
    def esc(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace('"', "\\\"").replace("\n", " ")

    lines = [
        "digraph DecisionFlow {",
        "  rankdir=TB;",
        "  node [shape=box, fontname=Helvetica];",
        "  edge [fontname=Helvetica];",
    ]

    for n in nodes:
        node_id = n.get("id")
        label = esc(n.get("text") or "")
        if not node_id:
            continue
        lines.append(f"  {node_id} [label=\"{label}\"]; ")

    for n in nodes:
        src = n.get("id")
        for opt in n.get("options", []) or []:
            dst = opt.get("next")
            label = esc(opt.get("label") or "")
            if src and dst:
                lines.append(f"  {src} -> {dst} [label=\"{label}\"]; ")

    lines.append("}")
    return "\n".join(lines) + "\n"


def build_campaign_pack_json(*, story_prompt: str, model: str | None = None) -> dict[str, Any]:
    """Return a structured campaign pack as a Python dict."""
    gen = DnDGenerator(model=model)

    system = (
        "You are an expert D&D campaign designer. "
        "Return STRICT JSON only. No markdown, no commentary."
    )

    user = f"""
Create a compact campaign pack from this story prompt:

{story_prompt}

Return JSON with this schema (use these exact keys):
{{
  "title": string,
  "premise": string,
  "tone": string,
  "starting_location": string,
  "locations": [
    {{"name": string, "summary": string, "encounters": [string], "map": {{"width": int, "height": int}} }}
  ],
  "npcs": [
    {{"name": string, "race": string, "role": string, "motivation": string, "secret": string}}
  ],
  "scenes": [
    {{
      "title": string,
      "location": string,
      "setup": string,
      "dialog": [{{"speaker": string, "line": string}}],
      "player_options": [{{"label": string, "outcome": string}}]
    }}
  ],
  "decision_flow": {{
    "nodes": [
      {{"id": string, "text": string, "options": [{{"label": string, "next": string}}]}}
    ]
  }},
  "handouts": [
    {{"title": string, "content": string}}
  ]
}}

Constraints:
- 4–6 locations.
- 6–10 NPCs.
- 5–8 scenes.
- Decision flow must have 8–14 nodes with ids like N1, N2, ...
- Keep content PG-13.
"""

    resp = gen.client.chat.completions.create(
        model=gen.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    text = resp.choices[0].message.content or ""
    return _extract_json(text)


def write_campaign_pack_pdf(*, pack: dict[str, Any], output_pdf: Path) -> None:
    """Write a printable PDF summary of the campaign pack."""
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", size=16)
    pdf.multi_cell(0, 8, pack.get("title", "Campaign Pack"))

    pdf.set_font("Helvetica", size=11)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 6, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    def section(title: str) -> None:
        pdf.set_font("Helvetica", style="B", size=13)
        pdf.multi_cell(0, 7, title)
        pdf.set_font("Helvetica", size=11)

    section("Premise")
    pdf.multi_cell(0, 6, pack.get("premise", ""))
    pdf.ln(2)

    section("Tone")
    pdf.multi_cell(0, 6, pack.get("tone", ""))
    pdf.ln(2)

    section("Starting Location")
    pdf.multi_cell(0, 6, pack.get("starting_location", ""))
    pdf.ln(2)

    section("Locations")
    for loc in pack.get("locations", []) or []:
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 6, f"- {loc.get('name','')}")
        pdf.set_font("Helvetica", size=11)
        summary = loc.get("summary", "")
        if summary:
            pdf.multi_cell(0, 6, summary)
        encounters = loc.get("encounters", []) or []
        if encounters:
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 6, "Encounters: " + "; ".join(encounters))
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    section("NPCs")
    for npc in pack.get("npcs", []) or []:
        line = f"- {npc.get('name','')} ({npc.get('race','')}) — {npc.get('role','')}"
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 6, line)
        pdf.set_font("Helvetica", size=11)
        mot = npc.get("motivation", "")
        sec = npc.get("secret", "")
        if mot:
            pdf.multi_cell(0, 6, f"Motivation: {mot}")
        if sec:
            pdf.set_text_color(120, 0, 0)
            pdf.multi_cell(0, 6, f"Secret (DM): {sec}")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    section("Scenes")
    for s in pack.get("scenes", []) or []:
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 6, f"- {s.get('title','')} ({s.get('location','')})")
        pdf.set_font("Helvetica", size=11)
        setup = s.get("setup", "")
        if setup:
            pdf.multi_cell(0, 6, setup)
        opts = s.get("player_options", []) or []
        if opts:
            pdf.set_text_color(60, 60, 60)
            for o in opts[:6]:
                pdf.multi_cell(0, 6, f"Option: {o.get('label','')} → {o.get('outcome','')}")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    section("Handouts")
    for h in pack.get("handouts", []) or []:
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 6, h.get("title", ""))
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, h.get("content", ""))
        pdf.ln(2)

    pdf.output(str(output_pdf))


def write_flowchart_mermaid(*, pack: dict[str, Any], output_path: Path) -> None:
    nodes = ((pack.get("decision_flow") or {}).get("nodes")) or []
    mermaid = _mermaid_flowchart(nodes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(mermaid, encoding="utf-8")


def write_flowchart_dot(*, pack: dict[str, Any], output_path: Path) -> None:
    nodes = ((pack.get("decision_flow") or {}).get("nodes")) or []
    dot = _dot_flowchart(nodes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dot, encoding="utf-8")


def render_flowchart_graphviz(*, dot_path: Path, png_path: Path, pdf_path: Path) -> bool:
    """Render DOT to PNG+PDF if Graphviz is installed (dot on PATH)."""
    dot_exe = shutil.which("dot")
    if not dot_exe:
        return False

    png_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run([dot_exe, "-Tpng", str(dot_path), "-o", str(png_path)], check=True)
    subprocess.run([dot_exe, "-Tpdf", str(dot_path), "-o", str(pdf_path)], check=True)
    return True
