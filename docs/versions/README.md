# Version documents

One file per version, written **before** the work rather than after it: what that version is for,
what lands in it, in what order, and what is deliberately left out.

This is not `docs/status.md` and not `CHANGELOG.md`, and the three are easy to collapse into each
other by accident:

| | Answers | Tense |
|---|---|---|
| `docs/versions/vX.Y.Z.md` | *What are we building, and why in this order* | Future. Frozen once the version ships |
| [`docs/status.md`](../status.md) | *Where does the build stand right now* | Present. A snapshot, rewritten as milestones land |
| [`CHANGELOG.md`](../../CHANGELOG.md) | *What changed, for somebody who was not here* | Past. Append-only |

A version document stops being edited when its tag is cut. If the plan turned out wrong, that is
worth reading later — the reasoning is the point, and a document quietly corrected after the fact
teaches nothing. Corrections go into the next version's document, or into an ADR when they change
the shape of the system.

**The milestones are the plan; these documents say why.** A version document is frozen and issues
are not, so where the two disagree the issues are right and this is a record of what was believed
at the time. See [ADR 6](../adr/0006-github-flow-and-milestones-are-the-plan.md).

*Before* the tag is cut a plan that changes says so **in place**, and keeps its milestone numbers.
M4 means the todo list forever, even if what is in it changes: renumbering after the fact makes
every commit message and status entry that says M4 wrong, and dropping one silently is what turns
*we decided not to* into *we forgot*.

| | |
|---|---|
| [v0.1.0](v0.1.0.md) | A coding agent that works: everything wired, and a todo list you can read |
| [v0.2.0](v0.2.0.md) | The look, and the memory of a run: the visual pass, the shadow tree, the graph |
| [v0.3.0](v0.3.0.md) | Reachable: hera drives hera-code, and where code runs |
