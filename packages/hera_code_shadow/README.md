# hera-code-shadow

Three directories under `<working tree>/.hera`, making three different promises.

| | |
|---|---|
| `shadow/<path>.md` | What was worked out about **one file**. Mirrors the tree |
| `sketches/<slug>.md` | Pre-thoughts and half-formed plans, not tied to a path |
| `thoughts/<slug>.md` | Conclusions worth keeping after the run that reached them |

**A shadow note is delivered with its file, never fetched.** When the read tool returns
`src/api/routes.py`, the note for that path goes back with it. A note the model has to remember to
ask for is a note that does not get read — the reasoning ADR 5 uses for skills and ADR 16 uses for
memories, and the thing that makes this a feature rather than a directory nobody opens.

Sketches and thoughts are the other half: they arrive as an **index** — title and one line each —
so the model knows what exists without paying to read all of it.

| Owns | Never |
|---|---|
| The three directories, note paths, the index, and what a note looks like | Does not decide when a note is written; does not rank or embed anything |

Landing in **v0.2.0 M2**.
