# 7. The working tree's `.hera/` is the agent's, and every file in it is a person's to read

- Status: accepted
- Date: 2026-09-06

## Context

hera-code needs somewhere to keep what it works out: the run's todo list, notes about individual
files, sketches, conclusions. Two questions follow immediately — where, and in what format.

**Where** has three candidates. Under `~/.hera/code/<repo digest>/`, which keeps the working tree
clean and makes the notes invisible, unbackupable and lost when the directory is cleared. In a
SQLite table, which makes them queryable and unreadable. Or inside the working tree itself.

**What format** has two: something structured, which is easy to write reliably and impossible to
edit by hand; or Markdown, which is the reverse.

The precedent is hera's, and it is emphatic. `mind/` is a real git repository. A memory is a
markdown file whose name is its key. A skill is a directory with a `SKILL.md` in it. `mcp.json` is
a file you wrote. The stated principle is that *the interface should never be the only way to see
something*.

## Decision

Everything hera-code works out about one repository lives in **`<working tree>/.hera/`**, as
files a person can open:

```
<root>/.hera/
  TODOS.md              the run's todo list
  shadow/<path>.md      one note per source file, mirroring the tree
  sketches/<slug>.md    half-formed plans, not tied to a path
  thoughts/<slug>.md    conclusions worth keeping
```

Markdown throughout, and there is no database behind any of it. The file **is** the model:
`hera_code_todos` parses `TODOS.md` and writes it back, and a person who reorders the list in
their editor has reordered the list.

**Whether it is committed is the person's decision.** hera-code never edits a `.gitignore` and
never asks again after saying so once on `init`. Both answers are reasonable — a team may want the
shadow tree in review, and a person working alone may not want the noise — and neither is
hera-code's to make.

**Parsing is total.** A line `hera_code_todos` does not understand is kept verbatim and reported
as a problem, never dropped. The same stance `hera_skillsets` takes on a malformed `SKILL.md`.

`~/.hera/code/` holds what is *not* about one repository: sessions, settings, the graph cache.

## Consequences

- **Silently rewriting away the part of a file that confused us is the one unforgivable thing.**
  Total parsing is what stops that, and it is why `TODOS.md` reports problems instead of raising:
  a person's file is not a place to have an opinion about their formatting.
- **The notes travel with the code.** Clone the repository elsewhere and the shadow tree comes
  too, if it was committed. That is the main argument for this location and it is worth the
  visible directory.
- **A stale note is possible and is not prevented.** A shadow note for a file that has since been
  rewritten will be wrong, and hera-code has no way to know. The mitigation is that a note is
  delivered *with* its file ([ADR 9](0009-a-shadow-note-is-delivered-with-its-file.md)), so the
  model reads the note and the current contents together and can see the disagreement. A note
  fetched on its own would not have that.
- **The graph cache is the exception and is not in the tree.** It is derived, large, and
  machine-readable — three properties none of the others have. It lives in `~/.hera/code/graph/`
  and deleting it costs a rebuild and nothing else.
- `.hera` collides with nothing in common use, and it is the same name hera uses in `$HOME`, which
  makes *the directory hera keeps things in* one idea rather than two.
