# hera-code-mcp

The MCP server hera-code **is**, as opposed to the ones it can reach. There are three positions in
this arrangement, and keeping them apart is what makes the third one possible:

| | |
|---|---|
| `hera_mcp` | the server **hera** is — hers, and not vendored here |
| `hera_tools` | the client hera-code **has** — mounts any server, knows nothing about ours |
| `hera_code_mcp` | the server hera-code **is**, and in v0.3.0 the one **hera reaches** |

| Group | Tools |
|---|---|
| Files | `read` · `write` · `edit` · `glob` · `grep` |
| Shell | `bash` |
| Graph | `graph_outline` · `graph_find` · `graph_neighbours` · `graph_path` |
| Todos | `todo_read` · `todo_write` · `todo_set` |
| Shadow | `note_write` · `note_read` · `sketch_write` · `thought_write` |
| Person | `ask` — the one that is never run |

**It imports no other package in this workspace and never will.** What it needs arrives as ports,
the way `hera_mcp.ports` does it. That is what keeps it servable over any transport, which is the
whole of the v0.3.0 milestone.

The tool descriptions are prompt text. Edit them and the agent's behaviour changes.

Landing in **v0.1.0 M2** (files, shell, `ask`) and **M4** (todos); graph and shadow in v0.2.0.
