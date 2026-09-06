"""Reading and changing files in the working tree.

Two things are being checked. **Containment**, which is the guard everything goes through — a path
arrives from a model, so most of the refusals here are about paths that try to leave. And
**refusals a model can act on**: each one says what was wrong and what would be right, because one
it cannot act on is one it repeats.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hera_code.files import MAX_READ_BYTES, WorkingTree
from hera_code_workspace import OutsideWorkspace, Workspace


@pytest.fixture
def tree(tmp_path: Path) -> WorkingTree:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "api.py").write_text("def get():\n    return 1\n")
    (root / "src" / "app.py").write_text("from api import get\n")
    (root / "README.md").write_text("# repo\n")
    return WorkingTree(Workspace(root=root))


def _root(tree: WorkingTree) -> Path:
    return tree._workspace.root


# -- reading ----------------------------------------------------------------------------------


async def test_read_numbers_the_lines(tree: WorkingTree) -> None:
    """A model quoting `api.py:2` has to be right about 2."""
    found = await tree.read("src/api.py")

    assert "     1  def get():" in found.text
    assert "     2      return 1" in found.text


async def test_read_numbers_from_the_offset(tree: WorkingTree) -> None:
    """The subtle one: numbering a window from 1 would make every line number after an offset a
    lie, and a model would then edit the wrong place."""
    found = await tree.read("src/api.py", offset=1)

    assert "     2      return 1" in found.text
    assert "     1  " not in found.text


async def test_read_says_when_there_is_more(tree: WorkingTree) -> None:
    """Truncation is said out loud. A model reasoning about a file it has only half of is the
    expensive kind of wrong."""
    (_root(tree) / "long.py").write_text("\n".join(f"line {i}" for i in range(100)))

    found = await tree.read("long.py", limit=10)

    assert found.truncated
    assert found.lines == 10


async def test_read_is_not_truncated_when_it_is_whole(tree: WorkingTree) -> None:
    assert not (await tree.read("src/api.py")).truncated


async def test_read_reports_the_relative_path(tree: WorkingTree) -> None:
    """What a person reads, and what the model should quote back."""
    assert (await tree.read("src/api.py")).path == "src/api.py"


async def test_reading_a_missing_file_says_so(tree: WorkingTree) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        await tree.read("src/nope.py")


async def test_reading_a_directory_suggests_glob(tree: WorkingTree) -> None:
    with pytest.raises(IsADirectoryError, match="glob"):
        await tree.read("src")


async def test_reading_a_binary_file_says_so(tree: WorkingTree) -> None:
    (_root(tree) / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00binary")

    with pytest.raises(ValueError, match="not a text file"):
        await tree.read("image.png")


async def test_an_enormous_file_suggests_grep(tree: WorkingTree) -> None:
    """The refusal names the tool that would work, rather than only refusing."""
    (_root(tree) / "huge.txt").write_bytes(b"x" * (MAX_READ_BYTES + 1))

    with pytest.raises(ValueError, match="grep"):
        await tree.read("huge.txt")


# -- writing ----------------------------------------------------------------------------------


async def test_write_creates_parents(tree: WorkingTree) -> None:
    size = await tree.write("a/b/c.py", "x = 1\n")

    assert (_root(tree) / "a" / "b" / "c.py").read_text() == "x = 1\n"
    assert size == 6


async def test_write_replaces_what_was_there(tree: WorkingTree) -> None:
    await tree.write("src/api.py", "new\n")
    assert (_root(tree) / "src" / "api.py").read_text() == "new\n"


# -- editing ----------------------------------------------------------------------------------


async def test_edit_replaces_one_passage(tree: WorkingTree) -> None:
    await tree.edit("src/api.py", "return 1", "return 2")

    assert "return 2" in (_root(tree) / "src" / "api.py").read_text()


async def test_edit_can_delete(tree: WorkingTree) -> None:
    await tree.edit("src/app.py", "from api import get\n", "")
    assert (_root(tree) / "src" / "app.py").read_text() == ""


async def test_edit_that_matches_nothing_says_to_copy_it_exactly(tree: WorkingTree) -> None:
    with pytest.raises(ValueError, match="does not appear"):
        await tree.edit("src/api.py", "return 99", "return 2")


async def test_edit_that_matches_twice_refuses_and_says_how_many(tree: WorkingTree) -> None:
    """**The count is the actionable part.**

    A replacement that hit the wrong one of three is a silent corruption and the model cannot see
    the file to notice — so it must not happen. But *be more specific* without a number is advice;
    with one, the model knows how much more context to include.
    """
    (_root(tree) / "twice.py").write_text("x = 1\ny = 1\n")

    with pytest.raises(ValueError, match="appears 2 times"):
        await tree.edit("twice.py", "= 1", "= 2")

    assert (_root(tree) / "twice.py").read_text() == "x = 1\ny = 1\n", "nothing may change"


async def test_edit_with_an_empty_find_points_at_write(tree: WorkingTree) -> None:
    with pytest.raises(ValueError, match="`write`"):
        await tree.edit("src/api.py", "", "anything")


async def test_editing_a_missing_file_says_so(tree: WorkingTree) -> None:
    with pytest.raises(FileNotFoundError):
        await tree.edit("nope.py", "a", "b")


# -- finding ----------------------------------------------------------------------------------


async def test_glob_matches(tree: WorkingTree) -> None:
    found = await tree.glob("src/*.py")
    assert set(found) == {"src/api.py", "src/app.py"}


async def test_glob_returns_the_newest_first(tree: WorkingTree) -> None:
    """The question behind a glob is almost always *what is being worked on*."""
    import os
    import time

    now = time.time()
    os.utime(_root(tree) / "src" / "api.py", (now - 500, now - 500))
    os.utime(_root(tree) / "src" / "app.py", (now, now))

    assert (await tree.glob("src/*.py"))[0] == "src/app.py"


async def test_glob_that_matches_nothing_returns_nothing(tree: WorkingTree) -> None:
    assert list(await tree.glob("*.rs")) == []


async def test_grep_finds_lines_with_their_numbers(tree: WorkingTree) -> None:
    found = await tree.grep(r"return")

    assert len(found) == 1
    assert found[0].path == "src/api.py"
    assert found[0].line == 2
    assert found[0].text == "return 1"


async def test_grep_can_be_narrowed_by_glob(tree: WorkingTree) -> None:
    found = await tree.grep("get", glob="*app.py")
    assert {match.path for match in found} == {"src/app.py"}


async def test_grep_stops_at_the_limit(tree: WorkingTree) -> None:
    (_root(tree) / "many.py").write_text("\n".join("match" for _ in range(50)))
    assert len(await tree.grep("match", limit=5)) == 5


async def test_grep_gives_the_regex_engines_own_complaint(tree: WorkingTree) -> None:
    """The model wrote the pattern and can fix it."""
    with pytest.raises(ValueError, match="not a valid regular expression"):
        await tree.grep("(unclosed")


async def test_grep_skips_binary_files(tree: WorkingTree) -> None:
    (_root(tree) / "blob.bin").write_bytes(b"\x00match\x00")
    assert not [m for m in await tree.grep("match") if m.path == "blob.bin"]


# -- the guard --------------------------------------------------------------------------------


@pytest.mark.parametrize("escape", ["../outside.py", "/etc/passwd", "src/../../x.py"])
async def test_every_tool_refuses_a_path_outside_the_tree(tree: WorkingTree, escape: str) -> None:
    """**One guard, and everything goes through it.**

    `OutsideWorkspace` stays its own type all the way up rather than being flattened into a
    `ValueError`: ADR 11 makes it the refusal that is *not* a decision for a person, so the layer
    above has to be able to tell it apart.
    """
    with pytest.raises(OutsideWorkspace):
        await tree.read(escape)
    with pytest.raises(OutsideWorkspace):
        await tree.write(escape, "x")
    with pytest.raises(OutsideWorkspace):
        await tree.edit(escape, "a", "b")


async def test_write_cannot_escape_through_a_symlink(tree: WorkingTree, tmp_path: Path) -> None:
    """The path is inside the tree by every textual measure and the write would land outside."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (_root(tree) / "out").symlink_to(elsewhere)

    with pytest.raises(OutsideWorkspace):
        await tree.write("out/stolen.txt", "x")

    assert not (elsewhere / "stolen.txt").exists()


async def test_the_ignored_directories_are_not_searched(tree: WorkingTree) -> None:
    """A `grep` that read `node_modules` would replace the answer with a haystack."""
    noise = _root(tree) / "node_modules" / "pkg"
    noise.mkdir(parents=True)
    (noise / "index.js").write_text("return 1")

    found = await tree.grep("return")

    assert all("node_modules" not in match.path for match in found)
