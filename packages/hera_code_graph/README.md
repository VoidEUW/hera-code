# hera-code-graph

Navigating beats reading everything.

tree-sitter parses each source file into files, symbols and edges — defines, imports, references —
cached in `~/.hera/code/graph/<root digest>.sqlite3` and rebuilt incrementally on a content hash.

| Tool | Answers |
|---|---|
| `graph_outline(path)` | Every symbol in a file, with its line span |
| `graph_find(name)` | Where a name is defined, across the tree |
| `graph_neighbours(symbol, depth)` | What it calls, what calls it |
| `graph_path(a, b)` | How two symbols are connected |

That ordering is the point. A model with only `read` and `grep` spends its context window
establishing where things are, and has none left for the change it was asked to make.

**Freshness is stated, not implied.** The prompt says what the index knows — *N files, M symbols,
built three minutes ago* — because an index a model cannot date is one it will re-derive with
`grep` anyway.

| Owns | Never |
|---|---|
| Parsing, the schema, incremental rebuild, and the four navigation queries | Does not read file contents back out; does not decide what is relevant — it answers, the model asks |

Landing in **v0.2.0 M3**.
