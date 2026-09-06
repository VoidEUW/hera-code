"""What a person has already written down about how to work in this repository.

**hera-code reads the file you already have.** `AGENT.md`, `AGENTS.md` and `CLAUDE.md` are all
read at the root — every one that exists, in that order — so a repository set up for another
coding agent needs no new file. That is the requirement, and it is why this reads three names
rather than inventing a fourth.

`~/.hera/code/AGENT.md` comes first, as instruction that applies in every tree.

Each source is labelled when it is rendered, because *you wrote this for every project* and *you
wrote this for this repository* are different claims on the model's attention and it should be
able to tell them apart.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

INSTRUCTION_FILENAMES: tuple[str, ...] = ("AGENT.md", "AGENTS.md", "CLAUDE.md")
"""Read at the root, in this order, all of them.

Order is the order they are rendered in and nothing more — none of them wins over another,
because a person with two of these files meant both. `AGENT.md` is first because it is the name
hera-code would suggest; `CLAUDE.md` is last and is the one most likely to already be there.

**Not a lookup that stops at the first hit.** Somebody with a short `AGENT.md` beside a long
`CLAUDE.md` has not asked for the second to be ignored, and silently dropping it would be the kind
of helpfulness nobody can debug.
"""

MAX_INSTRUCTION_BYTES = 64_000
"""How much of one file is read.

A ceiling rather than a limit that truncates quietly: what does not fit is *reported*, so a
repository whose `CLAUDE.md` has become a manual gets told rather than getting a prompt with half
a sentence in it. The project slot has its own, smaller ceiling on top of this
(`hera_code.context`); this one only stops a pathological file being read into memory at all.
"""


@dataclass(frozen=True)
class InstructionSource:
    """One instruction file that was found."""

    path: Path
    text: str
    scope: str
    """`user` for `~/.hera/code/AGENT.md`, `project` for one at the root. What the label says."""

    truncated: bool = False


@dataclass
class Instructions:
    """Every instruction file that applies here, and anything wrong with them."""

    sources: list[InstructionSource] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    """Files that exist and could not be used. **Reported, never silently skipped** — an
    instruction file a person wrote and that did not arrive is the failure they would take
    longest to find."""

    def render(self) -> str:
        """The text as it goes into the prompt, each source labelled with where it came from."""
        blocks = []
        for source in self.sources:
            where = "every project" if source.scope == "user" else source.path.name
            blocks.append(f"From {where}:\n\n{source.text.strip()}")
        return "\n\n---\n\n".join(blocks)

    def __bool__(self) -> bool:
        return bool(self.sources)


def instructions(root: Path, *, user_file: Path | None = None) -> Instructions:
    """Read every instruction file that applies to work in ``root``.

    Duplicates are dropped on a **content hash**, not on a filename: somebody who symlinked
    `AGENT.md` to `CLAUDE.md`, or copied one into the other, should not pay for it twice in every
    prompt. Two files with genuinely different words are two files and both are kept.

    Nested per-directory files are v0.2.0 M5. The shape here — a list of sources rather than one
    string, each carrying its path — is what that grows into: another source appended when a
    directory is touched, with no change to what the caller does with the result.
    """
    found = Instructions()
    seen: set[str] = set()

    candidates: list[tuple[Path, str]] = []
    if user_file is not None:
        candidates.append((user_file, "user"))
    candidates.extend((root / name, "project") for name in INSTRUCTION_FILENAMES)

    for path, scope in candidates:
        source = _read(path, scope, found.problems)
        if source is None:
            continue
        digest = hashlib.sha256(source.text.strip().encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        found.sources.append(source)
    return found


def _read(path: Path, scope: str, problems: list[str]) -> InstructionSource | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        problems.append(f"{path} could not be read: {exc}")
        return None

    truncated = len(raw) > MAX_INSTRUCTION_BYTES
    if truncated:
        problems.append(
            f"{path} is {len(raw)} bytes; only the first {MAX_INSTRUCTION_BYTES} were read"
        )
        raw = raw[:MAX_INSTRUCTION_BYTES]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Truncation can cut a multi-byte character in half, so a decode failure here is not
        # necessarily a file that is not text. Either way the honest answer is the same.
        problems.append(f"{path} is not valid UTF-8: {exc}")
        return None

    if not text.strip():
        return None
    return InstructionSource(path=path, text=text, scope=scope, truncated=truncated)


def paths_of(found: Instructions) -> Iterable[Path]:
    """Where the instructions came from. For a status line, or for `check` to list."""
    return (source.path for source in found.sources)
