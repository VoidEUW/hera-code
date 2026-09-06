"""Reading the instruction file a repository already has.

**The requirement is that no new file is needed.** A repository set up for another coding agent
has `CLAUDE.md` or `AGENTS.md` in it, and hera-code reads all three names rather than insisting on
its own — so most of this file is about *all of them* being read, not the first one found.
"""

from __future__ import annotations

from pathlib import Path

from hera_code_workspace.instructions import MAX_INSTRUCTION_BYTES, paths_of

from hera_code_workspace import INSTRUCTION_FILENAMES, instructions


def test_a_repository_with_only_claude_md_needs_no_new_file(tmp_path: Path) -> None:
    """**The whole requirement, in one test.**"""
    (tmp_path / "CLAUDE.md").write_text("Run the tests with `just test`.")

    found = instructions(tmp_path)

    assert found
    assert "just test" in found.render()


def test_every_file_that_exists_is_read(tmp_path: Path) -> None:
    """Not a lookup that stops at the first hit.

    Somebody with a short `AGENT.md` beside a long `CLAUDE.md` has not asked for the second to be
    ignored, and silently dropping it is the kind of helpfulness nobody can debug.
    """
    (tmp_path / "AGENT.md").write_text("one")
    (tmp_path / "AGENTS.md").write_text("two")
    (tmp_path / "CLAUDE.md").write_text("three")

    rendered = instructions(tmp_path).render()

    assert "one" in rendered
    assert "two" in rendered
    assert "three" in rendered


def test_they_are_rendered_in_the_declared_order(tmp_path: Path) -> None:
    for name in INSTRUCTION_FILENAMES:
        (tmp_path / name).write_text(name)

    rendered = instructions(tmp_path).render()
    positions = [rendered.index(name) for name in INSTRUCTION_FILENAMES]

    assert positions == sorted(positions)


def test_the_user_file_comes_first(tmp_path: Path) -> None:
    """`~/.hera/code/AGENT.md` applies in every tree, so it frames what follows."""
    user = tmp_path / "user.md"
    user.write_text("Always run the linter.")
    (tmp_path / "CLAUDE.md").write_text("This project uses ruff.")

    rendered = instructions(tmp_path, user_file=user).render()

    assert rendered.index("Always run the linter") < rendered.index("This project uses ruff")


def test_each_source_says_where_it_came_from(tmp_path: Path) -> None:
    """*You wrote this for every project* and *you wrote this for this repository* are different
    claims on the model's attention."""
    user = tmp_path / "user.md"
    user.write_text("global rule")
    (tmp_path / "CLAUDE.md").write_text("project rule")

    rendered = instructions(tmp_path, user_file=user).render()

    assert "every project" in rendered
    assert "CLAUDE.md" in rendered


def test_identical_content_is_read_once(tmp_path: Path) -> None:
    """Deduplicated on content, not on filename — somebody who copied one into the other should
    not pay for it twice in every prompt."""
    (tmp_path / "AGENT.md").write_text("Same words.\n")
    (tmp_path / "CLAUDE.md").write_text("  Same words.  \n\n")

    found = instructions(tmp_path)

    assert len(found.sources) == 1


def test_a_symlinked_duplicate_is_read_once(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("shared")
    (tmp_path / "AGENT.md").symlink_to(tmp_path / "CLAUDE.md")

    assert len(instructions(tmp_path).sources) == 1


def test_different_words_are_two_sources(tmp_path: Path) -> None:
    (tmp_path / "AGENT.md").write_text("one thing")
    (tmp_path / "CLAUDE.md").write_text("another thing")

    assert len(instructions(tmp_path).sources) == 2


def test_no_instruction_file_is_not_a_problem(tmp_path: Path) -> None:
    found = instructions(tmp_path)

    assert not found
    assert found.render() == ""
    assert not found.problems


def test_an_empty_file_contributes_nothing(tmp_path: Path) -> None:
    """An empty section tells a model there are no instructions; no section tells it nothing,
    which is the true thing."""
    (tmp_path / "CLAUDE.md").write_text("   \n\n")

    assert not instructions(tmp_path)


def test_an_enormous_file_is_reported_rather_than_silently_cut(tmp_path: Path) -> None:
    """**An instruction file a person wrote that did not arrive is the failure they would take
    longest to find.** So what did not fit is said out loud."""
    (tmp_path / "CLAUDE.md").write_text("x" * (MAX_INSTRUCTION_BYTES + 500))

    found = instructions(tmp_path)

    assert found.sources[0].truncated
    assert found.problems
    assert "only the first" in found.problems[0]


def test_a_file_that_is_not_text_is_reported(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_bytes(b"\xff\xfe\x00binary")

    found = instructions(tmp_path)

    assert not found.sources
    assert "not valid UTF-8" in found.problems[0]


def test_a_directory_named_like_an_instruction_file_is_ignored(tmp_path: Path) -> None:
    """`is_file()` rather than `exists()`. Somebody with a `CLAUDE.md/` directory is unusual and
    should not crash the launch."""
    (tmp_path / "CLAUDE.md").mkdir()

    found = instructions(tmp_path)

    assert not found
    assert not found.problems


def test_the_paths_are_reportable(tmp_path: Path) -> None:
    """For a status line, or for `check` to list what it found."""
    (tmp_path / "CLAUDE.md").write_text("something")

    assert [p.name for p in paths_of(instructions(tmp_path))] == ["CLAUDE.md"]
