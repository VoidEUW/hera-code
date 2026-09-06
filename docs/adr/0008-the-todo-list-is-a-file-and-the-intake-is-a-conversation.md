# 8. The todo list is a file, and the intake is a conversation

- Status: accepted
- Date: 2026-09-06

## Context

The failure mode this whole application is organised against is the agent that wanders: it is
given a goal, starts confidently, discovers something halfway through, follows it, and finishes
somewhere adjacent to what was asked for. Nobody notices until the diff.

A todo list is the usual answer and it is usually decorative — a list the model writes to itself,
renders once, and stops consulting. Three things are needed to make it load-bearing instead:

1. It has to be **visible continuously**, not printed once. A list that scrolled away three
   screens ago is not steering anything.
2. It has to be **in the prompt every turn**, or the model is not steering by it either.
3. It has to be **right at the start**, and it will not be, because the first message is
   underspecified. *Add rate limiting to the api* does not say which endpoints, which backend,
   or whether an existing middleware chain should be extended or replaced.

The third is the hard one. A model that plans from an underspecified prompt produces a confident
plan built on assumptions nobody agreed to, and then follows it — which is the wandering, arriving
one step earlier than expected.

## Decision

**The list is `<working tree>/.hera/TODOS.md`**, Markdown, no database behind it.

```markdown
# TODOS

- [x] `a1` read the existing middleware
- [>] `a2` add the token bucket to app/middleware/limit.py
- [ ] `a3` wire it into the app factory
- [!] `a4` pick the backend — blocked: redis or in-process?
```

Four states — pending `[ ]`, in progress `[>]`, done `[x]`, blocked `[!]` — and a short stable id
per item, so a tool call names one without an index that shifts when anything is inserted above
it.

**The intake is a conversation, and it happens before the plan.** With no `TODOS.md`, the project
slot instructs: ask before planning. The model calls `ask`, which suspends the turn — the
mechanism `hera_chats` already has for permission cards — the terminal draws a question card, and
the person's reply becomes that call's result. The list is written **with** the person, and only
then does work start.

`kind` on `ask` is the closed set hera settled on: `unsure · blocked · choice`. Intake questions
are almost always `choice`.

**It is visible in three places at once**, which is the point:

| Where | What it does |
|---|---|
| The dock's top row | Progress and the item in progress, always, `^T` for the whole list |
| The project slot | The full list, every turn |
| The file | A person edits it, and hera-code reads what they did |

## Consequences

- **A person can rewrite the plan mid-run by editing a file**, and the next turn will follow it.
  That is the strongest argument for a file over a table and it is worth the parsing work.
- **The intake costs a round trip before anything happens**, and on a genuinely clear request that
  is friction. The mitigation is a rule the model is given rather than a heuristic in code: ask
  only what changes what gets built. A person who wants none of it deletes nothing — they answer
  once and the list exists.
- **The list can be wrong and hera-code cannot tell.** It steers; it does not verify. An item
  marked done that was not is a lie the interface repeats. That is acceptable because the diff is
  the check and always was, and it is why the dock shows progress rather than claiming completion.
- **`[!] blocked` is a state and not an error.** It is the one that makes the list honest about a
  run that stopped: an item nobody could decide is visibly different from an item nobody started,
  and collapsing the two is how a stalled run looks like a slow one.
- Parsing is total ([ADR 7](0007-the-working-trees-hera-directory-is-readable.md)). A line the
  parser does not understand is kept and reported.
