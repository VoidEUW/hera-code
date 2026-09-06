"""Running a command in the working tree.

Three things, and each is a way this could quietly be wrong: it must not hang, it must not fill
the context window, and it must not lie about what happened.

The third is the one worth stating: **a non-zero exit is not an exception.** The tool worked and
the command said no, and those want different next moves from the model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hera_code.shell import MAX_OUTPUT_CHARS, WorkingShell
from hera_code_workspace import Workspace


@pytest.fixture
def shell(tmp_path: Path) -> WorkingShell:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "marker.txt").write_text("here\n")
    return WorkingShell(Workspace(root=root))


async def test_it_runs_in_the_working_tree(shell: WorkingShell) -> None:
    ran = await shell.run("cat marker.txt")

    assert ran.exit_code == 0
    assert "here" in ran.stdout


async def test_a_failing_command_is_an_answer_not_an_exception(shell: WorkingShell) -> None:
    """**The distinction the whole design of this tool rests on.**

    Raising would turn *the tests failed* into *the tool failed*, and the model would try to fix
    the wrong thing. `docs/tui.md` renders this muted rather than as a failure for the same reason.
    """
    ran = await shell.run("exit 3")

    assert ran.exit_code == 3
    assert not ran.timed_out


async def test_stderr_is_kept_separately(shell: WorkingShell) -> None:
    ran = await shell.run("echo out; echo err >&2")

    assert "out" in ran.stdout
    assert "err" in ran.stderr


async def test_a_command_that_hangs_is_killed(shell: WorkingShell) -> None:
    ran = await shell.run("sleep 30", timeout_s=0.5)

    assert ran.timed_out
    assert ran.exit_code != 0


async def test_output_written_before_a_timeout_survives(shell: WorkingShell) -> None:
    """A command that timed out after printing three failures has told you something.

    Throwing that away to report only *timed out* is the least useful thing to do with it.
    """
    ran = await shell.run("echo progress; sleep 30", timeout_s=0.8)

    assert ran.timed_out
    assert "progress" in ran.stdout


async def test_a_timeout_kills_the_whole_process_group(shell: WorkingShell, tmp_path: Path) -> None:
    """**The one that costs a held port if it is wrong.**

    Killing the shell alone leaves what it spawned running. The child here writes a file after the
    timeout has passed; if it survived, the file appears.
    """
    survivor = tmp_path / "survived.txt"
    child = f"import time; time.sleep(3); open({str(survivor)!r}, 'w').write('x')"
    script = f'{sys.executable} -c "{child}" &\nsleep 30'

    ran = await shell.run(script, timeout_s=0.5)

    assert ran.timed_out
    import asyncio

    await asyncio.sleep(4)
    assert not survivor.exists(), "a child outlived the timeout — the group was not killed"


async def test_enormous_output_is_cut_in_the_middle(shell: WorkingShell) -> None:
    """**The last lines of a failing test run are the ones that matter** — the summary, the
    assertion, the traceback's final frame. Cutting the tail is how a tool turns a useful failure
    into a useless one, so the middle goes and both ends stay.
    """
    ran = await shell.run(
        f"{sys.executable} -c \"print('HEAD'); print('x' * 60000); print('TAIL')\""
    )

    assert len(ran.stdout) <= MAX_OUTPUT_CHARS + 200
    assert "HEAD" in ran.stdout
    assert "TAIL" in ran.stdout
    assert "cut from the middle" in ran.stdout


async def test_short_output_is_untouched(shell: WorkingShell) -> None:
    ran = await shell.run("echo hello")
    assert ran.stdout == "hello\n"


async def test_it_reports_how_long_it_took(shell: WorkingShell) -> None:
    ran = await shell.run("true")
    assert ran.duration_ms >= 0


async def test_the_command_is_echoed_back(shell: WorkingShell) -> None:
    """The activity gutter renders it, so it has to survive the round trip."""
    ran = await shell.run("echo x")
    assert ran.command == "echo x"


async def test_a_command_that_cannot_run_is_still_an_answer(shell: WorkingShell) -> None:
    """A shell reports *command not found* as an exit code, not as a crash. Nothing here should
    turn that into one."""
    ran = await shell.run("this-command-does-not-exist-anywhere")

    assert ran.exit_code != 0
    assert ran.stderr.strip()


async def test_output_that_is_not_utf8_does_not_crash(shell: WorkingShell) -> None:
    """A test runner printing a byte sequence from somebody else's locale is ordinary."""
    ran = await shell.run(
        f"{sys.executable} -c \"import sys; sys.stdout.buffer.write(b'\\xff\\xfe')\""
    )

    assert ran.exit_code == 0
    assert ran.stdout
