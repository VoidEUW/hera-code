# 5. A session is a chat, and the turn loop is reused unchanged

- Status: accepted
- Date: 2026-09-06

## Context

A hera-code session is a conversation with tool calls in it. So is a hera chat. The question is
whether that structural similarity is deep enough to share an implementation, or whether a coding
agent wants a leaner loop of its own over `hera_providers` + `hera_tools` + `hera_permissions`
with sessions as JSONL files.

What `hera_chats.Turn` already does, and what a new loop would have to re-implement:

- The tool loop, bounded by `max_iterations`, with a final round where the tools are **withheld**
  rather than the turn simply stopping — the only thing that reliably stops a model asking for
  more, because telling it in prose is advice and an empty tool list is arithmetic.
- **Suspension.** A permission card and a question both close the turn with a reason and persist
  what happened; answering starts a new turn that resumes the same message. A turn that held a
  connection open waiting for a person is a turn that dies with the connection.
- A **repeat limiter** keyed on the tool and its sorted arguments, which answers a third identical
  call by quoting what the first two returned. This is the failure mode of a model that keeps
  searching because nothing told it the searching was not working, and a coding agent in a large
  repository hits it harder than a chat does.
- **Coalescing** at the boundary between streaming and storing, so a reload does not replay the
  typing and the live view and the reloaded one render the same variants.
- `Turn.recorded` being complete at every moment, which is what makes a cancelled turn a turn with
  the work so far rather than a lost one. `^C` mid-edit is an everyday event here.

The cost of reusing it is that `hera_chats` brings SQLAlchemy and `hera_profiles`, so a CLI
carries an ORM and a git repository of mind regions.

## Decision

**A session is a `hera_chats.Chat`**, and `TurnOrchestrator` is used unchanged. Sessions are
persisted to `~/.hera/code/sessions.sqlite3` — its own database, because a coding agent writes a
turn every few seconds and sharing a SQLite file with a running web application is how both learn
what `database is locked` means.

The mind is **shared**: `hera_profiles.MindRepository` defaults to `~/.hera/mind` and is left
there, so hera and hera-code answer from the same twelve regions. hera-code seeds them if no hera
install has.

Everything coding-specific goes into **`SLOT_PROJECT`** — the slot `hera_profiles` already
defines, whose stated meaning is *what we are working on*. The application composes it from the
working tree, the agent instruction files, the todo list, the shadow index and the graph's
freshness. That is exactly what that slot is for, and it means **no vendored package needs a line
changed**.

## Why not a leaner loop

Because the five behaviours above are not incidental. Each was written in response to something
observed against a real endpoint, and a second loop would rediscover all five — worse, it would
rediscover them one production incident at a time, and then the two loops would diverge and a fix
would have to be made twice. "The two loops will drift" is not a risk, it is what happens.

The ORM is a real cost and it is the price. It buys a schema that migrates, a query that is not a
directory scan, and a `Message` that already stores the events it was made of.

## Consequences

- **hera-code's profile is a profile, not a fork of the mind.** The coding register lives in a
  `coding` profile's trait overrides and in the project slot's preamble. If a piece of text would
  still be true in a chat window it is a mind region; if it would not, it is project text. That
  line comes from hera's `docs/frontend.md` and holds here unchanged.
- **hera-code seeds the shared `~/.hera`.** A person who has never run hera gets `mind/`,
  `skills/` and `mcp.json` created by hera-code, and installing hera later finds them already
  there. Nothing is ever overwritten.
- **The event union is hera's.** `ChatEvent` is what the terminal renders, one renderer per
  variant, no parsing. A new kind of thing a turn can contain is a variant in `hera_chats` and a
  renderer here.
- `hera_memories` is deliberately **not** vendored. A coding agent's memory of a repository is the
  shadow tree, and the two want designing together rather than one inherited — v0.2.0 M4.
- If `hera_chats` ever needs a change to serve hera-code, that is a signal worth taking seriously:
  it means the two applications' turns are not the same shape after all, and this record should be
  re-opened rather than the vendored copy patched.
