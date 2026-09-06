"""What hera-code's tools need from the rest of the system, expressed as protocols.

This package **imports no other package in this workspace and never will** (ADR 4). It does not
reach for `hera_code_workspace`; it declares what it needs and takes it injected. The port belongs
to the consumer, so it says exactly what `read` requires and nothing about how a working tree is
found.

That is not tidiness. In v0.3.0 this server is exposed over a transport so hera can drive a coding
agent running elsewhere, and the only thing that should change then is which transport — not what
the tools are, and not what they can reach.

All of them are async because the implementations touch a filesystem or spawn a process, and a
synchronous port would force every one of them through a thread later.

**Every port is optional.** A deployment that wires none of them still lists every tool, and the
unwired ones answer *not available here* as a tool error the model can read and work around. A
model that cannot see `read` concludes it cannot read files and says so to the person, which is
worse than a tool that says why.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class FileText:
    """One file's contents, as `read` hands them back.

    A dataclass rather than a string because a note will travel beside the text in v0.2.0 M2
    (ADR 9), and widening a return type later is a change at every call site. The field exists
    now and is empty; nothing has to move when it fills.
    """

    path: str
    """Relative to the working tree — what a person reads and what the model should quote back."""

    text: str
    lines: int = 0
    truncated: bool = False
    """Whether this is less than the whole file. Said out loud rather than implied, because a
    model reasoning about a file it has only half of is the expensive kind of wrong."""

    note: str = ""
    """The shadow note for this path, delivered with the file rather than fetched (ADR 9).
    Empty until v0.2.0 M2."""


@dataclass(frozen=True, slots=True)
class Match:
    """One line that matched a search."""

    path: str
    line: int
    text: str


@dataclass(frozen=True, slots=True)
class Ran:
    """What a shell command did."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int = 0
    timed_out: bool = False


@runtime_checkable
class Files(Protocol):
    """Reading and changing files inside one working tree.

    Every method takes a path the **model** wrote, so every implementation resolves it through the
    workspace guard before touching anything. This protocol says nothing about how — that is the
    application's, and it is why a path is a `str` here rather than a `Path`: what crosses this
    seam is what the model typed.
    """

    async def read(self, path: str, *, offset: int = 0, limit: int = 0) -> FileText:
        """One file's contents. `limit` of `0` means as much as the implementation will give.

        Raise when the path is outside the tree, missing, or not text. Each of those is a
        different sentence the model can act on, and flattening them into one is what makes an
        agent retry the same call.
        """
        ...

    async def write(self, path: str, text: str) -> int:
        """Write one file whole, creating parents. Returns its size in bytes."""
        ...

    async def edit(self, path: str, find: str, replace: str) -> int:
        """Replace one passage. Returns the new size in bytes.

        ``find`` must match **exactly once**. Zero matches and several are both refusals: a
        replacement that hit the wrong one of three is a silent corruption, and the model cannot
        see the file to notice. The refusal says which of the two happened and how many were
        found, because *be more specific* is only actionable with a count.
        """
        ...

    async def glob(self, pattern: str, *, limit: int = 0) -> Sequence[str]:
        """Paths matching a glob, most recently modified first.

        Newest first because the question behind a glob is almost always *what is being worked
        on*, and alphabetical order answers a different one.
        """
        ...

    async def grep(
        self, pattern: str, *, path: str = "", glob: str = "", limit: int = 0
    ) -> Sequence[Match]:
        """Lines matching a regular expression.

        Raise on a pattern that does not compile, with the regex engine's own complaint — the
        model wrote the pattern and can fix it.
        """
        ...


@runtime_checkable
class Shell(Protocol):
    """Running a command in the working tree.

    One method, and the thing to know about it is in ADR 11: this is the tool the permission
    default exists for. It is `ask` by default and every invocation costs a card, until there is
    a sandbox (v0.3.0).
    """

    async def run(self, command: str, *, timeout_s: float = 0) -> Ran:
        """Run one command and return what it did.

        **A non-zero exit is not an exception.** The tool worked and the command said no, which is
        information the model acts on — raising would turn *the tests failed* into *the tool
        failed*, and those want different next moves. Raise only when the command could not be
        run at all.
        """
        ...
