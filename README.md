<div align="center">

# ◉ hera-code

**A terminal coding agent with a todo list you can edit and a graph instead of a grep.**

</div>

---

> **Status: nothing works yet.** The repository skeleton and the design are in place; the first
> usable milestone is v0.1.0 M1. See [`docs/status.md`](docs/status.md) for exactly where the
> build stands, and [`docs/versions/v0.1.0.md`](docs/versions/v0.1.0.md) for what is coming.

hera-code is a coding agent in the register Claude Code and Codex CLI occupy: a terminal, a model,
tools that read and write a working tree, and skills. It is built on the libraries from
[hera](https://github.com/VoidEUW/hera) — the same model boundary, the same MCP client, the same
`SKILL.md` router, the same turn loop.

## What is different about it

**A todo list that steers, not one that decorates.** Before it plans, it asks — the questions that
change what gets built, answered inline. The list it writes with you is `<repo>/.hera/TODOS.md`:
Markdown, in your repository, **editable mid-run**. It is in the prompt every turn and pinned to
the bottom of the terminal the whole time.

**A shadow tree, so it thinks less next time.** One note per source file, mirroring your tree, and
the note comes back *with* the file rather than needing to be asked for. Plus `sketches/` for
half-formed plans and `thoughts/` for conclusions worth keeping.

**Navigation instead of reading.** A tree-sitter graph of files, symbols and the edges between
them, so *what calls this* is a query rather than eight `read` calls. It says how fresh it is,
because an index you cannot date is one the model will `grep` around.

**It reads the `CLAUDE.md` you already have.** `AGENT.md`, `AGENTS.md` and `CLAUDE.md` at the root,
every one that exists. No new file.

**Everything is a file you can open.** The mind is a git repository. Skills are Markdown
directories. Servers come from a JSON file you wrote. The todo list, the notes and the sketches are
in your repository — committed or ignored, your call, and hera-code never touches your
`.gitignore`.

## The terminal

The transcript goes into your terminal's real scrollback — your scroll wheel works, selection
works, `| less` works, and the conversation is still there after you exit. Only the dock is pinned.

```
  ◉  hera-code 0.1.0    ~/dev/myrepo  main ✱3                     coding

› add rate limiting to the api

┆◉ thought     read TODOS.md, 3 open                                    Show
┆▤ skill       fastapi                                        skill · pinned
┆◍ graph       api.routes → limiter                                  8 nodes
┆✎ todo        4 items written                                          12 ms

I'll add a token-bucket limiter in `app/middleware/limit.py`.

──────────────────────────────────────────────────────────────────────────
 ┆ TODOS  1/4   ▸ a2  add the token bucket                        ^T all
 ›  _
   ＋ coding                          ⏎ send   ⇧⏎ newline   ^C stop
──────────────────────────────────────────────────────────────────────────
```

Every skill it was given and why, every tool it called, every permission it wanted and every
failure it hit — down the left gutter, one eye each. The design is
[`docs/tui.md`](docs/tui.md), and the eye is Hera's: Argus had a hundred of them and never slept.

## Install

*Not yet — v0.1.0 M6. This is what it will be.*

```bash
curl -fsSL https://raw.githubusercontent.com/VoidEUW/hera-code/main/install.sh | sh
```

```powershell
irm https://raw.githubusercontent.com/VoidEUW/hera-code/main/install.ps1 | iex
```

A standalone binary per platform, from the GitHub release. No Python needed.

## Any OpenAI-compatible endpoint

There is no target model. Register endpoints in `~/.hera/code/config.toml`; several may be
registered and one is active. The minimum bar is native tool calling — an endpoint without it says
so rather than degrading into a text call grammar
([ADR 2](docs/adr/0002-any-openai-compatible-endpoint.md)).

## Its relationship to hera

hera is a self-hosted agentic chat space. hera-code is a second application on the same libraries,
in its own repository, with hera's packages vendored until they are published
([ADR 1](docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md)).

They **share** `~/.hera/mind/`, `~/.hera/skills/` and `~/.hera/mcp.json` — whichever runs first
creates them, and neither overwrites the other. hera-code keeps its own sessions and settings under
`~/.hera/code/`.

Two of hera's packages carry a claim that has never been tested: `hera_storage` and `hera_prompts`
"contain no domain concept at all and must stay liftable into an unrelated project". This is that
project, and `tests/test_layering.py` is where the claim gets checked rather than asserted.

In v0.3.0 it goes the other way: `hera-code serve` exposes its tools over MCP, and hera drives it —
remote control of a coding agent, which should need no change in hera at all.

## Development

```bash
uv sync --all-packages
uv run ruff check . && uv run mypy
uv run coverage run -m pytest && uv run coverage report
```

[`CONTRIBUTING.md`](CONTRIBUTING.md) for the branching and tag conventions,
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the packages and the layering rule,
[`CLAUDE.md`](CLAUDE.md) if you are an agent working in here.

## Licence

MIT. See [LICENSE](LICENSE).
