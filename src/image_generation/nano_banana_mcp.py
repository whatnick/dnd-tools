from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any

import requests


class McpError(RuntimeError):
    pass


class NanoBananaMcpClient:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_s: float = 900,
        session: requests.Session | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self.session = session or requests.Session()
        self.session_id: str | None = None
        self._request_id = 0

    def __enter__(self) -> NanoBananaMcpClient:
        self.initialize()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @staticmethod
    def _response_json(response: requests.Response) -> dict[str, Any]:
        content_type = response.headers.get("Content-Type", "")
        if "text/event-stream" not in content_type:
            value = response.json()
            if not isinstance(value, dict):
                raise McpError("MCP response was not a JSON object")
            return value

        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data:
                continue
            try:
                value = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and ("result" in value or "error" in value):
                return value
        raise McpError("MCP event stream did not contain a JSON-RPC response")

    def _post(
        self,
        payload: dict[str, Any],
        *,
        expect_response: bool = True,
    ) -> dict[str, Any] | None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        response = self.session.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        returned_session_id = response.headers.get("Mcp-Session-Id")
        if returned_session_id:
            self.session_id = returned_session_id
        if not expect_response:
            return None
        message = self._response_json(response)
        if "error" in message:
            error = message["error"]
            detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise McpError(detail)
        result = message.get("result")
        if not isinstance(result, dict):
            raise McpError("MCP response did not contain a result object")
        return result

    def initialize(self) -> dict[str, Any]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "dnd-tools", "version": "0.1.0"},
                },
            }
        )
        if not self.session_id:
            raise McpError("MCP server did not establish a session")
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            expect_response=False,
        )
        return result or {}

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
        )
        tools = (result or {}).get("tools")
        if not isinstance(tools, list):
            raise McpError("MCP tools/list response did not contain a tools list")
        return [tool for tool in tools if isinstance(tool, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if result is None:
            raise McpError(f"MCP tool {name} returned no result")
        if result.get("isError"):
            messages = [
                block.get("text", "")
                for block in result.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            raise McpError("\n".join(messages) or f"MCP tool {name} failed")
        return result

    def generate_image(
        self,
        *,
        prompt: str,
        destination: Path,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        thinking: str = "minimal",
    ) -> dict[str, Any]:
        result = self.call_tool(
            "generate_image",
            {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "thinking": thinking,
                "number_of_images": 1,
                "return_inline_image": True,
            },
        )
        image = next(
            (
                block
                for block in result.get("content", [])
                if isinstance(block, dict) and block.get("type") == "image"
            ),
            None,
        )
        if image is None:
            raise McpError("Nano Banana returned no inline image")
        encoded = image.get("data")
        if not isinstance(encoded, str):
            raise McpError("Nano Banana returned invalid image data")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise McpError("Nano Banana returned invalid base64 image data") from error
        mime_type = image.get("mimeType", "application/octet-stream")
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(mime_type, destination.suffix or ".img")
        destination = destination.with_suffix(suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {
            "path": str(destination),
            "mime_type": mime_type,
            "size_bytes": len(data),
            "session_id": self.session_id,
        }

    def close(self) -> None:
        if self.session_id:
            try:
                self.session.delete(
                    self.endpoint,
                    headers={"Mcp-Session-Id": self.session_id},
                    timeout=min(self.timeout_s, 10),
                )
            finally:
                self.session_id = None
