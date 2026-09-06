"""The run's todo list, which is a Markdown file and not a table.

``<working tree>/.hera/TODOS.md`` is the model. There is no database behind it and there is not
going to be one: a person opens it in their editor, reorders it, strikes something out, and
hera-code reads what they did. A list only the agent can write is a list a person watches happen
to them.

```markdown
# TODOS

- [x] `a1` read the existing middleware
- [>] `a2` add the token bucket to app/middleware/limit.py
- [ ] `a3` wire it into the app factory
- [!] `a4` pick the backend — blocked: redis or in-process?
```

Four states — pending, in progress, done, blocked — and a short stable id per item, so a tool call
can name one without an index that shifts the moment anything is inserted above it.

**Parsing is total.** A line this module does not understand is kept verbatim and reported as a
problem, never dropped — the same stance ``hera_skillsets`` takes on a malformed ``SKILL.md``, and
for the same reason: the file belongs to a person, and silently rewriting away the part of it that
confused us is the one unforgivable thing a tool can do to a file somebody wrote.

Landing in **v0.1.0 M4**, with the intake conversation that fills the list in the first place.
"""

from __future__ import annotations

__all__: list[str] = []
