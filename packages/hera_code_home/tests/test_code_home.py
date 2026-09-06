"""``hera_code_home`` answers where things are, and refuses two arguments it is handed."""

from __future__ import annotations

from pathlib import Path

import pytest

from hera_code_home import (
    code_config_path,
    code_home,
    graph_dir,
    graph_path,
    project_dir,
    sessions_db_path,
    shadow_dir,
    shadow_path,
    sketches_dir,
    thoughts_dir,
    todos_path,
    user_instructions_path,
)


def test_code_home_follows_hera_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A person who moved ``HERA_HOME`` moved hera-code with it."""
    monkeypatch.setenv("HERA_HOME", str(tmp_path))
    assert code_home() == tmp_path / "code"
    assert sessions_db_path() == tmp_path / "code" / "sessions.sqlite3"
    assert code_config_path() == tmp_path / "code" / "config.toml"
    assert user_instructions_path() == tmp_path / "code" / "AGENT.md"


def test_nothing_is_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Asking where something is does not decide to make it."""
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "absent"))
    code_home()
    sessions_db_path()
    assert not (tmp_path / "absent").exists()


def test_the_environment_is_read_on_every_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nothing is cached at import time, so a fixture can still redirect it."""
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "one"))
    first = code_home()
    monkeypatch.setenv("HERA_HOME", str(tmp_path / "two"))
    assert code_home() != first


def test_a_working_tree_keeps_its_thinking_inside_itself(tmp_path: Path) -> None:
    assert project_dir(tmp_path) == tmp_path / ".hera"
    assert todos_path(tmp_path) == tmp_path / ".hera" / "TODOS.md"
    assert shadow_dir(tmp_path) == tmp_path / ".hera" / "shadow"
    assert sketches_dir(tmp_path) == tmp_path / ".hera" / "sketches"
    assert thoughts_dir(tmp_path) == tmp_path / ".hera" / "thoughts"


def test_a_shadow_note_mirrors_the_tree_and_keeps_the_extension(tmp_path: Path) -> None:
    """``routes.py`` and ``routes.ts`` are two files and get two notes."""
    assert shadow_path(tmp_path, "src/api/routes.py") == (
        tmp_path / ".hera" / "shadow" / "src" / "api" / "routes.py.md"
    )
    assert shadow_path(tmp_path, "src/routes.ts") != shadow_path(tmp_path, "src/routes.py")


@pytest.mark.parametrize("bad", ["../outside.py", "/etc/passwd", "src/../../escape.py"])
def test_a_shadow_path_refuses_to_leave_the_tree(tmp_path: Path, bad: str) -> None:
    """It arrives from a tool call, so it is not trusted."""
    with pytest.raises(ValueError, match="not a usable path"):
        shadow_path(tmp_path, bad)


def test_the_graph_is_cached_outside_the_working_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The one derived thing, and the one thing not kept in the tree (ADR 7).

    Large, machine-readable, and safe to delete — none of which is true of the todo list or a
    shadow note.
    """
    monkeypatch.setenv("HERA_HOME", str(tmp_path))
    assert graph_dir() == tmp_path / "code" / "graph"
    assert graph_path("abc123") == tmp_path / "code" / "graph" / "abc123.sqlite3"


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b"])
def test_a_graph_digest_refuses_anything_that_is_not_one_segment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
) -> None:
    monkeypatch.setenv("HERA_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="not a usable graph digest"):
        graph_path(bad)
