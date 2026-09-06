# 9. A shadow note is delivered with its file, never fetched

- Status: accepted
- Date: 2026-09-06

## Context

Every run re-derives the same things. That this module is the only writer of the cache; that the
retry logic in one function is load-bearing and looks redundant; that two files must change
together. Working it out costs tool calls and context, and the next run starts from nothing.

The obvious fix is to let the agent write notes. The non-obvious part is how it reads them back,
and there are two designs:

- **A `note_read(path)` tool.** The model asks when it wants a note. Simple, and it depends
  entirely on the model remembering that notes exist and guessing that one exists for this file.
- **Delivery.** The note comes back attached to the thing it is about.

hera has already settled this argument twice, in two different places, against the same failure.
[ADR 5](https://github.com/VoidEUW/hera/blob/main/docs/adr/0005-deterministic-skill-routing.md):
skills are selected by code, because a mechanism that only works when the model volunteers is not
a mechanism. [ADR 16](https://github.com/VoidEUW/hera/blob/main/docs/adr/0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md):
every enabled memory is in the prompt, because a memory that was stored and did not arrive looks
exactly like one that was never stored, and nobody on either side can tell which happened.

## Decision

**When `code__read` returns a file, the shadow note for that path goes back with it.** One result,
the contents and the note, clearly separated. The model does not ask and cannot forget.

Notes live at `<root>/.hera/shadow/<same relative path>.md` — the extension kept rather than
replaced, so `routes.py` and `routes.ts` do not share a note.

`note_write` exists. **`note_read` also exists**, and that is deliberate: delivery covers the case
where the model is already looking at the file, and there is a real case where it wants a note
without the file — deciding whether to open it at all. What is *not* built is a tool that lists
notes, for ADR 16's reason: the ones that matter have already arrived.

**Sketches and thoughts work the other way**, and the asymmetry is the design. They are not about
any one path, so there is nothing to attach them to. They arrive as an **index** in the project
slot — title and one line each — and the model reaches for the one it wants. Cheap to carry, and
the model knows what exists without reading all of it. Exactly the shape of the skills catalogue.

## Consequences

- **A stale note is delivered as confidently as a fresh one**, and hera-code has no way to know.
  Delivery is what makes this survivable: the note and the current contents arrive together, so a
  disagreement is visible in the same result. A note fetched separately would be read on its own
  and believed. This is the strongest argument for delivery over a tool and it was not the
  original one.
- **Every read of an annotated file costs the note's tokens**, whether or not it was relevant.
  That is the same trade ADR 16 makes and the answer is the same: the space is the feature, and
  the control is a ceiling. A note that has grown past it is a note that should have been a
  `thoughts/` entry.
- **Notes are written, not curated.** Nothing prunes them. A note for a deleted file is orphaned
  and stays orphaned until a person deletes it — the same stance as *nothing is ever deleted for
  you*, and the reason the shadow tree mirrors the source tree is so that finding the orphan is
  the same act as noticing the file is gone.
- **Delivery makes `read` no longer a pure passthrough.** The tool has an opinion about what a
  file is. That is a real complication in a tool whose contract should be boring, and it is
  contained by putting the note *after* the contents behind a clear marker, so a caller that does
  not care can ignore the tail.
- Writing a note is not automatic and is not going to be. The model decides something is worth
  recording, and a note written by a rule would be a note nobody wrote.
