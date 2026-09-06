# Tooling

What a coding agent should be able to reach for, and what hera-code cannot reach for yet.

**Notes, not decisions.** Anything here that becomes a decision moves to `docs/adr/` and this file
gets a line pointing at it. Read this before adding a tool — several of the gaps below are gaps on
purpose, and the reason is not always obvious from the absence.

The rule that governs the whole file: **a tool is a thing the model can do, and every one of them
costs prompt tokens and a decision.** A catalogue of forty tools is a catalogue the model chooses
badly from. Each addition should be able to answer *what could it not do before?*

---

## 1. What it has, or will have

| Tool | Milestone | Notes |
|---|---|---|
| `read` · `write` · `edit` · `glob` · `grep` | ✅ v0.1.0 M2 | `edit` is find/replace, not a line-range patch — see § 3 |
| `bash` | ✅ v0.1.0 M2 | `ask` by default, and the reason it is not `allow` is § 5 |
| `ask` | ✅ v0.1.0 M2 | Suspends the turn. `hera_chats` already has the mechanism |
| `todo_read` · `todo_write` · `todo_set` | v0.1.0 M4 | The list is a file; these are how the model edits it |
| `note_write` · `note_read` · `sketch_write` · `thought_write` | v0.2.0 M2 | Reading a note is mostly automatic — ADR 9 |
| `graph_outline` · `graph_find` · `graph_neighbours` · `graph_path` | v0.2.0 M3 | ADR 10 |

Plus whatever is in `~/.hera/mcp.json`, mounted by `hera_tools` and namespaced by server. A
filesystem server, a browser, a database — none of that is hera-code's business to build.

---

## 2. Web search and fetch — missing, and it changes what it *says*

hera's `docs/tooling.md` § 1 makes the argument and it applies here more sharply: **a model with
no way to look something up does not answer "I cannot check that", it guesses fluently.** For a
chat assistant that produces a wrong sentence. For a coding agent it produces a call to an API
that does not exist, in the shape the model remembers from its training data, and the person finds
out at runtime.

The specific case is library versions. *Which argument does this function take in the version this
project pins* is the single most common thing an agent is confidently wrong about, and it is
answerable from a docs page.

Not built, and not scheduled. The options, in order of how much they are worth:

1. **Read the installed package.** The dependency is already on disk in `.venv`. A `read` on
   `site-packages` answers the version question exactly, offline, with no new tool — it is
   currently blocked by the containment guard, and *should the guard have a read-only exception
   for the active virtualenv* is the most valuable open question in this file.
2. Let a person configure a docs MCP server. Costs nothing, works today, and nobody will do it.
3. `fetch` on an explicit URL. Bounded, and needs a permission story.
4. General web search. Most useful and least bounded.

---

## 3. `edit` as find/replace, and what that costs

The chosen shape is `edit(path, find, replace)`, matching what Claude Code does, because it fails
loudly: a `find` that does not match exactly once is an error the model reads and retries, rather
than a patch applied at the wrong offset.

What it costs is tokens. The model has to reproduce enough surrounding context to be unique, which
on a large edit approaches quoting the file back. A line-range patch is cheaper and silently wrong
when the line numbers are stale — and with a graph in play, they will be.

**Worth revisiting after v0.2.0 M3**, when `graph_outline` can give a symbol's line span and an
edit could be addressed as *the body of this function* rather than as either coordinates or a
quotation. That is a third option neither tool currently offers, and it is the interesting one.

---

## 4. Running the tests

`bash` covers it, and that is the whole problem: hera-code sees a test run as a wall of text and
an exit code. It cannot tell three failures from one, cannot tell a failure from a collection
error, and cannot say which test.

A `test` tool that understood one runner's machine-readable output — `pytest --json-report`, and
nothing else at first — would make *did that fix it* a structured answer. The reason it is not
built is that it is one tool per ecosystem forever, and the first one is easy in exactly the way
that hides the cost of the sixth.

The honest interim is a **convention rather than a tool**: the project's `AGENT.md` says how to
run its tests, hera-code runs that with `bash`, and the model reads the output like a person does.
That is what root-level instruction files are *for*, and it is worth trying before building
anything.

---

## 5. Where code runs — the one with two callers

`bash` is `ask` by default and every invocation costs a card ([ADR 11](adr/0011-the-default-policy-and-what-ask-means-with-nobody-there.md)).
That is the correct default and it is also the single biggest friction in daily use, and both of
those are true at once. `--yes` is the escape hatch and is deliberately a *person saying yes in
advance* rather than a way to switch the cards off — it cannot reach what is denied outright.

The thing that would fix it is a sandbox: a `bash` that cannot reach outside the working tree and
cannot reach the network is a `bash` that can be `allow`. hera has already written the record —
[ADR 15](https://github.com/VoidEUW/hera/blob/main/docs/adr/0015-running-code-in-a-container.md),
deferred — and it asks exactly this question for a different caller.

**One question, two callers, and answering it twice is how two answers diverge.** v0.3.0 M3, and
the thing to bring to it is that hera-code's `bash` runs against a repository a person is also
editing, which is a constraint hera's version does not have.

---

## 6. A language server

The strongest possible version of the graph, and deliberately not the plan. An LSP client would
give exact go-to-definition, find-references, rename, and diagnostics — everything
[ADR 10](adr/0010-navigation-before-reading.md) approximates with tree-sitter.

It is not the plan because it needs the project to build. A language server on a repository with a
broken dependency install, a half-finished refactor or a missing environment gives nothing, and
those are exactly the states a coding agent is asked to work in. tree-sitter parses a file that
does not compile.

The right relationship is probably **both** — the graph as the always-available floor, an LSP as
an optional upgrade — but that is a v0.4 conversation and it should start from measurements of how
often the graph is wrong, which do not exist yet.

---

## 7. What is deliberately absent

| | Why |
|---|---|
| A tool that **lists** shadow notes | The ones that matter arrived with their files (ADR 9). hera's ADR 16 makes the same argument about memories |
| **Ranking** in the graph | It answers, it does not decide. A graph that guessed would be a retrieval system, and retrieval picking the wrong thing is what hera's ADR 5 is about |
| A tool that **deletes** a todo or a note | Nothing is deleted for you. A person removes a file; the agent marks it done or blocked |
| `git commit` as a **tool** | It is `bash`, and it should keep costing a card. A commit is the one action here that is hard to reverse for somebody else |
| A **second** memory | hera-code has one, and it is the shadow tree. `hera_memories` is v0.2.0 M4 and may turn out to be an ADR saying no |
