from __future__ import annotations

import io
import json
from typing import Any, TextIO

from llm_to_3dprint.bambu_mcp_server import (
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    call_mcp_tool,
    handle_mcp_request,
    main,
    serve_stdio,
)


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    return handle_mcp_request(message)


def run_stdio_server(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    source = input_stream or io.TextIOWrapper(io.BufferedReader(io.FileIO(0, "rb")), encoding="utf-8")
    sink = output_stream or io.TextIOWrapper(io.BufferedWriter(io.FileIO(1, "wb")), encoding="utf-8")
    for raw_line in source:
        line = raw_line.strip()
        if not line:
            continue
        response = handle_mcp_request(json.loads(line))
        if response is None:
            continue
        sink.write(json.dumps(response) + "\n")
        sink.flush()


def run_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    input_buffer = io.StringIO("".join(json.dumps(message) + "\n" for message in messages))
    output_buffer = io.StringIO()
    run_stdio_server(input_buffer, output_buffer)
    output_buffer.seek(0)
    return [json.loads(line) for line in output_buffer.read().splitlines() if line.strip()]


__all__ = [
    "MCP_PROTOCOL_VERSION",
    "SERVER_NAME",
    "call_mcp_tool",
    "handle_message",
    "handle_mcp_request",
    "main",
    "run_messages",
    "run_stdio_server",
    "serve_stdio",
]


if __name__ == "__main__":
    main()
