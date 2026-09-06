# Architecture decisions

One file per decision that changes the shape of the system: the context it was taken in, the
decision itself, and what it costs. Numbered, and not edited after the fact — a decision that
turns out wrong gets a new record that supersedes the old one, so the reasoning stays readable
later.

`tests/test_docs.py` holds this index and the directory together: an ADR that is not listed, a
listed file that does not exist, or a gap in the numbering is a failing build.

| # | Decision | Status |
|---|---|---|
| [1](0001-a-uv-workspace-with-heras-packages-vendored.md) | A uv workspace of its own, with hera's packages vendored | accepted |
| [2](0002-any-openai-compatible-endpoint.md) | Any OpenAI-compatible endpoint, and no target model | accepted |
| [3](0003-the-transcript-lives-in-scrollback.md) | The transcript lives in scrollback, and the dock is pinned | accepted |
| [4](0004-mcp-is-the-tool-layer.md) | MCP is the tool layer, and `hera_code_mcp` is the server hera-code is | accepted |
| [5](0005-a-session-is-a-chat-and-the-turn-loop-is-reused.md) | A session is a chat, and the turn loop is reused unchanged | accepted |
| [6](0006-github-flow-and-milestones-are-the-plan.md) | GitHub Flow, protected `main`, and milestones as the plan | accepted |
| [7](0007-the-working-trees-hera-directory-is-readable.md) | The working tree's `.hera/` is the agent's, and every file in it is a person's to read | accepted |
| [8](0008-the-todo-list-is-a-file-and-the-intake-is-a-conversation.md) | The todo list is a file, and the intake is a conversation | accepted |
| [9](0009-a-shadow-note-is-delivered-with-its-file.md) | A shadow note is delivered with its file, never fetched | accepted |
| [10](0010-navigation-before-reading.md) | Navigation before reading, and what keeping an index fresh costs | accepted |

## Read these first

If you are changing **model-facing behaviour** — prompts, tools, what the agent is told it can
do — read [2](0002-any-openai-compatible-endpoint.md), [4](0004-mcp-is-the-tool-layer.md) and
[9](0009-a-shadow-note-is-delivered-with-its-file.md).

If you are changing **the terminal**, read [3](0003-the-transcript-lives-in-scrollback.md) and
then [`docs/tui.md`](../tui.md).

If you are touching **anything under `packages/hera_*` that is not `hera_code_*`**, read
[1](0001-a-uv-workspace-with-heras-packages-vendored.md) first. The short version: don't.

## hera's decisions that apply here

hera-code vendors nine of hera's packages, so nine of hera's ADRs are load-bearing here without
being repeated. The ones worth reading in
[hera's `docs/adr/`](https://github.com/VoidEUW/hera/tree/main/docs/adr):

| | |
|---|---|
| **5** — skills are selected by code | The reasoning the shadow tree and the graph are both built on: a mechanism that only works when the model volunteers is not a mechanism |
| **10** — the persisted stream wraps the provider union | Why there is one event union and why the terminal renders variants rather than parsing text |
| **12** — a tool learns its context from `_meta` | Including the `contextvars` trap, which does not work here and does not fail either |
| **16** — a memory is a file, and all of them are in the prompt | The argument [9](0009-a-shadow-note-is-delivered-with-its-file.md) reuses |
| **17** — a stance is a sentence, and a question stands alone | Why `ask`'s `kind` is a closed set of three |

hera's **ADR 2** (Qwen only) is the one that deliberately does *not* apply — see
[2](0002-any-openai-compatible-endpoint.md).
