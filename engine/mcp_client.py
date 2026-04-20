"""
MCP Client — Lightweight client for Stellaris MCP tool servers.

Connects to MCP servers via stdio transport and calls their tools.
Designed for **dev-time enrichment** (validating meta, fetching wiki data),
NOT for runtime LLM prompts (meta must remain curated per project rules).

Supported servers:
  - stellaris-wiki-mcp  → wiki_game_data, wiki_search, wiki_patch_notes
  - stellaris-save-mcp  → save_empires, save_empire_detail, game_version

Usage:
    client = MCPClient("node", ["path/to/stellaris-wiki-mcp/build/index.js"])
    result = client.call_tool("wiki_game_data", {"type": "origins"})
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# JSON-RPC 2.0 message ID counter
_MSG_ID = 0


def _next_id() -> int:
    global _MSG_ID
    _MSG_ID += 1
    return _MSG_ID


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""

    tool_name: str
    content: list[dict]
    is_error: bool = False
    raw_response: dict | None = None

    @property
    def text(self) -> str:
        """Extract text content from the first content block."""
        for block in self.content:
            if block.get("type") == "text":
                return block.get("text", "")
        return ""

    @property
    def data(self) -> object:
        """Try to parse text content as JSON, return raw text on failure."""
        text = self.text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text


class MCPClient:
    """Connects to an MCP server via stdio and calls tools.

    The server process is started on first use and kept alive for the
    session.  Call ``close()`` to terminate it.
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env
        self._timeout_s = timeout_s
        self._process: subprocess.Popen | None = None
        self._initialized = False

    def _ensure_started(self) -> None:
        """Start the MCP server process if not already running."""
        if self._process is not None and self._process.poll() is None:
            return

        cmd = [self._command, *self._args]
        log.info("Starting MCP server: %s", " ".join(cmd))
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
        )
        self._initialized = False

    def _send_message(self, message: dict) -> dict:
        """Send a JSON-RPC message and read the response."""
        self._ensure_started()

        payload = json.dumps(message) + "\n"
        self._process.stdin.write(payload.encode())
        self._process.stdin.flush()

        # Read response line
        line = self._process.stdout.readline()
        if not line:
            raise ConnectionError("MCP server closed stdout")

        return json.loads(line.decode())

    def _initialize(self) -> None:
        """Send the MCP initialize handshake."""
        if self._initialized:
            return

        response = self._send_message({
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "stellaris-overmind",
                    "version": "1.0.0",
                },
            },
        })

        if "error" in response:
            raise ConnectionError(f"MCP init failed: {response['error']}")

        # Send initialized notification
        self._send_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        self._initialized = True
        log.info("MCP server initialized")

    def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        self._initialize()
        response = self._send_message({
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": "tools/list",
        })
        return response.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> MCPToolResult:
        """Call a tool on the MCP server and return the result."""
        self._initialize()
        response = self._send_message({
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        })

        result = response.get("result", {})
        content = result.get("content", [])
        is_error = result.get("isError", False)

        return MCPToolResult(
            tool_name=tool_name,
            content=content,
            is_error=is_error,
            raw_response=response,
        )

    def close(self) -> None:
        """Terminate the MCP server process."""
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
            self._initialized = False
            log.info("MCP server terminated")

    def __enter__(self) -> MCPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def create_wiki_client(
    server_path: str | Path,
) -> MCPClient:
    """Create an MCP client for the stellaris-wiki-mcp server.

    Parameters
    ----------
    server_path : str | Path
        Path to the built server entry point, e.g.
        ``../stellaris-wiki-mcp/build/index.js``
    """
    return MCPClient("node", [str(server_path)])


def create_save_client(
    server_path: str | Path,
    save_dir: str = "",
    localization_dir: str = "",
) -> MCPClient:
    """Create an MCP client for a stellaris-save-mcp server.

    Parameters
    ----------
    server_path : str | Path
        Path to the server binary or entry point.
    save_dir : str
        Stellaris save games directory.
    localization_dir : str
        Path to Stellaris localization/english directory.
    """
    args = [str(server_path)]
    if save_dir:
        args.append(save_dir)
    if localization_dir:
        args.append(localization_dir)
    return MCPClient(args[0], args[1:])
