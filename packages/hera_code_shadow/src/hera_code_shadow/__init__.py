"""What was worked out once, kept so it is not worked out again.

Three directories under ``<working tree>/.hera``, and they make three different promises:

``shadow/``
    One note per source file, at the same relative path. What this file is for, what surprised
    somebody about it, which of its functions is load-bearing. Mirrors the tree, so finding the
    note is the same act as finding the file.

``sketches/``
    Half-formed plans and pre-thoughts, not tied to any one path. Somewhere to reason out loud
    before there is anything to write down properly.

``thoughts/``
    Conclusions worth keeping after the run that reached them has ended.

**A shadow note is delivered with its file, never fetched.** When the read tool returns
``src/api/routes.py``, the note for that path goes back with it. A note the model has to remember
to ask for is a note that does not get read — the same reasoning ADR 5 uses for skills and ADR 16
uses for memories, and the thing that makes this a feature rather than a directory of files
nobody opens.

Sketches and thoughts are the other half of that arrangement: they arrive as an **index** — title
and one line each — so the model knows what exists without paying to read all of it, and reaches
for the one it wants.

Landing in **v0.2.0 M2**.
"""

from __future__ import annotations

__all__: list[str] = []
