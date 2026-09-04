from __future__ import annotations

import os
from pathlib import Path
import random

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from src.ai_tools.generator import DnDGenerator
from src.domain.actors import AbilityScores, CharacterSheet, MonsterSheet
from src.image_processing.portrait_pdf_gen import generate_pdf_from_dir
from src.map_making.generator import generate_simple_map
from src.workflows.campaign_pack import (
    build_campaign_pack_json,
    write_campaign_pack_pdf,
    write_flowchart_dot,
    write_flowchart_mermaid,
    render_flowchart_graphviz,
)
from src.image_generation.comfyui import (
    build_txt2img_workflow,
    download_image,
    is_configured as comfy_is_configured,
    queue_prompt,
    wait_for_result_image,
)
from src.image_generation.campaign_visuals import build_campaign_visual_briefs
from src.image_generation.nano_banana_mcp import NanoBananaMcpClient

from . import db
from .paths import campaign_artifacts_dir, campaign_uploads_dir


load_dotenv()

app = FastAPI(title="D&D Tools (Local)")

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _selected_image_providers(
    comfy_url: str | None,
    nano_banana_url: str | None,
) -> set[str]:
    configured = (os.getenv("CAMPAIGN_IMAGE_PROVIDERS") or "auto").strip().lower()
    if configured == "auto":
        providers = set()
        if comfy_url:
            providers.add("comfyui")
        if nano_banana_url:
            providers.add("nano-banana")
        return providers
    if configured in {"", "none", "disabled"}:
        return set()
    if configured == "both":
        return {"comfyui", "nano-banana"}
    return {
        provider.strip()
        for provider in configured.split(",")
        if provider.strip() in {"comfyui", "nano-banana"}
    }


@app.get("/api/image-providers")
def image_providers() -> dict[str, object]:
    comfy_url = os.getenv("COMFYUI_BASE_URL")
    nano_banana_url = os.getenv("NANO_BANANA_MCP_URL")
    selected = _selected_image_providers(comfy_url, nano_banana_url)
    return {
        "selected": sorted(selected),
        "comfyui": {
            "configured": bool(comfy_url and os.getenv("COMFYUI_CHECKPOINT")),
            "base_url": comfy_url,
        },
        "nano_banana": {
            "configured": bool(nano_banana_url),
            "endpoint": nano_banana_url,
        },
    }


@app.get("/campaigns", response_class=HTMLResponse)
def campaigns_page(request: Request):
    campaigns = db.list_campaigns()
    return templates.TemplateResponse(
        "campaigns.html", {"request": request, "campaigns": campaigns}
    )


@app.post("/campaigns", response_class=HTMLResponse)
def create_campaign(request: Request, name: str = Form(...)):
    db.create_campaign(name=name)
    campaigns = db.list_campaigns()
    return templates.TemplateResponse(
        "partials/campaign_list.html", {"request": request, "campaigns": campaigns}
    )


@app.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(request: Request, campaign_id: str):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    artifacts = db.list_artifacts(campaign_id)
    jobs = db.list_jobs(campaign_id)
    characters = db.list_actors(campaign_id, kind="character")
    monsters = db.list_actors(campaign_id, kind="monster")

    return templates.TemplateResponse(
        "campaign_detail.html",
        {
            "request": request,
            "campaign": campaign,
            "artifacts": artifacts,
            "jobs": jobs,
            "characters": characters,
            "monsters": monsters,
        },
    )


def _render_artifact_list(request: Request, campaign_id: str):
    artifacts = db.list_artifacts(campaign_id)
    return templates.TemplateResponse(
        "partials/artifact_list.html",
        {"request": request, "artifacts": artifacts},
    )


def _render_job_list(request: Request, campaign_id: str):
    jobs = db.list_jobs(campaign_id)
    return templates.TemplateResponse(
        "partials/job_list.html", {"request": request, "jobs": jobs}
    )


def _render_actor_list(request: Request, campaign_id: str, kind: str):
    actors = db.list_actors(campaign_id, kind=kind)
    return templates.TemplateResponse(
        "partials/actor_list.html",
        {"request": request, "actors": actors, "actor_kind": kind},
    )


def _require_campaign(campaign_id: str) -> None:
    if db.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")


def _ability_scores(
    strength: int,
    dexterity: int,
    constitution: int,
    intelligence: int,
    wisdom: int,
    charisma: int,
) -> AbilityScores:
    return AbilityScores(
        strength=strength,
        dexterity=dexterity,
        constitution=constitution,
        intelligence=intelligence,
        wisdom=wisdom,
        charisma=charisma,
    )


def _lines(value: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in value.splitlines() if line.strip())


@app.get("/actors/{actor_id}.json")
def export_actor(actor_id: str):
    actor = db.get_actor(actor_id)
    if actor is None:
        raise HTTPException(status_code=404, detail="Actor not found")
    return JSONResponse(actor.data)


@app.post("/campaigns/{campaign_id}/characters", response_class=HTMLResponse)
def create_character(
    request: Request,
    campaign_id: str,
    name: str = Form(...),
    ancestry: str = Form(...),
    class_name: str = Form(...),
    level: int = Form(...),
    armor_class: int = Form(...),
    hit_point_max: int = Form(...),
    strength: int = Form(...),
    dexterity: int = Form(...),
    constitution: int = Form(...),
    intelligence: int = Form(...),
    wisdom: int = Form(...),
    charisma: int = Form(...),
    perception_proficient: bool = Form(False),
    notes: str = Form(""),
):
    _require_campaign(campaign_id)
    try:
        character = CharacterSheet(
            name=name,
            ancestry=ancestry,
            class_name=class_name,
            level=level,
            armor_class=armor_class,
            hit_point_max=hit_point_max,
            perception_proficient=perception_proficient,
            abilities=_ability_scores(
                strength,
                dexterity,
                constitution,
                intelligence,
                wisdom,
                charisma,
            ),
            notes=notes,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=error.errors(include_context=False),
        ) from error

    data = character.model_dump(mode="json")
    db.create_actor(
        campaign_id=campaign_id,
        kind=character.kind,
        name=character.name,
        schema_version=character.schema_version,
        data=data,
    )
    return _render_actor_list(request, campaign_id, "character")


@app.post("/campaigns/{campaign_id}/monsters", response_class=HTMLResponse)
def create_monster(
    request: Request,
    campaign_id: str,
    name: str = Form(...),
    size: str = Form(...),
    creature_type: str = Form(...),
    challenge_rating: float = Form(...),
    armor_class: int = Form(...),
    hit_point_max: int = Form(...),
    speed: str = Form(...),
    primary_ability: str = Form(...),
    strength: int = Form(...),
    dexterity: int = Form(...),
    constitution: int = Form(...),
    intelligence: int = Form(...),
    wisdom: int = Form(...),
    charisma: int = Form(...),
    traits: str = Form(""),
    actions: str = Form(""),
    notes: str = Form(""),
):
    _require_campaign(campaign_id)
    try:
        monster = MonsterSheet(
            name=name,
            size=size,
            creature_type=creature_type,
            challenge_rating=challenge_rating,
            armor_class=armor_class,
            hit_point_max=hit_point_max,
            speed=speed,
            primary_ability=primary_ability,
            abilities=_ability_scores(
                strength,
                dexterity,
                constitution,
                intelligence,
                wisdom,
                charisma,
            ),
            traits=_lines(traits),
            actions=_lines(actions),
            notes=notes,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=error.errors(include_context=False),
        ) from error

    data = monster.model_dump(mode="json")
    db.create_actor(
        campaign_id=campaign_id,
        kind=monster.kind,
        name=monster.name,
        schema_version=monster.schema_version,
        data=data,
    )
    return _render_actor_list(request, campaign_id, "monster")


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_row(request: Request, job_id: str):
    j = db.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse("partials/job_row.html", {"request": request, "j": j})


@app.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    artifact = db.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if artifact.file_path:
        path = Path(artifact.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File missing on disk")
        return FileResponse(path)

    # text artifact
    return HTMLResponse(
        f"<pre>{(artifact.text_content or '').replace('<', '&lt;')}</pre>",
        media_type="text/html",
    )


@app.post("/campaigns/{campaign_id}/generate/backstory", response_class=HTMLResponse)
def generate_backstory(
    request: Request,
    campaign_id: str,
    name: str = Form(...),
    race: str = Form(...),
    char_class: str = Form(...),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    gen = DnDGenerator()
    text = gen.generate_character_backstory(name, race, char_class)

    db.create_artifact(
        campaign_id=campaign_id,
        kind="text.backstory",
        title=f"Backstory: {name}",
        text_content=text,
        meta={"name": name, "race": race, "class": char_class},
    )

    return _render_artifact_list(request, campaign_id)


@app.post("/campaigns/{campaign_id}/generate/plot-hooks", response_class=HTMLResponse)
def generate_plot_hooks(
    request: Request,
    campaign_id: str,
    setting: str = Form("a small village"),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    gen = DnDGenerator()
    text = gen.generate_plot_hook(setting=setting)

    db.create_artifact(
        campaign_id=campaign_id,
        kind="text.plot_hooks",
        title=f"Plot hooks: {setting}",
        text_content=text,
        meta={"setting": setting},
    )

    return _render_artifact_list(request, campaign_id)


def _job_generate_campaign_pack(job_id: str, campaign_id: str, story_prompt: str) -> None:
    try:
        db.update_job(job_id=job_id, status="running", message="Designing campaign")

        out_dir = campaign_artifacts_dir(campaign_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        pack = build_campaign_pack_json(story_prompt=story_prompt)

        # Save JSON
        json_path = out_dir / f"campaign_pack_{job_id}.json"
        json_path.write_text(
            __import__("json").dumps(pack, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        json_artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.campaign_pack_json",
            title=f"Campaign pack JSON: {pack.get('title','')}",
            file_path=str(json_path),
            meta={"title": pack.get("title")},
        )

        # Flowchart sources
        db.update_job(job_id=job_id, status="running", message="Writing flowchart")

        flow_mmd_path = out_dir / f"decision_flow_{job_id}.mmd"
        write_flowchart_mermaid(pack=pack, output_path=flow_mmd_path)
        flow_mmd_artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.flowchart_mermaid",
            title="Decision flow (Mermaid)",
            file_path=str(flow_mmd_path),
            meta={},
        )

        flow_dot_path = out_dir / f"decision_flow_{job_id}.dot"
        write_flowchart_dot(pack=pack, output_path=flow_dot_path)
        flow_dot_artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.flowchart_dot",
            title="Decision flow (Graphviz DOT)",
            file_path=str(flow_dot_path),
            meta={},
        )

        # Optional render if Graphviz installed
        rendered = False
        try:
            flow_png_path = out_dir / f"decision_flow_{job_id}.png"
            flow_pdf_path = out_dir / f"decision_flow_{job_id}.pdf"
            rendered = render_flowchart_graphviz(
                dot_path=flow_dot_path,
                png_path=flow_png_path,
                pdf_path=flow_pdf_path,
            )
            if rendered:
                db.create_artifact(
                    campaign_id=campaign_id,
                    kind="file.flowchart_png",
                    title="Decision flow (PNG)",
                    file_path=str(flow_png_path),
                    meta={},
                )
                db.create_artifact(
                    campaign_id=campaign_id,
                    kind="file.flowchart_pdf",
                    title="Decision flow (PDF)",
                    file_path=str(flow_pdf_path),
                    meta={},
                )
        except Exception as e:
            # Rendering failure shouldn't kill the whole pack.
            db.create_artifact(
                campaign_id=campaign_id,
                kind="text.flowchart_render_warning",
                title="Flowchart render warning",
                text_content=str(e),
                meta={},
            )

        # Maps per location (simple draft maps)
        db.update_job(job_id=job_id, status="running", message="Generating maps")
        for loc in (pack.get("locations") or [])[:6]:
            name = (loc.get("name") or "location").strip() or "location"
            map_cfg = loc.get("map") or {}
            width = int(map_cfg.get("width") or 20)
            height = int(map_cfg.get("height") or 20)
            safe_name = "_".join(name.split())[:40]
            map_path = out_dir / f"map_{safe_name}_{width}x{height}_{job_id}.png"
            generate_simple_map(width=width, height=height, output_path=str(map_path))
            db.create_artifact(
                campaign_id=campaign_id,
                kind="file.map_png",
                title=f"Map: {name}",
                file_path=str(map_path),
                meta={"location": name, "width": width, "height": height},
            )

        # Optional providers consume the same campaign visual briefs.
        comfy_url = os.getenv("COMFYUI_BASE_URL")
        comfy_ckpt = os.getenv("COMFYUI_CHECKPOINT")
        nano_banana_url = os.getenv("NANO_BANANA_MCP_URL")
        providers = _selected_image_providers(comfy_url, nano_banana_url)
        briefs = []
        if providers:
            try:
                mode = (
                    os.getenv("CAMPAIGN_IMAGE_MODE")
                    or os.getenv("COMFYUI_MODE")
                    or "location"
                ).strip().lower()
                if mode not in {"location", "scene", "both"}:
                    raise ValueError(
                        "CAMPAIGN_IMAGE_MODE must be location, scene, or both"
                    )
                max_images = int(
                    os.getenv("CAMPAIGN_IMAGE_MAX_IMAGES")
                    or os.getenv("COMFYUI_MAX_IMAGES")
                    or 2
                )
                if not 1 <= max_images <= 10:
                    raise ValueError(
                        "CAMPAIGN_IMAGE_MAX_IMAGES must be between 1 and 10"
                    )
                briefs = build_campaign_visual_briefs(
                    pack,
                    mode=mode,
                    max_images=max_images,
                )
            except (TypeError, ValueError) as error:
                db.create_artifact(
                    campaign_id=campaign_id,
                    kind="text.image_provider_warning",
                    title="Campaign image configuration warning",
                    text_content=str(error),
                    meta={"providers": sorted(providers)},
                )
                providers = set()

        if "comfyui" in providers and comfy_is_configured() and comfy_ckpt:
            try:
                width = int(os.getenv("COMFYUI_WIDTH") or 768)
                height = int(os.getenv("COMFYUI_HEIGHT") or 768)
                steps = int(os.getenv("COMFYUI_STEPS") or 8)
                cfg = float(os.getenv("COMFYUI_CFG") or 4.0)

                db.update_job(
                    job_id=job_id,
                    status="running",
                    message="Generating illustrations (ComfyUI)",
                )

                negative = (
                    "low quality, blurry, watermark, text, signature, extra limbs, "
                    "worst quality, jpeg artifacts"
                )
                seed_base = random.randint(1, 2**31 - 1)
                for index, brief in enumerate(briefs):
                    filename_prefix = (
                        f"campaign_{campaign_id}_{brief.subject_kind}_{job_id}_{index}"
                    )
                    workflow = build_txt2img_workflow(
                        positive=brief.prompt,
                        negative=negative,
                        checkpoint=comfy_ckpt,
                        width=width,
                        height=height,
                        steps=steps,
                        cfg=cfg,
                        seed=seed_base + index,
                        filename_prefix=filename_prefix,
                    )
                    prompt_id = queue_prompt(workflow=workflow)
                    ref = wait_for_result_image(prompt_id=prompt_id, timeout_s=900)
                    out_path = (
                        out_dir
                        / f"{brief.subject_kind}_illustration_comfyui_{index}_{job_id}.png"
                    )
                    download_image(ref=ref, dest_path=out_path)
                    db.create_artifact(
                        campaign_id=campaign_id,
                        kind=f"file.{brief.subject_kind}_illustration_png",
                        title=f"{brief.subject_kind.title()} illustration: {brief.subject_name}",
                        file_path=str(out_path),
                        meta={
                            **brief.metadata,
                            "provider": "comfyui",
                            "prompt": brief.prompt,
                            "prompt_id": prompt_id,
                            "width": width,
                            "height": height,
                            "steps": steps,
                            "cfg": cfg,
                        },
                    )

            except Exception as e:
                db.create_artifact(
                    campaign_id=campaign_id,
                    kind="text.comfyui_warning",
                    title="ComfyUI image generation warning",
                    text_content=str(e),
                    meta={"comfyui_base_url": comfy_url},
                )
        elif "comfyui" in providers:
            db.create_artifact(
                campaign_id=campaign_id,
                kind="text.comfyui_warning",
                title="ComfyUI not configured (missing checkpoint)",
                text_content="Set COMFYUI_CHECKPOINT to a checkpoint filename available in ComfyUI (models/checkpoints).",
                meta={"comfyui_base_url": comfy_url},
            )

        if "nano-banana" in providers and nano_banana_url:
            try:
                resolution = os.getenv("NANO_BANANA_RESOLUTION") or "1K"
                aspect_ratio = os.getenv("NANO_BANANA_ASPECT_RATIO") or "1:1"
                thinking = os.getenv("NANO_BANANA_THINKING") or "minimal"
                timeout_s = float(os.getenv("NANO_BANANA_TIMEOUT_SECONDS") or 900)
                db.update_job(
                    job_id=job_id,
                    status="running",
                    message="Generating illustrations (Nano Banana MCP)",
                )
                with NanoBananaMcpClient(
                    nano_banana_url,
                    timeout_s=timeout_s,
                ) as client:
                    available_tools = {
                        tool.get("name") for tool in client.list_tools()
                    }
                    if "generate_image" not in available_tools:
                        raise RuntimeError(
                            "Nano Banana MCP does not advertise generate_image"
                        )
                    for index, brief in enumerate(briefs):
                        requested_path = (
                            out_dir
                            / f"{brief.subject_kind}_illustration_nano_banana_{index}_{job_id}"
                        )
                        result = client.generate_image(
                            prompt=brief.prompt,
                            destination=requested_path,
                            aspect_ratio=aspect_ratio,
                            resolution=resolution,
                            thinking=thinking,
                        )
                        db.create_artifact(
                            campaign_id=campaign_id,
                            kind=f"file.{brief.subject_kind}_illustration_image",
                            title=(
                                f"{brief.subject_kind.title()} illustration "
                                f"(Nano Banana): {brief.subject_name}"
                            ),
                            file_path=result["path"],
                            meta={
                                **brief.metadata,
                                "provider": "nano-banana",
                                "prompt": brief.prompt,
                                "mcp_tool": "generate_image",
                                "mcp_endpoint": nano_banana_url,
                                "mime_type": result["mime_type"],
                                "size_bytes": result["size_bytes"],
                                "resolution": resolution,
                                "aspect_ratio": aspect_ratio,
                                "thinking": thinking,
                            },
                        )
            except Exception as e:
                db.create_artifact(
                    campaign_id=campaign_id,
                    kind="text.nano_banana_warning",
                    title="Nano Banana image generation warning",
                    text_content=str(e),
                    meta={
                        "provider": "nano-banana",
                        "mcp_endpoint": nano_banana_url,
                    },
                )
        elif "nano-banana" in providers:
            db.create_artifact(
                campaign_id=campaign_id,
                kind="text.nano_banana_warning",
                title="Nano Banana not configured",
                text_content="Set NANO_BANANA_MCP_URL to the Streamable HTTP MCP endpoint.",
                meta={"provider": "nano-banana"},
            )

        # Printable PDF
        db.update_job(job_id=job_id, status="running", message="Writing printable PDF")
        pdf_path = out_dir / f"campaign_pack_{job_id}.pdf"
        write_campaign_pack_pdf(pack=pack, output_pdf=pdf_path)
        pdf_artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.campaign_pack_pdf",
            title="Campaign pack (Printable PDF)",
            file_path=str(pdf_path),
            meta={"title": pack.get("title")},
        )

        # Also store a quick text artifact for in-page viewing
        db.create_artifact(
            campaign_id=campaign_id,
            kind="text.campaign_pack_premise",
            title=f"Premise: {pack.get('title','Campaign pack')}",
            text_content=pack.get("premise", ""),
            meta={
                "starting_location": pack.get("starting_location"),
                "json_artifact_id": json_artifact.id,
                "flow_mermaid_artifact_id": flow_mmd_artifact.id,
                "flow_dot_artifact_id": flow_dot_artifact.id,
                "flow_rendered": rendered,
                "pdf_artifact_id": pdf_artifact.id,
            },
        )

        db.update_job(job_id=job_id, status="done", message="Done", result_artifact_id=pdf_artifact.id)
    except Exception as e:
        db.update_job(job_id=job_id, status="error", message=str(e))


@app.post("/campaigns/{campaign_id}/generate/campaign-pack", response_class=HTMLResponse)
def generate_campaign_pack(
    request: Request,
    background_tasks: BackgroundTasks,
    campaign_id: str,
    story_prompt: str = Form(...),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    job = db.create_job(campaign_id=campaign_id, kind="campaign_pack", status="queued", message="Queued")
    background_tasks.add_task(_job_generate_campaign_pack, job.id, campaign_id, story_prompt)

    return _render_job_list(request, campaign_id)


def _job_generate_map(job_id: str, campaign_id: str, width: int, height: int) -> None:
    try:
        db.update_job(job_id=job_id, status="running", message="Generating map")

        out_dir = campaign_artifacts_dir(campaign_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"map_{width}x{height}_{job_id}.png"

        generate_simple_map(width=width, height=height, output_path=str(out_path))

        artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.map_png",
            title=f"Map {width}×{height}",
            file_path=str(out_path),
            meta={"width": width, "height": height},
        )
        db.update_job(job_id=job_id, status="done", message="Done", result_artifact_id=artifact.id)
    except Exception as e:
        db.update_job(job_id=job_id, status="error", message=str(e))


@app.post("/campaigns/{campaign_id}/generate/map", response_class=HTMLResponse)
def generate_map(
    request: Request,
    background_tasks: BackgroundTasks,
    campaign_id: str,
    width: int = Form(20),
    height: int = Form(20),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    job = db.create_job(campaign_id=campaign_id, kind="map", status="queued", message="Queued")
    background_tasks.add_task(_job_generate_map, job.id, campaign_id, width, height)

    return _render_job_list(request, campaign_id)


@app.post("/campaigns/{campaign_id}/upload", response_class=HTMLResponse)
def upload_files(
    request: Request,
    campaign_id: str,
    files: list[UploadFile] = File(...),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    up_dir = campaign_uploads_dir(campaign_id)
    up_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        if not f.filename:
            continue
        dest = up_dir / Path(f.filename).name
        with dest.open("wb") as out:
            out.write(f.file.read())
        saved += 1

    return HTMLResponse(f"Uploaded {saved} file(s) to {up_dir}")


def _job_generate_portraits_pdf(job_id: str, campaign_id: str, columns: int, rows: int) -> None:
    try:
        db.update_job(job_id=job_id, status="running", message="Generating PDF")

        input_dir = campaign_uploads_dir(campaign_id)
        if not input_dir.exists():
            raise RuntimeError("No uploads directory; upload images first")

        out_dir = campaign_artifacts_dir(campaign_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"portraits_{columns}x{rows}_{job_id}.pdf"

        generate_pdf_from_dir(
            input_dir=input_dir,
            output_pdf=out_path,
            columns=columns,
            rows=rows,
        )

        artifact = db.create_artifact(
            campaign_id=campaign_id,
            kind="file.portraits_pdf",
            title=f"Portraits PDF ({columns}×{rows})",
            file_path=str(out_path),
            meta={"columns": columns, "rows": rows},
        )
        db.update_job(job_id=job_id, status="done", message="Done", result_artifact_id=artifact.id)
    except Exception as e:
        db.update_job(job_id=job_id, status="error", message=str(e))


@app.post("/campaigns/{campaign_id}/generate/portraits-pdf", response_class=HTMLResponse)
def generate_portraits_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    campaign_id: str,
    columns: int = Form(2),
    rows: int = Form(3),
):
    campaign = db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    job = db.create_job(
        campaign_id=campaign_id,
        kind="portraits_pdf",
        status="queued",
        message="Queued",
    )
    background_tasks.add_task(_job_generate_portraits_pdf, job.id, campaign_id, columns, rows)

    return _render_job_list(request, campaign_id)
