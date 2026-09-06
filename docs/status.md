# Status

Current state of the build, so a new session can start without re-reading history. A snapshot, not
a changelog — historical detail lives in `CHANGELOG.md` and full rationale in `versions/` and the
ADRs.

**Updated:** 2026-09-06 · **Version:** nothing tagged · **Strategy:** make it work, then make
it look right, then make it reachable

## Now: v0.1.0 M3 — the terminal

**M2 is done: it can do work.** `hera_code_mcp` is mounted as `code`, so a turn can read, search,
write, edit and run commands inside the working tree — and `AGENT.md`/`AGENTS.md`/`CLAUDE.md` reach
the prompt. What is missing is the interactive part: a permission card cannot be *drawn* yet, so
anything that changes a file suspends the turn until M3, or runs under `--yes`.

| | |
|---|---|
| Tools | `read` · `write` · `edit` · `glob` · `grep` · `bash` · `ask`, namespaced `code__` |
| The guard | One containment check, `Workspace.resolve`, symlinks resolved before comparing |
| The policy | [ADR 11](adr/0011-the-default-policy-and-what-ask-means-with-nobody-there.md): reads allow, changes ask, outside the tree deny — and `--yes` cannot reach a deny |
| Instructions | All three filenames, read **every turn** so a mid-session edit is followed |

## Done: v0.1.0 M1 — the spine

**A turn runs end to end.** `hera-code init` seeds both data directories, `check`
reports whether they are usable, and `hera-code -p "…"` sends one turn to a configured endpoint and
prints the answer. There is no terminal yet (M3) and no tools yet (M2), so what it can do is
*answer*, not *work*.

| | |
|---|---|
| `init` | Seeds the shared `~/.hera` — mind, skills, `mcp.json` — and `~/.hera/code`. Idempotent, overwrites nothing |
| `check` | Looks and reports; creates, changes and repairs nothing. Never contacts the endpoint |
| `-p "…"` | One turn, plain text, no dock. Exit `0` completed · `1` failed · `4` suspended with nobody to answer |
| config | `~/.hera/code/config.toml`, mode 600, seeded from hera's endpoints then `HERA_PROVIDER_*`, and the file wins afterwards |
| the register | A `coding` profile with three traits, and the preamble in `SLOT_PROJECT`. **No mind region is written** |

## Done: v0.1.0 M0 — the workspace

| | |
|---|---|
| Workspace | ✅ `uv sync --all-packages` resolves. 16 members |
| Vendored packages | ✅ nine, byte-identical, digests in [`packages/VENDOR.md`](../packages/VENDOR.md) |
| New packages | ✅ six stubs — `hera_code_home` is real, the other five are their contracts |
| Meta-tests | ✅ layering · workspace · docs · vendor |
| ADRs | ✅ 1–10 |
| Documents | ✅ ARCHITECTURE · tui · tooling · versions · CLAUDE · CONTRIBUTING · README |
| Checks | ✅ `ruff`, `mypy --strict`, and every pre-commit hook |
| CI | ✅ lint · types · structure · test (3.12, 3.13) · terminal |
| Milestones and issues | ✅ created |

**What M0 is really for.** The four meta-tests are what stop this repository quietly becoming
something else. `test_layering.py` is the only place hera's claim that `hera_storage` and
`hera_prompts` are liftable into an unrelated project gets *tested* rather than asserted —
this is that project. `test_vendor.py` makes "a vendored package is not edited" a build failure.
Both had to be written before the code that could violate them.

## Timeline

| Version | State | For |
|---|---|---|
| v0.1.0 | M2 done, M3 next | A coding agent that works — see [versions/v0.1.0.md](versions/v0.1.0.md) |
| v0.2.0 | planned | The look, and the memory of a run: the visual pass, shadow tree, graph |
| v0.3.0 | planned | Reachable: hera drives hera-code, and where code runs |

## v0.1.0 milestones

**The bar for this version is stable enough to run daily and to test the concept.** Everything
wired: the packages, the local MCP server, skills, the working tree, the todo list, and a terminal
you can hold a conversation in. Correct beats polished — the visual pass is v0.2.0 M1, and
[versions/v0.1.0.md](versions/v0.1.0.md) names exactly what that defers.

| Milestone | Status | What it lands |
|---|---|---|
| M0 the workspace | ✅ | skeleton, vendoring, meta-tests, ten ADRs, every document |
| M1 the spine | ✅ | `init` · `check` · config · the `coding` profile · skills seeded · wiring · `-p "…"` · migrations |
| M2 the tools | ✅ | `hera_code_mcp` mounted as `code`: files, `bash`, `ask` · `hera_code_workspace` · `AGENT.md`/`CLAUDE.md` · the default policy |
| M3 the terminal | ⬜ next | scrollback + dock, one renderer per event variant, the gutter, both cards, `/slash`, `@file`, `NO_COLOR`, `^C` |
| M4 the todo list | ⬜ | `TODOS.md`, the three todo tools, the intake conversation, the dock strip |
| M5 sessions | ⬜ | `--continue` · `--resume` · the picker · compaction |
| M6 the release | ⬜ | five binaries, `install.sh`, `install.ps1` |

The chain M1 → M2 → M3 → M4 is a real dependency: the loop before the tools, the tools before the
terminal that draws their cards, the terminal before the conversation that fills the todo list. The
one arguable place is M2 before M3 — see the version document.

## Decided, and worth not re-litigating

Each of these has a record; this is the index to save reading all ten.

| | Where |
|---|---|
| Its own repository, hera's packages vendored and never edited | [ADR 1](adr/0001-a-uv-workspace-with-heras-packages-vendored.md) |
| Any OpenAI-compatible endpoint; no target model. hera's ADR 2 does not apply | [ADR 2](adr/0002-any-openai-compatible-endpoint.md) |
| Transcript in scrollback, dock pinned, `prompt_toolkit` + `rich`, not Textual | [ADR 3](adr/0003-the-transcript-lives-in-scrollback.md) |
| MCP is the tool layer; `hera_code_mcp` imports nothing of ours | [ADR 4](adr/0004-mcp-is-the-tool-layer.md) |
| A session is a `hera_chats.Chat`; the turn loop is reused unchanged | [ADR 5](adr/0005-a-session-is-a-chat-and-the-turn-loop-is-reused.md) |
| GitHub Flow; milestones are the plan; tags are the only thing that ships | [ADR 6](adr/0006-github-flow-and-milestones-are-the-plan.md) |
| `<root>/.hera/` is readable Markdown, and committing it is your call | [ADR 7](adr/0007-the-working-trees-hera-directory-is-readable.md) |
| The todo list is a file; the intake is a conversation | [ADR 8](adr/0008-the-todo-list-is-a-file-and-the-intake-is-a-conversation.md) |
| A shadow note is delivered with its file | [ADR 9](adr/0009-a-shadow-note-is-delivered-with-its-file.md) |
| Navigation before reading; freshness is stated | [ADR 10](adr/0010-navigation-before-reading.md) |
| Reads allow, changes ask, outside the tree deny; `--yes` is a person saying yes in advance | [ADR 11](adr/0011-the-default-policy-and-what-ask-means-with-nobody-there.md) |

**The one that cost the most to establish and pays the most:** everything hera-code redirects is
already injectable, so no vendored package needed a line changed. The database URL, the mind path,
the MCP config path, the built-in server, the asking tool — all of them are settings or arguments.
`SLOT_PROJECT` takes the working tree, the instructions, the todo list and the graph, and that is
what that slot is *for*. If that stops being true, [ADR 1](adr/0001-a-uv-workspace-with-heras-packages-vendored.md)
is the thing to re-open, not the copy to patch.

## Known gaps

- **No terminal.** `hera-code` with no `-p` says so and exits `3`. Until M3 there is no way to
  *answer* a permission card, so anything that changes a file either suspends the turn or needs
  `--yes`.
- **No sandbox.** `bash` runs with the person's own environment and permissions; the card is the
  only thing between a model and the machine. v0.3.0, and `docs/tooling.md` § 5 records the cost.
- **`.gitignore` is not parsed.** `Workspace.walk` takes glob patterns and a fixed ignore list; a
  half-right implementation of the real format would hide a file a person can see, which is worse
  than not having one.
- **`release.yml` fails deliberately on an application tag.** The tag-and-version check and the
  package path work; the PyInstaller matrix is a job that exits 1 with a pointer to M6. A release
  workflow that silently produced no binaries would be worse.
- **Nothing verifies the terminal.** The renderer-per-variant snapshot suite arrives with M3, and
  until then `docs/tui.md` is a document with nothing holding it to the code.
- **`main` is not protected yet.** The rulesets go on next; until then the branch-first rule in
  `CONTRIBUTING.md` is a convention rather than an enforcement.
- **Nothing has been run against a real endpoint.** Every test drives `FakeProvider`, and the
  suite now *forces* it so no test can reach a network by accident — the default `base_url` is
  where LM Studio listens, so a test that built its own provider used to talk to a real model on a
  developer machine and pass for the wrong reason in CI.
