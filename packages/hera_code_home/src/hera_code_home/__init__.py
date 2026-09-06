"""Where hera-code keeps its data, and the well-known paths inside it.

There are **two** roots here, and the split is the whole design of this module.

``~/.hera`` is hera's, and hera-code shares it: the mind repository, the skills directory,
``mcp.json`` and ``config.toml`` are the same files both applications read, and hera-code creates
them if no hera install has. Those paths come from :mod:`hera_home` and this module does not
repeat them.

``~/.hera/code`` is hera-code's alone — sessions, its own settings, the graph index — and
``<working tree>/.hera`` belongs to one repository: the todo list, the shadow tree, the sketches
and the thoughts. Neither is anything hera should read, which is why they are somewhere hera does
not look.

Like :mod:`hera_home`, this reads the environment on every call and caches nothing. A cached home
would be captured at import time, which is before a test fixture has had a chance to point it
somewhere temporary — and the failure mode of getting that wrong is writing into a real
``~/.hera`` during a test run.
"""

from __future__ import annotations

from pathlib import Path

from hera_home import home

CODE_DIRNAME = "code"
"""hera-code's own directory, inside hera's. A subdirectory rather than a sibling because
``HERA_HOME`` should move both at once: a person who pointed hera at a different disk did not
mean to leave the coding agent behind on the old one."""

PROJECT_DIRNAME = ".hera"
"""What one working tree calls the directory hera-code keeps its thinking in."""

SESSIONS_FILENAME = "sessions.sqlite3"
CONFIG_FILENAME = "config.toml"
INSTRUCTIONS_FILENAME = "AGENT.md"
GRAPH_DIRNAME = "graph"
TODOS_FILENAME = "TODOS.md"
SHADOW_DIRNAME = "shadow"
SKETCHES_DIRNAME = "sketches"
THOUGHTS_DIRNAME = "thoughts"

__all__ = [
    "CODE_DIRNAME",
    "CONFIG_FILENAME",
    "GRAPH_DIRNAME",
    "INSTRUCTIONS_FILENAME",
    "PROJECT_DIRNAME",
    "SESSIONS_FILENAME",
    "SHADOW_DIRNAME",
    "SKETCHES_DIRNAME",
    "THOUGHTS_DIRNAME",
    "TODOS_FILENAME",
    "code_config_path",
    "code_home",
    "graph_dir",
    "graph_path",
    "project_dir",
    "sessions_db_path",
    "shadow_dir",
    "shadow_path",
    "sketches_dir",
    "thoughts_dir",
    "todos_path",
    "user_instructions_path",
]


# -- ~/.hera/code, which is hera-code's ------------------------------------------------------


def code_home() -> Path:
    """hera-code's own directory. Everything hera has no business reading lives under here."""
    return home() / CODE_DIRNAME


def sessions_db_path() -> Path:
    """The SQLite file holding sessions and their persisted event streams.

    Its own database rather than a table in ``hera.sqlite3``, and the reason is not tidiness: a
    coding agent writes a turn every few seconds, and sharing a SQLite file with a running web
    application is how both learn what ``database is locked`` means.
    """
    return code_home() / SESSIONS_FILENAME


def code_config_path() -> Path:
    """hera-code's settings — which endpoint is active, and how it behaves in a terminal.

    Separate from ``~/.hera/config.toml``, which stays shared: an endpoint registered for hera is
    one hera-code can use, and the *choice* of which one is active is not the same choice in a
    chat window as in a terminal.
    """
    return code_home() / CONFIG_FILENAME


def user_instructions_path() -> Path:
    """Instructions that apply in every working tree, written by a person.

    ``AGENT.md`` rather than ``CLAUDE.md`` here, because this file is nobody else's convention to
    honour — the repository-level lookup reads all three names, and that is where compatibility
    belongs.
    """
    return code_home() / INSTRUCTIONS_FILENAME


def graph_dir() -> Path:
    """Where the code graph is cached, one database per working tree."""
    return code_home() / GRAPH_DIRNAME


def graph_path(digest: str) -> Path:
    """One working tree's graph index, named after a digest of its root.

    Guarded the way :func:`hera_home.chat_dir` guards a chat id. The digest is computed by the
    caller, so this cannot assume it is hex — and a ``..`` arriving here would put a database
    somewhere nobody would think to look for it.
    """
    if not digest or digest in {".", ".."} or "/" in digest or "\\" in digest:
        raise ValueError(f"not a usable graph digest: {digest!r}")
    return graph_dir() / f"{digest}.sqlite3"


# -- <working tree>/.hera, which is one repository's ------------------------------------------


def project_dir(root: Path) -> Path:
    """The directory hera-code keeps its thinking about one working tree in.

    Inside the tree rather than under ``~/.hera/code``, and that is the decision: the todo list
    and the shadow notes are *about this code*, they are worth reading in a diff, and a person
    who clones the repository somewhere else should get them. Whether they are committed is
    theirs to decide — hera-code never edits a ``.gitignore``.
    """
    return root / PROJECT_DIRNAME


def todos_path(root: Path) -> Path:
    """The run's todo list, as Markdown a person can edit in their own editor."""
    return project_dir(root) / TODOS_FILENAME


def shadow_dir(root: Path) -> Path:
    """The shadow tree: one note per source file, mirroring the tree's own shape."""
    return project_dir(root) / SHADOW_DIRNAME


def shadow_path(root: Path, relative: Path | str) -> Path:
    """The shadow note for one source file, at the same relative path with ``.md`` appended.

    ``src/api/routes.py`` becomes ``.hera/shadow/src/api/routes.py.md``. The extension is kept
    rather than replaced, so ``routes.py`` and ``routes.ts`` do not share a note.

    ``relative`` must stay inside the shadow tree. It reaches this from a tool call, and the
    answer to how much this function trusts it is **not at all**.
    """
    path = Path(relative)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(f"not a usable path inside the working tree: {relative!r}")
    return shadow_dir(root) / f"{path.as_posix()}.md"


def sketches_dir(root: Path) -> Path:
    """Half-formed plans and pre-thoughts, not tied to any one file."""
    return project_dir(root) / SKETCHES_DIRNAME


def thoughts_dir(root: Path) -> Path:
    """Conclusions worth keeping after the run that reached them has ended."""
    return project_dir(root) / THOUGHTS_DIRNAME
