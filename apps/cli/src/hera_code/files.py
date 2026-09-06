"""Reading and changing files in the working tree.

The application's side of :class:`hera_code_mcp.Files`. `hera_code_mcp` declares what it needs and
imports nothing of ours; this is what it needs, holding a `Workspace`.

**Every path goes through `Workspace.resolve` before anything is touched**, and that is the only
containment check in the system — one place, so there is one answer to *is this inside the tree*.

Every refusal here is read by a **model**, so every one of them says what was wrong and what would
be right. A refusal a model cannot act on is a refusal it repeats.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from pathlib import Path

from hera_code_mcp import FileText, Match
from hera_code_workspace import OutsideWorkspace, Workspace

MAX_READ_BYTES = 5_000_000
"""A file bigger than this is refused rather than read.

Not a context-window concern — `limit` handles that. This is about not pulling a 2 GB fixture into
memory to hand back the first two thousand lines of it.
"""

BINARY_SNIFF = 8_000
"""How much of a file is examined to decide whether it is text.

A NUL byte in the first few KB is the practical test. It is not perfect and does not need to be:
what it prevents is a model being handed a screenful of mojibake and reasoning about it.
"""


class WorkingTree:
    """:class:`hera_code_mcp.Files`, over a real directory."""

    def __init__(self, workspace: Workspace, *, ignored: Sequence[str] = ()) -> None:
        self._workspace = workspace
        self._ignored = tuple(ignored)

    # -- reading ---------------------------------------------------------------------------

    async def read(self, path: str, *, offset: int = 0, limit: int = 0) -> FileText:
        return await asyncio.to_thread(self._read, path, offset, limit)

    def _read(self, path: str, offset: int, limit: int) -> FileText:
        target = self._resolve(path)
        if target.is_dir():
            raise IsADirectoryError(f"{path} is a directory. Use `glob` to see what is in it.")
        if not target.exists():
            raise FileNotFoundError(f"{path} does not exist")

        size = target.stat().st_size
        if size > MAX_READ_BYTES:
            raise ValueError(
                f"{path} is {size} bytes, which is too large to read. "
                "Use `grep` to find what you need in it."
            )
        raw = target.read_bytes()
        if b"\0" in raw[:BINARY_SNIFF]:
            raise ValueError(f"{path} is not a text file")

        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        offset = max(offset, 0)
        window = lines[offset:] if limit <= 0 else lines[offset : offset + limit]

        # Numbered from one, and from the *offset*, so a line number in the output is the line
        # number in the file. A model quoting `api.py:42` has to be right about 42.
        numbered = "\n".join(f"{offset + i + 1:>6}  {line}" for i, line in enumerate(window))
        return FileText(
            path=str(self._workspace.relative(target)),
            text=numbered,
            lines=len(window),
            truncated=offset + len(window) < len(lines),
        )

    # -- changing --------------------------------------------------------------------------

    async def write(self, path: str, text: str) -> int:
        return await asyncio.to_thread(self._write, path, text)

    def _write(self, path: str, text: str) -> int:
        target = self._resolve(path)
        if target.is_dir():
            raise IsADirectoryError(f"{path} is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return len(text.encode("utf-8"))

    async def edit(self, path: str, find: str, replace: str) -> int:
        return await asyncio.to_thread(self._edit, path, find, replace)

    def _edit(self, path: str, find: str, replace: str) -> int:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"{path} does not exist")
        if not find:
            raise ValueError("`find` is empty. Use `write` to replace a file whole.")

        text = target.read_text(encoding="utf-8")
        count = text.count(find)
        if count == 0:
            raise ValueError(
                f"`find` does not appear in {path}. Read the file and copy the passage "
                "exactly, including its indentation."
            )
        if count > 1:
            # The count is the actionable part. "Be more specific" without it is advice; with it
            # the model knows how much more context it has to include.
            raise ValueError(
                f"`find` appears {count} times in {path} and must appear once. "
                "Include more of the surrounding lines to make it unique."
            )

        target.write_text(text.replace(find, replace, 1), encoding="utf-8")
        return target.stat().st_size

    # -- finding ---------------------------------------------------------------------------

    async def glob(self, pattern: str, *, limit: int = 0) -> Sequence[str]:
        return await asyncio.to_thread(self._glob, pattern, limit)

    def _glob(self, pattern: str, limit: int) -> Sequence[str]:
        root = self._workspace.root
        found = [
            path
            for path in self._workspace.walk(ignored=self._ignored)
            if path.relative_to(root).match(pattern) or _globs(path.relative_to(root), pattern)
        ]
        # Newest first: the question behind a glob is almost always *what is being worked on*,
        # and alphabetical order answers a different one.
        found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        if limit > 0:
            found = found[:limit]
        return [str(path.relative_to(root)) for path in found]

    async def grep(
        self, pattern: str, *, path: str = "", glob: str = "", limit: int = 0
    ) -> Sequence[Match]:
        return await asyncio.to_thread(self._grep, pattern, path, glob, limit)

    def _grep(self, pattern: str, path: str, glob: str, limit: int) -> Sequence[Match]:
        try:
            expression = re.compile(pattern)
        except re.error as exc:
            # The model wrote the pattern and can fix it, so it gets the engine's own complaint
            # rather than "invalid pattern".
            raise ValueError(f"{pattern} is not a valid regular expression: {exc}") from exc

        root = self._workspace.root
        within = self._resolve(path) if path else root
        matches: list[Match] = []
        for candidate in self._workspace.walk(ignored=self._ignored):
            if within != root and within not in candidate.parents:
                continue
            relative = candidate.relative_to(root)
            if glob and not _globs(relative, glob):
                continue
            matches.extend(_search(candidate, relative, expression))
            if limit > 0 and len(matches) >= limit:
                return matches[:limit]
        return matches

    # -- one guard -------------------------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        """The one containment check, and the one place it happens.

        `OutsideWorkspace` is re-raised as itself rather than wrapped: ADR 11 makes it the refusal
        that is *not* a decision for a person, so it must stay distinguishable all the way up.
        """
        try:
            return self._workspace.resolve(path)
        except OutsideWorkspace:
            raise


def _globs(relative: Path, pattern: str) -> bool:
    """Whether one relative path matches a glob, `**` included.

    `Path.match` does not handle a leading `**/` the way a person expects, so `full_match` is used
    where it exists and the plain match is the fallback.
    """
    # `full_match` is 3.13+; it is the one that handles a leading `**/` the way a person writing
    # `**/test_*.py` expects. On 3.12 the fallback is `match` plus a prefix check, which gets the
    # common cases and is honestly worse -- both interpreters are supported, so both are here.
    full_match = getattr(relative, "full_match", None)
    if full_match is not None:
        return bool(full_match(pattern))
    return bool(relative.match(pattern)) or relative.as_posix().startswith(pattern.rstrip("*"))


def _search(path: Path, relative: Path, expression: re.Pattern[str]) -> list[Match]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    if b"\0" in raw[:BINARY_SNIFF]:
        return []
    found = []
    for number, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), start=1):
        if expression.search(line):
            # Trimmed, because a minified bundle on one line would otherwise put the whole file
            # into the context window through a search that matched once.
            found.append(Match(path=str(relative), line=number, text=line.strip()[:400]))
    return found
