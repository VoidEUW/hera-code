"""The command line: what each verb does, and what it says when it cannot.

**Nothing here prints a traceback at a person.** A configuration problem, a data directory from a
newer build and a missing endpoint are all things somebody has to *do* something about, and a
stack trace buries the one line that says what. Several tests below assert exactly that.
"""

from __future__ import annotations

import pytest

from hera_code import __version__
from hera_code.cli import FAILED, main


def test_version_is_read_from_packaging(capsys: pytest.CaptureFixture[str]) -> None:
    """Declared in pyproject.toml and read back, so a release tag cannot disagree with it."""
    with pytest.raises(SystemExit) as exit_:
        main(["--version"])
    assert exit_.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_init_prepares_the_directories(capsys: pytest.CaptureFixture[str]) -> None:
    from hera_code_home import code_config_path, sessions_db_path
    from hera_home import mcp_path, mind_dir

    assert main(["init"]) == 0

    assert mind_dir().is_dir()
    assert mcp_path().is_file()
    assert code_config_path().is_file()
    assert sessions_db_path().is_file()
    assert "created" in capsys.readouterr().out


def test_init_says_what_it_created(capsys: pytest.CaptureFixture[str]) -> None:
    """*created ~/.hera/mind* is a useful sentence; *created 4 things* is not."""
    main(["init"])
    out = capsys.readouterr().out
    assert "mind" in out
    assert "mcp.json" in out


def test_init_mentions_the_gitignore_decision_once(capsys: pytest.CaptureFixture[str]) -> None:
    """Whether `<root>/.hera` is committed is the person's call, said once and never again —
    and hera-code never edits a .gitignore (ADR 7)."""
    main(["init"])
    assert ".gitignore" in capsys.readouterr().out


def test_a_second_init_says_there_was_nothing_to_do(capsys: pytest.CaptureFixture[str]) -> None:
    """The sentence that tells somebody their install is already fine."""
    main(["init"])
    capsys.readouterr()

    assert main(["init"]) == 0
    assert "already in place" in capsys.readouterr().out


def test_check_on_a_fresh_install_is_usable(capsys: pytest.CaptureFixture[str]) -> None:
    main(["init"])
    capsys.readouterr()

    assert main(["check"]) == 0
    assert "ok" in capsys.readouterr().out


def test_check_on_nothing_says_what_to_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check"]) == FAILED
    assert "hera-code init" in capsys.readouterr().out


def test_a_broken_config_is_one_line_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`_Reportable` exists for this. A person who hand-edited the file needs the complaint."""
    from hera_code_home import code_config_path

    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text("[[providers]\nbroken")

    assert main(["init"]) == FAILED

    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert str(code_config_path()) in err


def test_the_terminal_refuses_a_pipe_and_says_what_to_use(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """pytest's stdout is not a terminal, which is the case this guard is for.

    A dock drawn into a pipe is the failure ADR 3 says this design is most exposed to, and there
    is a better answer than a corrupted transcript: name the flag that works.
    """
    assert main([]) == 2
    err = capsys.readouterr().err
    assert "needs a terminal" in err
    assert "-p" in err


@pytest.mark.parametrize(
    "argv",
    [
        ["-p", "hello"],
        ["--print", "hello"],
        ["--continue"],
        ["--resume", "abc"],
        ["run", "-p", "hello"],
        ["run", "--continue"],
    ],
)
def test_runs_options_parse_with_and_without_the_verb(argv: list[str]) -> None:
    """`run` is the default, so its options have to work without it being typed.

    A default that only works when you type the thing it is a default for is not a default — and
    `hera-code -p "…"` is the form README.md documents.
    """
    parser_accepted = True
    try:
        main(argv)
    except SystemExit as exit_:
        parser_accepted = exit_.code != 2
    assert parser_accepted, f"{argv} did not parse"


def test_an_unknown_verb_is_refused() -> None:
    with pytest.raises(SystemExit) as exit_:
        main(["dream"])
    assert exit_.value.code == 2


def test_library_logging_does_not_reach_a_person(capsys: pytest.CaptureFixture[str]) -> None:
    """**The gap the test suite had and manual use found.**

    Alembic logs a line per autogenerate plugin at INFO, so the first thing anybody saw on a
    fresh install was fourteen lines about `alembic.autogenerate.schemas` before
    `created ~/.hera/mind`. pytest captures logging by default, so no test noticed — this one
    asserts on the *streams*, which is where a person is actually looking.
    """
    main(["init"])

    captured = capsys.readouterr()
    for stream in (captured.out, captured.err):
        assert "autogenerate" not in stream
        assert "setup plugin" not in stream
        assert "SQLiteImpl" not in stream


def test_init_says_only_what_it_did(capsys: pytest.CaptureFixture[str]) -> None:
    """Every line on stdout should be one somebody wanted to read."""
    main(["init"])

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    assert lines
    assert all(line.startswith(("created", "migrated", "`<your repo>")) for line in lines), lines


def test_verbose_puts_the_logging_back(capsys: pytest.CaptureFixture[str]) -> None:
    """Quietened rather than disabled — somebody debugging a migration wants exactly those lines,
    and a flag they can find is better than an environment variable they cannot."""
    import logging

    main(["--verbose", "init"])

    assert logging.getLogger("alembic").level in {logging.NOTSET, logging.DEBUG}
