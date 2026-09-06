# hera-code-workspace

The working tree hera-code is pointed at: where its root is, what branch it is on, which files are
worth walking, and what a person has already written down about how to work in it.

**Instruction files.** `AGENT.md`, `AGENTS.md` and `CLAUDE.md` are all read at the root — every
one that exists, in that order. A repository already set up for another coding agent needs no new
file. `~/.hera/code/AGENT.md` prepends as instruction that applies in every tree.

**Nothing outside the root is reachable.** The guard lives here rather than in each tool that
needs it, because a path arrives from a model and there has to be exactly one place that decides
whether a path is inside the tree.

| Owns | Never |
|---|---|
| Root discovery, branch and dirty count, `.gitignore`-aware walks, the instruction lookup, the containment guard | Does not know what a model, a turn or a tool is; does not read or write source files itself |

Landing in **v0.1.0 M2**. Until then this package is its contract and nothing else.
