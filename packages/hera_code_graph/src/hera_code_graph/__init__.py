"""A code knowledge graph, so that navigating beats reading everything.

tree-sitter parses each source file into **files**, **symbols** and **edges** — defines, imports,
references — cached in ``~/.hera/code/graph/<root digest>.sqlite3`` and rebuilt incrementally on a
content hash, so a rebuild touches only what changed.

The tools built on it are shaped so that reading a whole file is the **last** resort:

===========================================  ============================================
``graph_outline(path)``                      every symbol in a file, with its line span
``graph_find(name)``                         where a name is defined, across the tree
``graph_neighbours(symbol, depth)``          what it calls, and what calls it
``graph_path(a, b)``                         how two symbols are connected
===========================================  ============================================

That ordering is the whole point of the package. A model with only ``read`` and ``grep`` spends
its context window establishing where things are, and then has none left for the change it was
asked to make.

**Freshness is stated, not implied.** The prompt says what the index knows — *N files, M symbols,
built three minutes ago* — because a model that cannot tell whether an index is current will not
trust it, and an untrusted index is one that gets re-derived with ``grep`` anyway.

Landing in **v0.2.0 M3**.
"""

from __future__ import annotations

__all__: list[str] = []
