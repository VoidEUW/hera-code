"""What we are working on, composed into one string.

`SLOT_PROJECT` is `hera_profiles`' own slot and its stated meaning is *what we are working on*.
The working tree, the instruction files a person wrote, the todo list, the shadow index and the
graph's freshness are all exactly that — so all of them go here, and **no vendored package needs a
line changed** to make room for them. That is the seam ADR 5 is about, and this module is the
whole of it.

What lands when:

===========  ==========================================================================
v0.1.0 M1    the preamble, and where we are
v0.1.0 M2    the instruction files — AGENT.md, AGENTS.md, CLAUDE.md
v0.1.0 M4    the todo list
v0.2.0 M2    the sketch and thought index
v0.2.0 M3    what the graph knows, and how fresh it is
===========  ==========================================================================

**Composed under a ceiling from the start**, because it only grows. A slot that silently exceeded
the context window would fail as a turn that forgot its instructions, which looks exactly like a
model that ignored them.

The sections are XML-tagged because the target deployment is a model with enough capacity for
structure, and a labelled block is what lets a model tell *what you told me to do* from *what is
currently on the list*. This is not a parser and never reads anything back: `hera_prompts` takes
the result as an opaque pre-rendered string through a named slot, which is the only way foreign
content is allowed in.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from hera_code_workspace import Workspace

PREAMBLE = """\
You are working in a terminal, on a checkout of real code that a person is also editing.

- The deliverable is a change to the working tree, not a description of one. Prefer editing a \
file over explaining what you would put in it.
- Read before you write. Say what you could not establish rather than guessing at it — a \
confident wrong path costs more here than an admission.
- Keep prose short. What is worth reading is the diff and the one sentence saying why.
- When something is genuinely ambiguous and the two readings lead to different code, ask. Do not \
ask about anything that does not change what gets built.\
"""
"""The fixed part, and the only prose hera-code puts in a prompt that is not somebody's file.

Four sentences, because this competes for the same attention the person's own instructions want.
Anything here that would still be true in a chat window belongs in a mind region instead
(:mod:`hera_code.profile` states that line).
"""

DEFAULT_CEILING = 12_000
"""Characters, not tokens, and that is deliberate.

Tokens would need a tokeniser, the tokeniser depends on the model, and there is no target model
(ADR 2) — so a character budget is the honest approximation. `hera_prompts` has a real token
budget for the parts it owns; this is a guard on one slot, sized so that instruction files and a
todo list fit comfortably and a repository that has committed a novel to `CLAUDE.md` does not
silently eat the window.
"""


@dataclass
class Section:
    """One labelled block of the slot."""

    tag: str
    body: str

    def render(self) -> str:
        return f"<{self.tag}>\n{self.body.strip()}\n</{self.tag}>"


@dataclass
class ProjectContext:
    """Everything `SLOT_PROJECT` will carry, and what had to be dropped to fit.

    `dropped` is not diagnostics. A slot that quietly truncated would fail as a model that
    ignored an instruction, which is indistinguishable from a model that read it and disagreed —
    so what did not fit is reported, and `check` and the terminal can both say so.
    """

    sections: list[Section] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    def render(self) -> str:
        return "\n\n".join(section.render() for section in self.sections)


def build(
    *,
    root: Path | None = None,
    workspace: Workspace | None = None,
    instructions: str = "",
    todos: str = "",
    notes: str = "",
    graph: str = "",
    ceiling: int = DEFAULT_CEILING,
) -> ProjectContext:
    """Compose the slot, in the order a model should read it.

    Every argument but ``root`` is a **pre-rendered string** supplied by whoever owns it, and
    empty means the section is left out entirely rather than rendered empty. A model told
    ``<todos></todos>`` concludes there is an empty list; a model told nothing concludes there is
    no list, which is the true thing.

    Order matters and is not alphabetical. The preamble is first because it frames everything
    after it; the person's own instructions come next because they outrank ours; the todo list is
    last of the always-present sections because it is the thing that changes every turn and the
    thing a model should be looking at when it starts work.
    """
    if workspace is None and root is not None:
        # A bare root is still a working tree. Accepted so a caller that has only a path -- a
        # test, or `-p` before discovery -- does not have to construct one.
        workspace = Workspace(root=root)

    candidates = [
        Section("how-you-work", PREAMBLE),
        Section("where-we-are", where(workspace)),
        Section("instructions", instructions),
        Section("what-the-index-knows", graph),
        Section("notes-you-have-kept", notes),
        Section("todos", todos),
    ]

    context = ProjectContext()
    spent = 0
    for section in candidates:
        if not section.body.strip():
            continue
        rendered = section.render()
        # The preamble is never dropped. A ceiling small enough to exclude it is a
        # misconfiguration, and the failure it would produce -- an agent with no instructions at
        # all -- is worse than being one section over budget.
        if spent + len(rendered) > ceiling and section.tag != "how-you-work":
            context.dropped.append(section.tag)
            continue
        context.sections.append(section)
        spent += len(rendered) + 2
    return context


def where(workspace: Workspace | None) -> str:
    """The working tree, as one or two lines.

    The branch and the dirty count are here because they change what a sensible next step is: an
    agent about to make a sweeping change should know there are already twelve uncommitted files,
    and one on `main` should know that too.
    """
    if workspace is None:
        return ""
    lines = [f"The working tree is {workspace.root}."]
    if workspace.is_repository:
        state = f"On branch {workspace.branch}" if workspace.branch else "In a git repository"
        if workspace.dirty:
            plural = "" if workspace.dirty == 1 else "s"
            state += f", with {workspace.dirty} uncommitted change{plural}"
        lines.append(state + ".")
    else:
        lines.append("It is not a git repository, so there is nothing to revert a change with.")
    return "\n".join(lines)


def sections_of(context: ProjectContext) -> Iterator[str]:
    """The tags present, for a test or a status line to assert on."""
    return (section.tag for section in context.sections)
