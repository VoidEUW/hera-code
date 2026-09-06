"""The MCP server hera-code **is**, as opposed to the ones it can reach.

Its own tools — reading and editing a working tree, a shell, and ``ask`` — on a real
``MCPServer``. The application mounts it in-process through ``hera_tools``, which reaches it with
the same client it reaches a filesystem server with, lists it in the same catalogue and checks it
with the same policy.

The arrangement is hera's, and there are three positions in it rather than two:

===============  =========================================================================
``hera_mcp``     the server **hera** is — hers, and not vendored here
``hera_tools``   the client hera-code **has** — mounts any server, knows nothing about ours
this package     the server hera-code **is**, and in v0.3.0 the one **hera reaches**
===============  =========================================================================

That last column is why this is a package rather than a module inside the application. In v0.3.0
it is served over a transport of its own so hera can drive a coding agent running elsewhere, and
the only thing that should change then is which transport — not what the tools are.

**It imports no other package in this workspace and never will.** What it needs from the rest of
the system arrives as :mod:`hera_code_mcp.ports`. That is what keeps it servable over anything,
and ``tests/test_layering.py`` gives it an empty allow-list so the claim is checked rather than
trusted.

``ASK_TOOL`` and ``BUILTIN_SERVER_NAME`` are exported for the reason ``hera_mcp`` exports its
equivalents: ``hera_chats`` recognises the asking tool by name and suspends the turn, and
``hera_tools`` mounts a server under its own name. Neither may import this package, so the
application reads the constants and makes them agree.

The tool descriptions are prompt text. Edit them and the agent's behaviour changes.
"""

from __future__ import annotations

from hera_code_mcp.ports import Files, FileText, Match, Ran, Shell
from hera_code_mcp.server import (
    ASK_KINDS,
    ASK_TOOL,
    BASH_TIMEOUT_S,
    BUILTIN_SERVER_NAME,
    GLOB_LIMIT,
    GREP_LIMIT,
    READ_LIMIT,
    TOOL_NAMES,
    AskKind,
    build_server,
)

__all__ = [
    "ASK_KINDS",
    "ASK_TOOL",
    "BASH_TIMEOUT_S",
    "BUILTIN_SERVER_NAME",
    "GLOB_LIMIT",
    "GREP_LIMIT",
    "READ_LIMIT",
    "TOOL_NAMES",
    "AskKind",
    "FileText",
    "Files",
    "Match",
    "Ran",
    "Shell",
    "build_server",
]
