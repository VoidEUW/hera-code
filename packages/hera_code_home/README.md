# hera-code-home

Two questions, two answers: **where is `~/.hera/code`**, and **where is this working tree's
`.hera`?**

```python
from pathlib import Path
from hera_code_home import code_home, sessions_db_path, todos_path, shadow_path

code_home()                                    # ~/.hera/code
sessions_db_path()                             # ~/.hera/code/sessions.sqlite3
todos_path(Path("/repo"))                      # /repo/.hera/TODOS.md
shadow_path(Path("/repo"), "src/api.py")       # /repo/.hera/shadow/src/api.py.md
```

Everything **shared with hera** — `mind/`, `skills/`, `mcp.json`, `config.toml` — comes from
`hera_home` and is not repeated here. This module answers only for the two directories hera has no
business reading.

The split is the point. `~/.hera/code` is hera-code's, so `HERA_HOME` moves both applications at
once. `<root>/.hera` is one repository's, because the todo list and the shadow notes are *about
that code*: they belong in a diff, and a person who clones the repository elsewhere should get
them.

It depends on `hera_home` and nothing else, holds no state, and reads the environment on every
call — so a test that sets `HERA_HOME` with `monkeypatch.setenv` takes effect immediately and
nothing has to be reset.

Nothing here creates a directory. Asking where something is and deciding to make it are different
decisions, and the second one belongs to whoever owns the contents.

The two functions that take an argument from a tool call — `graph_path` and `shadow_path` —
refuse it rather than trusting it. A `..` in a shadow path would write a note outside the tree.
