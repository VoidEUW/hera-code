# Architecture

hera-code is a uv workspace. Each package has one job, owns its own tables, and imports only
downwards. The rule is mechanical: if a package needs something from a package above it, the
dependency is wrong, not the design.

```
                    apps/cli  (hera-code: the terminal, owns migrations)
                                  │
      ┌───────────────────────────┼────────────────────────────┐
 hera_profiles              hera_code_graph            hera_code_todos
 hera_tools    hera_chats   hera_code_shadow           hera_code_workspace
 hera_prompts *  hera_providers   hera_permissions     hera_skillsets
 hera_code_mcp *      hera_storage *      hera_code_home
                            hera_home
```

`*` = imports no other package in this workspace, and `tests/test_layering.py` gives each of the
three an empty allow-list so this is checked rather than trusted.

`hera_storage` and `hera_prompts` are **domain-free by contract**: they know nothing about hera,
nothing about coding, no table, no chat, no tool, and must stay liftable into an unrelated
project. **This repository is that project.** hera asserts the claim; hera-code is the only thing
that can test it, and those two empty sets are where it happens.

`hera_code_mcp` has an empty allow-list for a different reason: it is *entirely* about hera-code —
its tools, what `edit` is for, the sentence a model reads before running a shell — but everything
it needs from the rest of the system arrives as a port, so it imports nothing of ours. It is the
server hera-code **is**; `hera_tools` is the client it **has**, and the client does not know it
exists. The application mounts one into the other. See [ADR 4](docs/adr/0004-mcp-is-the-tool-layer.md).

`hera_home` and `hera_code_home` are the exceptions that prove the layering rule rather than
violations of it. Neither is domain-free — both say the word "hera" and know the shape of a
directory — but both depend on almost nothing, answer one question, and sit below everything. They
exist because several packages need the same answer and some of them may not import each other; a
copy of the lookup in each would be several places that can disagree about a path, which fails as
an empty directory rather than as an error.

## Vendored, and what that means

Nine of the packages under `packages/` are **copies** of hera's, byte-identical, recorded in
[`packages/VENDOR.md`](packages/VENDOR.md) with a digest each. They are not forks and are never
edited; `tests/test_vendor.py` fails if one is. When hera publishes tags, each directory is
deleted and each `[tool.uv.sources]` row becomes a git source — that is the whole migration, and
the no-edit rule is what keeps it that cheap. See [ADR 1](docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md).

Their allow-lists in `tests/test_layering.py` are hera's rows unchanged, which is itself a check:
a copy whose layering had to be widened here is a copy that is no longer the same package.

## The packages

### Vendored from hera

| Package | Owns | Never |
|---|---|---|
| `hera_home` | Where `~/.hera` is and the well-known paths inside it. Reads the environment on every call; caches nothing, creates nothing | No I/O, no dependency, no opinion about what lives in those paths |
| `hera_storage` | The persistence foundation: engine, sessions, `Entity`/`SoftDeletable`/`Versioned` mixins, a generic `Repository`, snapshot versioning, pytest fixtures | No table, no domain concept, no other package's import |
| `hera_prompts` | The prompt compiler: `Prompt`, `Section`, traits, renderers, budget, `fingerprint()`. Foreign content enters only as pre-rendered strings through named slots | Does not know what a tool, a file, a skill or a session is; no persistence, no I/O |
| `hera_providers` | Talking to a model. httpx streaming, the OpenAI-compatible provider, the Qwen adapter, embeddings, and a `FakeProvider` for tests. Emits one normalised event union | Knows nothing about sessions, prompts or tools |
| `hera_permissions` | Whether a tool call may run: allow / deny / ask, per pattern, per profile. Pure logic | No I/O, no registry of actual tools |
| `hera_tools` | The MCP **client**: server lifecycle, tool catalogue, namespacing, dispatch. Mounts whatever in-process server it is handed, under that server's own name. Above `ToolRegistry`, a failed call is a `ToolResult`, never an exception | Does not decide policy, does not build prompts, and does not know `hera_code_mcp` exists |
| `hera_skillsets` | `SKILL.md` packages on disk and the **router** that picks them server-side — pinned, `/slash`, retrieved — with per-owner usage counts. Bad content is a reported problem, never an exception | Does not ask the model which skill it wants; does not write to the skills directory |
| `hera_profiles` | The mind: twelve named regions as files in a git repository, behaviour traits, profiles that select and override them, and the builder that turns the lot into a `hera_prompts.Prompt` with slots left open. Answers *who it is*; the working tree answers *what we are working on* | Does not render, does not stream, does not know what fills a slot |
| `hera_chats` | Sessions, messages, the persisted `ChatEvent` stream, and the turn orchestrator | Does not know which provider or which tools exist — both arrive injected; raises nothing — a turn closes with a reason |

### hera-code's own

| Package | Owns | Never |
|---|---|---|
| `hera_code_home` | Where `~/.hera/code` is, and where a working tree's `.hera` is. The two directories hera has no business reading | No I/O, no creation. Does not answer for anything shared — that is `hera_home` |
| `hera_code_mcp` | The MCP server hera-code **is**: files, shell, graph, todos, the shadow tree, and `ask` — plus the **ports** the ones that touch the rest of the system take. Tool descriptions are prompt text; changing them changes behaviour | Imports no other package here, and does no I/O at all |
| `hera_code_workspace` | The working tree: root discovery, branch and dirty count, `.gitignore`-aware walks, the `AGENT.md`/`AGENTS.md`/`CLAUDE.md` lookup, and the guard that nothing outside the root is reachable | Does not know what a model, a turn or a tool is; does not read or write source files itself |
| `hera_code_todos` | `TODOS.md`: the format, the four states, stable ids, parsing and rendering, and reporting what it could not read | Does not decide what goes on the list — that is the intake conversation, in the application |
| `hera_code_shadow` | The shadow tree, `sketches/` and `thoughts/`: note paths, the index, and what a note looks like | Does not decide when a note is written; does not rank or embed anything |
| `hera_code_graph` | The code graph: parsing, the schema, incremental rebuild, and the four navigation queries | Does not read file contents back out; does not decide what is relevant — it answers, the model asks |

## Rules that hold everywhere

**Tables.** Every package sets `__tablename__` explicitly with its own prefix (`chat_`, `skill_`,
`graph_`). All models share one `MetaData`, so unprefixed names from two packages would silently
collide.

**No cross-package foreign keys.** A reference to another package's entity is a bare `UUID`
column. Integrity is the application's job, not the database's.

**Migrations live in `apps/cli`.** Only there is every package imported, so only there does
`alembic autogenerate` see the whole schema. SQLite needs `render_as_batch=True`.

**One event union per boundary, with a total mapping between them.** `hera_providers` defines what
a *model* can emit. `hera_chats.ChatEvent` wraps it and adds what a *turn* contains — a skill
selection, a tool result, a permission request — because none of those is model output and the
model boundary must not learn what a skill is. The terminal renders one component per variant and
**never parses text**. A new kind of thing the model can do is one variant in `hera_providers`
plus one line of mapping; a new kind of thing a turn contains is one variant in `hera_chats` and
one renderer here.

**The persisted render is authoritative.** The terminal draws optimistically while streaming, then
re-renders the turn from the persisted event list at `turn_closed`. Live view and a resumed
session therefore cannot disagree.

**Skill selection is code.** Never build a feature that depends on the model noticing something is
relevant — that is the reasoning the shadow tree and the graph are both built on. hera's ADR 5.

**English everywhere** — code, comments, commits, prompts, stored content, terminal strings.

## The turn

```
what the person typed
  └─ hera_skillsets.SkillRouter.select()      pinned · /slash · retrieval   (no model involved)
  └─ hera_profiles.PromptBuilder.build()      mind regions → Prompt, slots bound
       └─ SLOT_PROJECT ← apps/cli/context.py  working tree · instructions · TODOS.md ·
                                              shadow index · graph freshness
  └─ hera_prompts.Prompt.render()             messages + snapshot (fingerprint, dropped keys)
  └─ hera_providers.Provider.stream()         TextDelta · ThinkingDelta · ToolCallReady …
        ├─ ToolCallReady → hera_permissions.check() → hera_tools.dispatch() → ToolResultEvent
        │                    └─ ask → PermissionRequired, turn closes, resumable
        │                    └─ code__ask → AnswerRequired, turn closes, resumable
        │                                      ↑ loops, bounded by max_iterations
        └─ TurnEnd consumed per round trip → one TurnClosed ends the turn
             └─ hera_chats persists the coalesced ChatEvent list
             └─ apps/cli/tui re-renders the turn from it
```

`SLOT_PROJECT` is the seam that makes this work without changing a vendored package. It is
`hera_profiles`' own slot, its stated meaning is *what we are working on*, and the working tree,
the instructions, the todo list, the shadow index and the graph are exactly that. See
[ADR 5](docs/adr/0005-a-session-is-a-chat-and-the-turn-loop-is-reused.md).

## The model

Any **OpenAI-compatible endpoint** ([ADR 2](docs/adr/0002-any-openai-compatible-endpoint.md)).
Several may be registered in `~/.hera/code/config.toml`; one is active. The minimum bar is native
tool calling — an endpoint without it does not work and says so, rather than degrading into a text
call grammar. There is deliberately no target model and nothing above `hera_providers` may assume
one.

## Data on disk

### Shared with hera — created by whichever runs first

```
~/.hera/                 HERA_HOME overrides
  mind/                  a real git repository, one file per mind region
  skills/<name>/SKILL.md skill packages, the same format Claude Code uses
  mcp.json               Claude-Desktop-compatible `mcpServers` shape
  config.toml            registered endpoints
```

If no hera install has created these, hera-code does, and installing hera later finds them already
there. Nothing is ever overwritten and nothing is ever deleted for you.

### hera-code's own

```
~/.hera/code/
  sessions.sqlite3       sessions and their persisted event streams
  config.toml            which endpoint is active here, and how the terminal behaves
  AGENT.md               instructions that apply in every working tree
  graph/<digest>.sqlite3 one code index per working tree — derived, safe to delete
```

Its own database rather than a table in `hera.sqlite3`: a coding agent writes a turn every few
seconds, and sharing a SQLite file with a running web application is how both learn what
`database is locked` means.

### One working tree's

```
<root>/.hera/
  TODOS.md               the run's todo list — Markdown, and a person may edit it
  shadow/<path>.md       one note per source file, mirroring the tree
  sketches/<slug>.md     half-formed plans, not tied to a path
  thoughts/<slug>.md     conclusions worth keeping
```

Inside the working tree because these are *about this code*: they belong in a diff, and a person
who clones the repository elsewhere should get them. Whether they are committed is theirs to
decide — hera-code says so once on `init` and never edits a `.gitignore`. See
[ADR 7](docs/adr/0007-the-working-trees-hera-directory-is-readable.md).
