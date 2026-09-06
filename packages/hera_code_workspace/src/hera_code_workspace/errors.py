"""What this package raises.

Both are read by a **model**, through `ToolError`, so both are written for one: they say what was
wrong and what would be right, because a refusal a model cannot act on is a refusal it repeats.
"""

from __future__ import annotations


class WorkspaceError(RuntimeError):
    """Something about the working tree is wrong."""


class OutsideWorkspace(WorkspaceError):
    """A path resolved outside the root.

    Its own type because the caller has to be able to tell it apart: this is the one refusal that
    is **not a decision for a person**. ADR 11 draws that line — outside-the-tree is denied
    because it is outside the contract, not because it is risky, so it is never a permission card
    and `--yes` cannot reach it.
    """
