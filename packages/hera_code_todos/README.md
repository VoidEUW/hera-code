# hera-code-todos

`<working tree>/.hera/TODOS.md` is the model. There is no database behind it and there is not going
to be one.

```markdown
# TODOS

- [x] `a1` read the existing middleware
- [>] `a2` add the token bucket to app/middleware/limit.py
- [ ] `a3` wire it into the app factory
- [!] `a4` pick the backend — blocked: redis or in-process?
```

Four states — pending, in progress, done, blocked — and a short stable id per item so a tool call
can name one without an index that shifts.

**Parsing is total.** A line this package does not understand is kept verbatim and reported, never
dropped. The file belongs to a person; silently rewriting away the part that confused us is the
one unforgivable thing to do to a file somebody wrote.

| Owns | Never |
|---|---|
| The format, the four states, stable ids, parsing and rendering, and reporting what it could not read | Does not decide what goes on the list — that is the intake conversation, and it happens in the application |

Landing in **v0.1.0 M4**.
