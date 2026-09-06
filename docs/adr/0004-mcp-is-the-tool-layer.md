# 4. MCP is the tool layer, and `hera_code_mcp` is the server hera-code is

- Status: accepted
- Date: 2026-09-06

## Context

hera-code needs tools a chat assistant has no business having: reading and editing a working tree,
a shell, a code index, a todo list. It also inherits `hera_tools`, hera's MCP **client**, which
already handles server lifecycle, a namespaced catalogue, dispatch, timeouts and the rule that a
failed call is a `ToolResult` rather than an exception.

hera's [ADR 4](https://github.com/VoidEUW/hera/blob/main/docs/adr/0004-mcp-as-the-tool-layer.md)
settled the shape: her own capabilities live in `hera_mcp` as a real MCP server, mounted
in-process by the application through the same client that reaches a filesystem server, listed in
the same catalogue, checked by the same policy. It gives one reason for that, and it is the reason
that matters here: a special case would have to be unpicked the moment the server is exposed to
another agent.

For hera-code that moment is a planned milestone, not a hypothetical. The user's requirement is
that hera should be able to drive hera-code — remote control, in the way Claude Code can be driven
by something else.

## Decision

Tools are MCP. hera-code's own capabilities live in **`hera_code_mcp`**, a real `MCPServer`
mounted in-process under its own name, `code`, so its tools are `code__read`, `code__edit`,
`code__bash`.

There are **three** positions in the arrangement, and naming all three keeps the first two from
blurring:

| | |
|---|---|
| `hera_mcp` | the server **hera** is. Hers, not vendored here, and never mounted by hera-code |
| `hera_tools` | the client hera-code **has**. Mounts any server, and does not know ours exists |
| `hera_code_mcp` | the server hera-code **is** — and, in v0.3.0, the one **hera reaches** |

`hera_code_mcp` **imports no other package in this workspace**, exactly as `hera_mcp` does not.
Everything it needs — the working tree, the todo list, the graph — arrives as a port. That is not
tidiness: it is the only thing that makes serving it over a transport a change of transport rather
than a rewrite.

Two constants are exported rather than agreed on twice, for the reason hera exports them:
`BUILTIN_SERVER_NAME`, because `hera_tools` mounts a server under `server.name`; and `ASK_TOOL`,
because `hera_chats` suspends a turn on that name and may not learn what hera-code's tools are —
the application reads the constant and fills in `ChatsSettings.asking_tools`.

**Hera's tools are not mounted.** `hera_mcp` is deliberately not vendored. `remember`, `forget`
and a chat scratchpad are hers; a coding agent given them would have two memories that disagree.

## Consequences

- **The default policy is where a coding agent differs from a chat one, and it is decided before
  anything is wired.** `hera__*` is allowed without a card in hera because it is bounded; nothing
  about that reasoning survives a tool with a shell in it. The seed is: navigate and read `allow`,
  write and edit `ask`, `bash` `ask`, anything outside the working tree `deny`. Editable, and
  **Always allow** writes a rule.
- **A tool learns which session it is in from `_meta`, never from an argument.** Inherited whole
  from hera's [ADR 12](https://github.com/VoidEUW/hera/blob/main/docs/adr/0012-a-chat-has-a-scratchpad.md):
  the model chooses arguments, so a `session_id` field is one it would invent, while a
  `ctx: Context` parameter is kept out of the schema by the SDK. A `contextvars.ContextVar` does
  not work here and does not fail either — every call runs in a worker task created when the server
  connected, so it reads back empty. That trap is worth inheriting the knowledge of.
- **v0.3.0 is a transport and a permission decision, not a feature.** hera already reads
  `~/.hera/mcp.json` and `hera_tools` already mounts whatever it finds there, so hera reaching
  hera-code should need **no change in hera at all**. That claim is what the v0.3.0 M1 milestone
  exists to verify rather than assume.
- Tool descriptions are prompt text. They live in this package, and editing one changes the
  agent's behaviour — which is why they are somewhere a diff can show them rather than in a
  template string in the application.
