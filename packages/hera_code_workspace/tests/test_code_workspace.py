"""The working tree, and the one guard everything that touches a file goes through.

`Workspace.resolve` is the single place that decides a path is inside the tree. A path arrives
from a model, so most of this file is about the ways one could try to leave — and the symlink
cases are the ones a string comparison would wave through.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hera_code_workspace import (
    IGNORED_DIRECTORIES,
    OutsideWorkspace,
    Workspace,
    discover,
    git_root,
    matches_glob,
)


@pytest.fixture
def tree(tmp_path: Path) -> Workspace:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "api.py").write_text("x = 1\n")
    (root / "README.md").write_text("# repo\n")
    return Workspace(root=root)


# -- the guard --------------------------------------------------------------------------------


def test_a_path_inside_resolves(tree: Workspace) -> None:
    assert tree.resolve("src/api.py") == tree.root / "src" / "api.py"


def test_a_path_that_does_not_exist_yet_resolves(tree: Workspace) -> None:
    """`write` has to be able to create a file. A strict resolve would make that impossible."""
    assert tree.resolve("src/new.py").name == "new.py"


@pytest.mark.parametrize(
    "attempt",
    [
        "../outside.py",
        "../../etc/passwd",
        "src/../../escape.py",
        "/etc/passwd",
        "src/./../../out.py",
    ],
)
def test_leaving_the_tree_is_refused(tree: Workspace, attempt: str) -> None:
    with pytest.raises(OutsideWorkspace):
        tree.resolve(attempt)


def test_a_symlink_out_of_the_tree_is_refused(tree: Workspace, tmp_path: Path) -> None:
    """**The case a string comparison would wave through.**

    The path is inside the tree by every textual measure and points outside it. This is why
    `resolve` resolves before it compares, and why the cost of a `stat` per call is worth paying.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("shh")
    (tree.root / "link.txt").symlink_to(secret)

    with pytest.raises(OutsideWorkspace):
        tree.resolve("link.txt")


def test_a_symlink_inside_the_tree_is_allowed(tree: Workspace) -> None:
    """Resolving is not the same as refusing links. One that stays inside is a normal file."""
    (tree.root / "alias.py").symlink_to(tree.root / "src" / "api.py")
    assert tree.resolve("alias.py") == (tree.root / "src" / "api.py").resolve()


def test_a_symlinked_parent_is_followed(tree: Workspace, tmp_path: Path) -> None:
    """The subtler version: the *leaf* does not exist, so a strict resolve would not look — but
    the directory holding it is a link out of the tree, and a write would land outside."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tree.root / "out").symlink_to(elsewhere)

    with pytest.raises(OutsideWorkspace):
        tree.resolve("out/new.txt")


def test_the_root_itself_is_inside(tree: Workspace) -> None:
    assert tree.resolve(".") == tree.root.resolve()


def test_a_sibling_with_a_shared_prefix_is_outside(tmp_path: Path) -> None:
    """`/tmp/repo-backup` starts with `/tmp/repo`. A prefix comparison on strings would accept it;
    comparing against `parents` does not."""
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo-backup").mkdir()
    tree = Workspace(root=tmp_path / "repo")

    with pytest.raises(OutsideWorkspace):
        tree.resolve(tmp_path / "repo-backup" / "x.py")


def test_contains_answers_without_raising(tree: Workspace) -> None:
    assert tree.contains("src/api.py")
    assert not tree.contains("../elsewhere.py")


def test_relative_is_what_a_person_reads(tree: Workspace) -> None:
    assert tree.relative(tree.root / "src" / "api.py") == Path("src/api.py")


def test_the_refusal_says_where_the_tree_is(tree: Workspace) -> None:
    """A refusal a model cannot act on is one it repeats."""
    with pytest.raises(OutsideWorkspace, match="outside the working tree"):
        tree.resolve("../nope.py")


# -- walking ----------------------------------------------------------------------------------


def test_walk_finds_the_files(tree: Workspace) -> None:
    found = {path.relative_to(tree.root).as_posix() for path in tree.walk()}
    assert found == {"src/api.py", "README.md"}


def test_walk_prunes_the_uninteresting_directories(tree: Workspace) -> None:
    """Pruned during the walk, not filtered after — the difference between skipping
    `node_modules` and reading all of it before throwing it away."""
    (tree.root / "node_modules" / "pkg").mkdir(parents=True)
    (tree.root / "node_modules" / "pkg" / "index.js").write_text("//")
    (tree.root / ".git").mkdir()
    (tree.root / ".git" / "config").write_text("[core]")

    found = {path.relative_to(tree.root).as_posix() for path in tree.walk()}

    assert found == {"src/api.py", "README.md"}


def test_walk_honours_extra_patterns(tree: Workspace) -> None:
    (tree.root / "notes.log").write_text("noise")
    found = {path.relative_to(tree.root).as_posix() for path in tree.walk(ignored=["*.log"])}
    assert "notes.log" not in found


def test_walk_does_not_follow_a_symlinked_directory(tree: Workspace, tmp_path: Path) -> None:
    """A link into a directory that contains the tree is an infinite walk."""
    (tree.root / "loop").symlink_to(tree.root)
    found = list(tree.walk())
    assert len(found) == 2


def test_walk_skips_a_directory_it_cannot_read(tree: Workspace) -> None:
    """Permission denied somewhere in a tree is ordinary, and not a reason for the walk to fail."""
    closed = tree.root / "closed"
    closed.mkdir()
    (closed / "x.py").write_text("x")
    closed.chmod(0o000)
    try:
        found = {path.relative_to(tree.root).as_posix() for path in tree.walk()}
    finally:
        closed.chmod(0o755)
    assert found == {"src/api.py", "README.md"}


def test_the_ignore_list_covers_the_expensive_ones() -> None:
    assert {".git", "node_modules", ".venv", "__pycache__"} <= IGNORED_DIRECTORIES


# -- discovery --------------------------------------------------------------------------------


def test_a_directory_that_is_not_a_repository_is_still_a_working_tree(tmp_path: Path) -> None:
    """The fallback is the decision. Somebody running hera-code in a scratch folder means it."""
    workspace = discover(tmp_path)

    assert workspace.root == tmp_path.resolve()
    assert not workspace.is_repository
    assert workspace.branch == ""
    assert git_root(tmp_path) is None


def test_a_repository_is_found_from_a_subdirectory(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    deep = root / "src" / "deep"
    deep.mkdir(parents=True)

    workspace = discover(deep)

    assert workspace.root == root.resolve()
    assert workspace.is_repository
    assert workspace.branch


def test_the_dirty_count_reflects_the_tree(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    assert discover(root).dirty == 0

    (root / "new.txt").write_text("x")

    assert discover(root).dirty == 1


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    run = ["git", "-c", "init.defaultBranch=main", "init", "--quiet"]
    subprocess.run(run, cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)
    (root / "README.md").write_text("# repo\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=root, check=True, capture_output=True)
    return root


def test_a_repository_with_no_commits_still_reports_its_branch(tmp_path: Path) -> None:
    """**The first day of a project**, which is the case somebody is most likely to be in.

    `git init` puts you on a branch with no commits on it, and `rev-parse HEAD` fails there — so
    reading the branch that way reported nothing at all for a perfectly ordinary repository.
    """
    root = tmp_path / "fresh"
    root.mkdir()
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "--quiet"],
        cwd=root,
        check=True,
        capture_output=True,
    )

    workspace = discover(root)

    assert workspace.is_repository
    assert workspace.branch == "main"


def test_a_detached_head_shows_the_commit(tmp_path: Path) -> None:
    """*What am I on* has an answer there, and `HEAD` is not it."""
    root = _repository(tmp_path)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "checkout", "--quiet", commit], cwd=root, check=True, capture_output=True
    )

    assert discover(root).branch == commit


# -- what a glob means ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("api.py", "*.py", True),
        ("src/api.py", "*.py", True),
        ("src/deep/api.py", "*.py", True),
        ("src/api.py", "src/*.py", True),
        ("src/deep/api.py", "src/*.py", False),
        ("src/deep/api.py", "src/**/*.py", True),
        ("src/app.py", "*app.py", True),
        ("src/api.py", "*app.py", False),
        ("README.md", "*.py", False),
        ("test_api.py", "test_*.py", True),
        ("src/test_api.py", "test_*.py", True),
    ],
)
def test_what_a_glob_means(path: str, pattern: str, expected: bool) -> None:
    """**One definition, pinned, because it silently had two.**

    `Path.match` and `Path.full_match` disagree — the first matches a basename anywhere in the
    tree, the second requires the whole path and will not let `*` cross a `/` — and `full_match`
    only exists from 3.13. A build that used one with the other as a fallback changed what a glob
    meant depending on the interpreter. It did, and CI caught it on 3.13 after it passed on 3.12.

    So the behaviour is written down here rather than inherited from whichever `pathlib` is
    installed.
    """
    assert matches_glob(path, pattern) is expected


def test_a_glob_matches_the_basename_anywhere() -> None:
    """`*.py` finds `src/deep/api.py`, which is what somebody typing it means.

    The strict reading would need `**/*.py`, and a tool that made you spell that out would be
    right and unhelpful.
    """
    assert matches_glob("src/deep/api.py", "*.py")
