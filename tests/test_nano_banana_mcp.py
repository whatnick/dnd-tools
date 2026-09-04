from __future__ import annotations

import base64
from pathlib import Path

import requests

from src.image_generation.campaign_visuals import build_campaign_visual_briefs
from src.image_generation.nano_banana_mcp import NanoBananaMcpClient


def _response(
    payload: str,
    *,
    content_type: str = "text/event-stream",
    session_id: str | None = None,
    status: int = 200,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = payload.encode()
    response.headers["Content-Type"] = content_type
    if session_id:
        response.headers["Mcp-Session-Id"] = session_id
    return response


class FakeSession:
    def __init__(self, responses: list[requests.Response]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def post(self, url: str, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.responses.pop(0)

    def delete(self, url: str, **kwargs):
        self.requests.append({"url": url, "method": "DELETE", **kwargs})
        return _response("", content_type="application/json", status=204)


def test_streamable_http_session_and_inline_image(tmp_path: Path) -> None:
    image_data = b"test-image"
    session = FakeSession(
        [
            _response(
                'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18"}}\n\n',
                session_id="session-1",
            ),
            _response("", status=202),
            _response(
                "data: "
                + '{"jsonrpc":"2.0","id":2,"result":{"content":['
                + '{"type":"text","text":"generated"},'
                + '{"type":"image","data":"'
                + base64.b64encode(image_data).decode()
                + '","mimeType":"image/png"}],"isError":false}}\n\n'
            ),
        ]
    )
    destination = tmp_path / "campaign.png"
    client = NanoBananaMcpClient(
        "http://nano-banana:3000/mcp", session=session  # type: ignore[arg-type]
    )

    client.initialize()
    metadata = client.generate_image(prompt="a castle", destination=destination)

    assert destination.read_bytes() == image_data
    assert metadata["mime_type"] == "image/png"
    assert session.requests[1]["headers"]["Mcp-Session-Id"] == "session-1"
    assert session.requests[2]["json"]["params"]["name"] == "generate_image"


def test_visual_briefs_apply_shared_limit() -> None:
    pack = {
        "locations": [{"name": "Keep", "summary": "On a cliff"}],
        "scenes": [{"title": "Arrival", "location": "Keep", "setup": "A storm"}],
    }

    briefs = build_campaign_visual_briefs(pack, mode="both", max_images=2)

    assert [(brief.subject_kind, brief.subject_name) for brief in briefs] == [
        ("location", "Keep"),
        ("scene", "Arrival"),
    ]
