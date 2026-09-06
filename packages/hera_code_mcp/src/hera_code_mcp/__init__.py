"""The MCP server hera-code **is**, as opposed to the ones it can reach.

Its own tools — reading and editing a working tree, a shell, the graph, the todo list, the shadow
tree, and ``ask`` — on a real ``MCPServer``. The application mounts it in-process through
``hera_tools``, which reaches it with the same client it reaches a filesystem server with, lists
it in the same catalogue and checks it with the same policy.

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
the system arrives as ports, the way ``hera_mcp.ports`` does it. That is what keeps it servable
over anything.

``ASK_TOOL`` is exported for the reason ``hera_mcp`` exports it: ``hera_chats`` recognises the
asking tool by name and suspends the turn, and it may not learn what hera-code's tools are. The
application reads the constant and fills in ``ChatsSettings.asking_tools``, so the string is
written once and travels rather than being agreed on twice.

The tool descriptions are prompt text. The model reads them and nothing else explains what these
do, so they are written for it: short, imperative, and clear about when *not* to call.

Landing in **v0.1.0 M2** (files, shell and ``ask``) and **M4** (todos), with the graph and
shadow groups in v0.2.0.
"""

from __future__ import annotations

BUILTIN_SERVER_NAME = "code"
"""hera-code's tools are namespaced ``code__read``, ``code__edit``, ``code__bash``.

The name travels on the server object rather than being agreed on twice: ``hera_tools`` mounts
whatever it is handed under ``server.name``, so this constant is the only place the word is
written.
"""

ASK_TOOL = "ask"
"""The one tool here that is answered by a *person* rather than run.

Named as a constant because the layer that suspends the turn is ``hera_chats``, which does not
import this package and must not learn what its tools are.
"""

__all__ = ["ASK_TOOL", "BUILTIN_SERVER_NAME"]
