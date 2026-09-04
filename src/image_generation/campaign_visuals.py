from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CampaignVisualBrief:
    subject_kind: str
    subject_name: str
    prompt: str
    metadata: dict[str, str]


def build_campaign_visual_briefs(
    pack: dict[str, Any],
    *,
    mode: str,
    max_images: int,
) -> list[CampaignVisualBrief]:
    briefs: list[CampaignVisualBrief] = []
    if mode in {"location", "both"}:
        for location in pack.get("locations") or []:
            name = (location.get("name") or "Location").strip() or "Location"
            summary = (location.get("summary") or "").strip()
            briefs.append(
                CampaignVisualBrief(
                    subject_kind="location",
                    subject_name=name,
                    prompt=(
                        f"Fantasy top-down map illustration of {name}, highly detailed, "
                        f"parchment style, ink lines, readable pathways, no text. {summary}"
                    ),
                    metadata={"location": name},
                )
            )
            if len(briefs) >= max_images:
                return briefs
    if mode in {"scene", "both"}:
        for scene in pack.get("scenes") or []:
            title = (scene.get("title") or "Scene").strip() or "Scene"
            location = (scene.get("location") or "").strip()
            setup = (scene.get("setup") or "").strip()
            briefs.append(
                CampaignVisualBrief(
                    subject_kind="scene",
                    subject_name=title,
                    prompt=(
                        "Fantasy scene illustration, cinematic lighting, highly detailed, "
                        f"{title}, at {location}. {setup}"
                    ),
                    metadata={"scene": title},
                )
            )
            if len(briefs) >= max_images:
                break
    return briefs

