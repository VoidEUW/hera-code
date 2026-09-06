"""The working tree hera-code is pointed at.

Where its root is, what branch it is on, which files are worth walking, and what a person has
already written down about how to work in it. One question with several parts, and every part is
about *this directory* rather than about the agent — nothing here knows what a model, a turn or a
tool is.

**The instruction files are the part with somebody else's convention in it.** ``AGENT.md``,
``AGENTS.md`` and ``CLAUDE.md`` are all read at the root, every one that exists, in that order —
so a repository already set up for another coding agent needs no new file, which is the whole
requirement. ``~/.hera/code/AGENT.md`` prepends as instruction that applies everywhere.
Nested per-directory files are v0.2.0; :func:`instructions` is written to grow into them.

**Nothing outside the root is reachable**, and :func:`resolve` is the only place that decides so.
The guard lives here rather than in the tools that use it because a path arrives from a model and
there has to be exactly one answer to *is this inside the tree*.
"""

from __future__ import annotations

from hera_code_workspace.errors import OutsideWorkspace, WorkspaceError
from hera_code_workspace.instructions import (
    INSTRUCTION_FILENAMES,
    Instructions,
    InstructionSource,
    instructions,
)
from hera_code_workspace.tree import (
    IGNORED_DIRECTORIES,
    Workspace,
    discover,
    git_root,
    matches_glob,
)

__all__ = [
    "IGNORED_DIRECTORIES",
    "INSTRUCTION_FILENAMES",
    "InstructionSource",
    "Instructions",
    "OutsideWorkspace",
    "Workspace",
    "WorkspaceError",
    "discover",
    "git_root",
    "instructions",
    "matches_glob",
]
