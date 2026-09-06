"""The working tree: where it is, what state it is in, and what may be reached inside it."""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from hera_code_workspace.errors import OutsideWorkspace

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".next",
        ".idea",
        ".DS_Store",
    }
)
"""Never walked, whatever `.gitignore` says.

A fixed list rather than a clever heuristic, and short on purpose. Each entry is somewhere that
holds thousands of files nobody is going to edit, and walking one turns `glob` from an answer into
a denial-of-service against the context window.

`.git` is here twice over: it is huge, and its contents are the one place in a repository where a
stray write is unrecoverable.
"""

GIT_TIMEOUT_S = 5.0
"""How long `git` gets. Short, because every call here is metadata about a local directory.

A repository on a stalled network mount is the case this exists for: the status line is not worth
hanging the launch over, and every caller treats a timeout as *no git information* rather than as
a failure.
"""


@dataclass(frozen=True)
class Workspace:
    """One working tree, and what is true of it right now.

    Frozen, and the git fields are a snapshot rather than properties: a status line that re-shelled
    out on every repaint would run `git status` several times a second.
    """

    root: Path
    branch: str = ""
    """Empty when this is not a git repository, or when git could not say. Not `None` — there is
    nothing a caller would do differently, and `if workspace.branch` reads better than a check
    against `None` in a status line."""

    dirty: int = 0
    """How many paths `git status --porcelain` reports. Zero for a clean tree *and* for a
    directory that is not a repository, which is why :attr:`is_repository` exists separately."""

    is_repository: bool = False

    def resolve(self, path: str | Path) -> Path:
        """One path inside this tree, absolute and real, or :class:`OutsideWorkspace`.

        **The single place that decides a path is inside the tree.** Everything that touches a
        file goes through here.

        Symlinks are resolved *before* the check, and that is the whole point rather than a
        detail: a link inside the tree pointing at `/etc/passwd` is the interesting case, and a
        guard that compared the string before resolving would wave it through. It costs a `stat`
        per call, which is nothing next to what it prevents.

        A path that does not exist yet still resolves — `write` has to be able to create a file.
        `Path.resolve()` is non-strict, so a missing leaf is fine while a symlinked *parent* is
        still followed.
        """
        candidate = Path(path)
        absolute = candidate if candidate.is_absolute() else self.root / candidate
        resolved = absolute.resolve()
        root = self.root.resolve()
        if resolved != root and root not in resolved.parents:
            raise OutsideWorkspace(
                f"{path} is outside the working tree at {root}. "
                "Only files inside it can be reached."
            )
        return resolved

    def relative(self, path: str | Path) -> Path:
        """A resolved path as the tree sees it — what goes in a message a person reads."""
        return self.resolve(path).relative_to(self.root.resolve())

    def contains(self, path: str | Path) -> bool:
        """Whether :meth:`resolve` would accept it. For a caller that wants a bool, not a raise."""
        try:
            self.resolve(path)
        except OutsideWorkspace:
            return False
        return True

    def walk(self, *, ignored: Sequence[str] = ()) -> Iterator[Path]:
        """Every file in the tree, absolute, with the uninteresting directories pruned.

        `ignored` is extra glob patterns on top of :data:`IGNORED_DIRECTORIES` — what the caller
        read out of a `.gitignore`. Matched against the path *relative to the root*, so a pattern
        means the same thing it means in the file it came from.

        Pruned during the walk rather than filtered afterwards, which is the difference between
        skipping `node_modules` and reading all of it before throwing it away.
        """
        yield from _walk(self.root, self.root, tuple(ignored))


def _walk(directory: Path, root: Path, ignored: tuple[str, ...]) -> Iterator[Path]:
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        # A directory we cannot read is one we skip. Permission denied somewhere in a tree is
        # ordinary, and it is not a reason for the whole walk to fail.
        return
    for entry in entries:
        if entry.name in IGNORED_DIRECTORIES:
            continue
        relative = entry.relative_to(root).as_posix()
        if _matches(relative, ignored):
            continue
        if entry.is_symlink():
            # Not followed. A link into a directory that contains the tree is an infinite walk,
            # and a link out of it is something `resolve` would refuse anyway.
            continue
        if entry.is_dir():
            yield from _walk(entry, root, ignored)
        elif entry.is_file():
            yield entry


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    """Whether one relative path matches any pattern.

    Deliberately **not** a `.gitignore` implementation. The full format has negation, anchoring,
    directory-only rules and precedence, and reimplementing it badly would be worse than not
    having it: a half-right ignore file hides a file the person can see. What this does is plain
    globbing, and the caller says what patterns to pass.
    """
    if not patterns:
        return False
    name = relative.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns
    )


def git_root(start: Path) -> Path | None:
    """The enclosing repository's root, or ``None`` if there is not one.

    ``None`` is an ordinary answer: a directory that is not a repository is a working tree
    hera-code can be pointed at, and refusing it would be refusing the case where somebody is
    starting something new.
    """
    found = _git(start, "rev-parse", "--show-toplevel")
    return Path(found).resolve() if found else None


def discover(start: Path | None = None) -> Workspace:
    """The working tree containing ``start``, falling back to ``start`` itself.

    The fallback is the decision: no repository means the current directory *is* the tree, rather
    than an error. Somebody running hera-code in a scratch folder means that folder.
    """
    start = (start if start is not None else Path.cwd()).resolve()
    root = git_root(start)
    if root is None:
        return Workspace(root=start)
    return Workspace(
        root=root,
        branch=_branch(root),
        dirty=len([line for line in _git(root, "status", "--porcelain").splitlines() if line]),
        is_repository=True,
    )


def _branch(root: Path) -> str:
    """The current branch, or the short commit on a detached HEAD, or empty.

    `branch --show-current` first, because it is the only one that answers on a repository with
    **no commits yet** — a freshly `git init`ed directory is on `main` and `rev-parse HEAD` fails
    there, which used to report no branch at all for the case somebody is most likely to be in on
    the first day of a project.

    A detached HEAD shows the commit rather than nothing, because *what am I on* has an answer
    there and `HEAD` is not it.
    """
    current = _git(root, "branch", "--show-current")
    if current:
        return current
    name = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if name and name != "HEAD":
        return name
    return _git(root, "rev-parse", "--short", "HEAD")


def _git(cwd: Path, *args: str) -> str:
    """One git command, or ``""`` if it did not work.

    Every failure is the same answer — no git information — and that is deliberate. Not a
    repository, git not installed, a stalled network mount and a corrupt index are four different
    problems and none of them is one hera-code can do anything about, so none of them stops it
    from working on the directory.
    """
    try:
        # A fixed argv with no shell, so nothing a model wrote can become a command: `args` is
        # always a literal at every call site in this module. `git` is resolved from PATH rather
        # than pinned, because a person using a version manager has a git that is not /usr/bin/git
        # and pinning would break them to guard against a PATH they already control.
        finished = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return finished.stdout.strip() if finished.returncode == 0 else ""
