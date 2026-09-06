# hera-code

The application: the terminal, and the wiring that makes one.

It is the only layer that knows every other one exists. It reads the settings, seeds `~/.hera` and
`~/.hera/code`, builds a provider from a registered endpoint, mounts `hera_code_mcp` into
`hera_tools`, composes the working tree and the todo list into the prompt's project slot, hands
the lot to `hera_chats.TurnOrchestrator`, and draws what comes back.

Everything under `packages/` is a library something else could use. This is the thing that could
not.

```bash
hera-code                     # the terminal
hera-code -p "explain this"   # one turn, printed, no terminal
hera-code init                # prepare ~/.hera and ~/.hera/code
hera-code check               # report whether the data directories are usable
```

| | |
|---|---|
| `cli.py` | Four verbs, argparse, no framework |
| `boot.py` | Seeds the shared `~/.hera` and hera-code's own `~/.hera/code` |
| `wiring.py` | Assembles provider · builder · router · registry · orchestrator |
| `context.py` | Composes `SLOT_PROJECT` from the working tree, the todos, the shadow tree and the graph |
| `session.py` | A session is a `hera_chats.Chat`; runs one turn and persists it |
| `tui/` | The dock, the transcript, the gutter, the cards, the ocellus, the theme |
| `migrations/` | Alembic. Only here is every package imported, so only here does autogenerate see the whole schema |

The design language the `tui/` package builds is [`docs/tui.md`](../../docs/tui.md), and it is not
a suggestion — a renderer that invents a colour meaning is a bug in the same way a wrong `if` is.

**Everything hera-code redirects is injectable, so no vendored package is edited.**
`StorageSettings.url` points the database at `~/.hera/code/sessions.sqlite3`;
`ToolsSettings.config_path` and `MindRepository(path=...)` are left at their defaults, which is
the shared `~/.hera`. See [`packages/VENDOR.md`](../../packages/VENDOR.md).

The version is declared here and read back from packaging by `hera_code.__version__`, so
`--version` and a release tag cannot disagree — `release.yml` refuses a tag that does not match.
