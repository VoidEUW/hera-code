"""The command line: the verbs exist, and the ones that are not built say so."""

from __future__ import annotations

import pytest

from hera_code import __version__
from hera_code.cli import NOT_YET, main


def test_version_is_read_from_packaging(capsys: pytest.CaptureFixture[str]) -> None:
    """Declared in pyproject.toml and read back, so a tag cannot disagree with it."""
    with pytest.raises(SystemExit) as exit_:
        main(["--version"])
    assert exit_.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["run"], ["init"], ["check"]])
def test_a_planned_verb_says_what_it_is_waiting_on(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """A verb that exists and says 'not yet' is a promise; one that does not is a surprise."""
    assert main(argv) == NOT_YET
    assert "not built yet" in capsys.readouterr().err


def test_run_is_the_default_verb(capsys: pytest.CaptureFixture[str]) -> None:
    """Typing `hera-code` with no verb is what a person means every time but the first."""
    main([])
    assert "`run`" in capsys.readouterr().err


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
def test_runs_options_parse_with_and_without_the_verb(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """`run` is the default, so its options have to work without it being typed.

    A default that only works when you type the thing it is a default for is not a default —
    and `hera-code -p "…"` is the form README.md documents.
    """
    assert main(argv) == NOT_YET
    assert "not built yet" in capsys.readouterr().err


def test_an_unknown_verb_is_refused() -> None:
    with pytest.raises(SystemExit) as exit_:
        main(["dream"])
    assert exit_.value.code == 2
