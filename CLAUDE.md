# CLAUDE.md — hera-code

A map of this repository, not a changelog. Keep it short: hera's predecessor of this file grew to
98 KB and stopped being readable. `tests/test_docs.py` fails above 16 KB — when it does, move a
section into `docs/`.

hera-code is a terminal coding agent, built on [hera](https://github.com/VoidEUW/hera)'s packages:
a uv workspace, nine vendored libraries, six of its own, and one application under `apps/cli`.

## Read first

- `docs/status.md` — where the build stands, what is settled, what is next. **Start here**
- `docs/versions/` — one file per version, written before the work. Read the one you are working
  on before touching its packages. The **milestones and issues are the plan**; these say why
- `ARCHITECTURE.md` — the packages, the layering rule, the shape of a turn, what is on disk
- `docs/adr/` — why the structure looks like this. Read **1** (vendoring) before touching anything
  under `packages/hera_*` that is not `hera_code_*`; **2**, **4** and **9** before changing
  model-facing behaviour; **3** before touching the terminal
- `docs/tui.md` — the design language of the terminal, converted from hera's `docs/frontend.md`
- `docs/tooling.md` — what a coding agent should reach for and cannot. Notes, not decisions; read
  § 2 before concluding it has no web search by accident
- `CONTRIBUTING.md` — setup, the check loop, branching, tags, refreshing a vendored package

## Commands

```bash
uv sync --all-packages
uv run ruff check . && uv run ruff format --check .
uv run mypy                                         # strict
uv run coverage run -m pytest && uv run coverage report
uv run pytest tests/                                # the four meta-tests
uv run hera-code
```

`-m "not live"` is the fast loop. `live` marks anything needing a real model endpoint; it never
runs in CI.

## Rules that are not negotiable

**A vendored package is not edited.** Nine of the directories under `packages/` are byte-identical
copies of hera's — `packages/VENDOR.md` names them and `tests/test_vendor.py` fails if one
changes. A fix goes upstream and the copy is refreshed. Everything hera-code needs to redirect is
already injectable; if you find something that is not, that is [ADR 1](docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md)
to re-open, not a file to patch.

**Imports point downwards.** The table in `ARCHITECTURE.md` is the authority and
`tests/test_layering.py` enforces it. `hera_storage`, `hera_prompts` and `hera_code_mcp` import no
other package here. The first two are hera's promise that they are liftable into an unrelated
project — **this is that project**, and those empty allow-lists are the only place that claim gets
tested rather than asserted.

**Three MCP positions, and the difference matters.** `hera_code_mcp` is the server it **is** —
files, shell, graph, todos, the shadow tree, `ask` — and everything it needs arrives as a port, so
it imports nothing of ours. `hera_tools` is the client it **has**, and it does not know the other
exists; it mounts whatever in-process server the application hands it, under that server's own
name. The third is v0.3.0: the same server over a transport, so **hera** can reach it. `hera_mcp`
is hers and is deliberately not vendored.

**`ask` is never run.** `hera_chats` recognises it by name (`ChatsSettings.asking_tools`, filled in
by the application from `hera_code_mcp.ASK_TOOL`) and suspends the turn the way a permission card
does, so a person's reply becomes that call's result. This is what the intake conversation is made
of.

**A tool learns which session it is in from `_meta`, never from an argument.** The model chooses
arguments, so a `session_id` field is one it would invent; a `ctx: Context` parameter is kept out
of the schema by the SDK. A `contextvars.ContextVar` does **not** work here and does not fail
either: every call runs in a worker task created when the server connected, so it reads back
empty. hera's ADR 12.

**One event union.** `hera_providers` says what a model can emit; `hera_chats.ChatEvent` wraps it
and adds what a *turn* contains. If you are writing a parser for model output, something is wrong —
the answer is almost always a tool call.

**No parser in the terminal.** It renders event variants it is handed, one renderer per variant,
and an unknown one degrades **visibly**. Typesetting Markdown is not that parser and may not become
one. This is the single largest source of bugs in hera's previous generation and it is designed
out.

**The persisted render is authoritative** at `turn_closed`. And in scrollback that is a re-print,
not a repaint — streaming output has to be correct as it goes, because there is no going back.

**The transcript belongs to the terminal.** Never take the alternate screen buffer, never repaint
above the dock, and `hera-code -p "…" | cat` must produce plain text.
[ADR 3](docs/adr/0003-the-transcript-lives-in-scrollback.md).

**Skill selection is code.** Never build anything that depends on the model noticing something is
relevant — the todo list, the shadow tree and the graph are all built on that. hera's ADR 5.

**English everywhere** — code, comments, commits, prompts, stored content, terminal strings.

**Tables** carry a package-prefixed `__tablename__`; cross-package references are bare `UUID`
columns, never `ForeignKey`; migrations live in `apps/cli`.

## The three project files

hera-code writes into `<working tree>/.hera/`, and each of the three makes a different promise —
[ADR 7](docs/adr/0007-the-working-trees-hera-directory-is-readable.md).

| | |
|---|---|
| `TODOS.md` | The run's red line. Markdown, four states, stable ids. **A person may edit it mid-run and the next turn follows it.** Parsing is total — a line we do not understand is kept and reported, never dropped |
| `shadow/<path>.md` | One note per source file. **Delivered with its file, never fetched** ([ADR 9](docs/adr/0009-a-shadow-note-is-delivered-with-its-file.md)) — a note the model has to remember to ask for is one that does not get read |
| `sketches/` · `thoughts/` | Not tied to a path, so they arrive as an **index** — title and one line each — and the model reaches for one |

Whether any of it is committed is the person's call. **hera-code never edits a `.gitignore`.**

## What is shared with hera, and what is not

`~/.hera/mind/`, `~/.hera/skills/`, `~/.hera/mcp.json` and `~/.hera/config.toml` are **shared**;
hera-code creates them if no hera install has, and overwrites nothing.
`~/.hera/code/` is hera-code's alone — sessions, its own config, the graph cache.

## Agent instruction files

hera-code reads `AGENT.md`, `AGENTS.md` **and** `CLAUDE.md` at a working tree's root — every one
that exists — so a repository already set up for another coding agent needs no new file. They
compose into `SLOT_PROJECT`, which is `hera_profiles`' own slot and means *what we are working on*.
That seam is why no vendored package needed changing.

Commit and push only when asked. Branch first — `main` is protected.
