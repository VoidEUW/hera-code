# 10. Navigation before reading, and what keeping an index fresh costs

- Status: accepted
- Date: 2026-09-06

## Context

An agent with `read`, `glob` and `grep` establishes where things are by reading. In a small
repository that is fine. In a large one it is most of the run: a dozen files opened to find the
three functions that matter, a context window mostly full of code that turned out to be
irrelevant, and the change itself made with whatever budget is left.

`grep` is the specific problem rather than reading in general. It answers *where does this string
appear*, and the question is almost always *where is this defined*, *what calls it*, or *what
would break*. The gap between those is filled by opening files.

What is actually wanted is a **graph**: files, symbols, and the edges between them — defines,
imports, references. That is a well-understood structure and tree-sitter produces it for every
language worth supporting, without needing the project to build or a language server to run.

The reason not to is freshness. An index is a cache of a working tree that changes under it,
including changes the agent itself just made.

## Decision

**hera-code builds and maintains a code graph, and its tools are shaped so that reading a whole
file is the last resort.**

| Tool | Answers |
|---|---|
| `graph_outline(path)` | Every symbol in a file with its line span, no bodies |
| `graph_find(name)` | Where a name is defined, across the tree |
| `graph_neighbours(symbol, depth)` | What it calls, what calls it |
| `graph_path(a, b)` | How two symbols are connected |

tree-sitter parses; the result is cached in `~/.hera/code/graph/<root digest>.sqlite3` and rebuilt
**incrementally on a content hash**, so a rebuild touches only what changed.

**Freshness is stated in the prompt, not implied.** The project slot says what the index knows —
*N files, M symbols, built three minutes ago, 2 files pending* — because a model that cannot date
an index will not trust it, and an index it does not trust is one it re-derives with `grep`
anyway, at which point the whole package has cost tokens and saved none.

**A write invalidates its own file immediately.** After `code__write` or `code__edit`, that file's
entry is marked stale in the same call, so the next `graph_outline` on it re-parses. The agent
cannot be shown its own edit as though it had not happened — that is the one staleness a person
would never forgive and the one that is trivial to prevent.

## Consequences

- **Everything else is stale until the next rebuild**, including changes made outside hera-code.
  A rebuild runs at session start and on demand; between those, an edit from another terminal is
  invisible. Stating the age is what makes this honest rather than a trap, and it is why the
  freshness line includes a count of pending files rather than only a timestamp.
- **tree-sitter grammars are a real dependency and a real binary-size cost.** Five platform
  binaries each carrying a grammar pack is the largest single contributor to the artifact, and it
  is why the graph is v0.2.0 rather than v0.1.0 — [ADR 3](0003-the-transcript-lives-in-scrollback.md)'s
  bundling concern applies here more than anywhere.
- **The graph does not read file contents back out.** `graph_outline` gives names and line spans;
  getting a body is still `read`. Keeping that boundary is what stops the graph turning into a
  second, worse file API — and it is the whole reason an outline is cheap.
- **It answers, it does not decide.** No ranking, no relevance scoring, no "here is what you
  probably want". The model asks. A graph that guessed would be a retrieval system, and retrieval
  that picks the wrong thing is the failure hera's ADR 5 spent a whole record on.
- **`grep` is not removed.** It is the right tool for a string, and pretending otherwise would
  make the agent work around the graph rather than with it. The prompt says which question each
  tool answers; it does not forbid one.
- The cache is derived and safe to delete. It is the one thing in this design not kept in the
  working tree ([ADR 7](0007-the-working-trees-hera-directory-is-readable.md)), because it is
  large, machine-readable, and costs only a rebuild.
