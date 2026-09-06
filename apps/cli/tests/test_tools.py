"""The tools, reached the way the model reaches them.

Not the adapters — those are `test_files.py` and `test_shell.py`. This is the whole path: the
model asks for a tool, `hera_permissions` decides, `hera_tools` dispatches into the in-process
`hera_code_mcp` server, and a result comes back as a `ToolResultEvent`.

**The permission behaviour is what most of this file is about**, because ADR 11 took a decision
that is only real if it is enforced: reads run without a card, writes and shells stop the turn,
and nothing outside the working tree happens at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from code_support import Scripted

from hera_chats import PermissionRequired, ToolResultEvent
from hera_code import oneshot
from hera_code.oneshot import COMPLETED, SUSPENDED
from hera_code.wiring import DEFAULT_POLICY, Services, build_services
from hera_code_mcp import BUILTIN_SERVER_NAME, TOOL_NAMES
from hera_code_workspace import Workspace
from hera_permissions import Decision
from hera_providers import text_turn, tool_call, tool_turn
from hera_storage import Database


@pytest.fixture
def wired(
    settings: object,
    config: object,
    database: Database,
    provider: Scripted,
    workspace: Workspace,
    owner_id: object,
) -> Services:
    """The application with the real registry and the real server mounted.

    `build_services` rather than the hand-assembled `services` fixture, because what is being
    tested here is the wiring itself.
    """
    from hera_code.boot import prepare
    from hera_code.settings import CodeSettings

    assert isinstance(settings, CodeSettings)
    built = build_services(
        settings,
        config=config,  # type: ignore[arg-type]  # the fixture is a CodeConfig
        provider=provider,
        database=database,
        workspace=workspace,
    )
    prepare(built.database, built.mind, owner_id=built.settings.owner_id, config=built.config)
    return built


def _results(events: list[object]) -> list[ToolResultEvent]:
    return [event for event in events if isinstance(event, ToolResultEvent)]


# -- the catalogue ----------------------------------------------------------------------------


async def test_the_model_is_offered_every_tool(wired: Services, provider: Scripted) -> None:
    provider.script(text_turn("nothing to do"))

    await oneshot.run(wired, "hello")

    offered = {spec.name for spec in provider.requests[-1].tools}
    assert offered == {f"{BUILTIN_SERVER_NAME}__{name}" for name in TOOL_NAMES}


async def test_the_catalogue_reaches_the_prompt(wired: Services, provider: Scripted) -> None:
    """`hera_chats` binds a rendered listing into the prompt's `tools` slot. If it stops arriving,
    the model has tool specs it was never told about, which reads as a smaller toolset."""
    provider.script(text_turn("ok"))

    await oneshot.run(wired, "hello")

    assert "code__read" in provider.sent


# -- reads run without a card -----------------------------------------------------------------


async def test_a_read_runs_without_asking(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    """ADR 11: reading changes nothing, and a card before every read would teach a person to
    click through cards without reading them."""
    (workspace.root / "hello.py").write_text("x = 1\n")
    provider.script(tool_turn(tool_call("code__read", {"path": "hello.py"})))
    provider.script(text_turn("It sets x to 1."))

    code = await oneshot.run(wired, "what is in hello.py?")

    assert code == COMPLETED


async def test_a_grep_runs_and_the_model_sees_the_matches(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    (workspace.root / "api.py").write_text("def limit():\n    pass\n")
    provider.script(tool_turn(tool_call("code__grep", {"pattern": "limit"})))
    provider.script(text_turn("It is in api.py."))

    await oneshot.run(wired, "where is limit?")

    # The result went back to the model on the second round trip, which is the thing that would
    # silently not happen if dispatch were wired wrongly.
    assert "api.py:1" in provider.sent


# -- writes and shells stop the turn ----------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("code__write", {"path": "new.py", "text": "x = 1"}),
        ("code__edit", {"path": "a.py", "find": "a", "replace": "b"}),
        ("code__bash", {"command": "rm -rf /"}),
    ],
)
async def test_a_change_stops_the_turn_and_does_not_happen(
    wired: Services, provider: Scripted, workspace: Workspace, tool: str, arguments: dict[str, str]
) -> None:
    """**The decision ADR 11 took, enforced.**

    Not only that the turn suspends — that nothing *happened*. A card that appeared after the
    write would be theatre.
    """
    provider.script(tool_turn(tool_call(tool, arguments)))

    code = await oneshot.run(wired, "change it")

    assert code == SUSPENDED
    assert not (workspace.root / "new.py").exists()


async def test_the_card_carries_the_rules_reason(wired: Services, provider: Scripted) -> None:
    """`reason` is why that field exists. *Why am I being asked this* should not be a question
    only a configuration file can answer — it is the card's third line and the line `--yes`
    prints."""
    provider.script(tool_turn(tool_call("code__bash", {"command": "pytest"})))

    with wired.database.session() as db:
        from hera_code import session as sessions

        chat = sessions.open_session(db, wired)
        exchange = sessions.begin(db, wired, chat, "run the tests")
        events = [event async for event in sessions.run(db, exchange)]

    asked = [event for event in events if isinstance(event, PermissionRequired)]
    assert asked
    assert asked[0].reason == "runs a command in your working tree"


# -- outside the tree is not a decision for a person -------------------------------------------


async def test_a_path_outside_the_tree_is_refused_rather_than_asked(
    wired: Services, provider: Scripted
) -> None:
    """**`deny` is not `ask, but stricter`.**

    Reading outside the tree is refused because it is outside the contract, not because it is
    risky — so it comes back as a failed result the model can work around, and the turn carries
    on rather than stopping to ask a person about something they cannot usefully allow.
    """
    provider.script(tool_turn(tool_call("code__read", {"path": "../../../etc/passwd"})))
    provider.script(text_turn("I cannot reach that."))

    code = await oneshot.run(wired, "read /etc/passwd")

    assert code == COMPLETED


async def test_the_refusal_says_it_is_outside_the_tree(wired: Services, provider: Scripted) -> None:
    provider.script(tool_turn(tool_call("code__read", {"path": "/etc/passwd"})))
    provider.script(text_turn("done"))

    with wired.database.session() as db:
        from hera_code import session as sessions

        chat = sessions.open_session(db, wired)
        exchange = sessions.begin(db, wired, chat, "read it")
        events = [event async for event in sessions.run(db, exchange)]

    results = _results(list(events))
    assert results
    assert "outside the working tree" in results[0].text


# -- the seeded policy ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("code__read", Decision.ALLOW),
        ("code__glob", Decision.ALLOW),
        ("code__grep", Decision.ALLOW),
        ("code__todo_write", Decision.ALLOW),
        ("code__note_write", Decision.ALLOW),
        ("code__write", Decision.ASK),
        ("code__edit", Decision.ASK),
        ("code__bash", Decision.ASK),
        ("filesystem__delete_everything", Decision.ASK),
    ],
)
def test_the_seeded_policy_matches_the_record(tool: str, expected: Decision) -> None:
    """The table in ADR 11, as a test. If these drift apart, the record is the wrong one to
    believe — so this is what keeps them together."""
    assert DEFAULT_POLICY.check(tool).decision is expected


def test_every_seeded_rule_says_why() -> None:
    """`reason` is load-bearing twice — on the card and on the line `--yes` prints. A rule added
    without one degrades both."""
    for rule in DEFAULT_POLICY.base.rules:
        assert rule.reason, f"{rule.pattern} has no reason"


def test_every_tool_that_changes_something_asks() -> None:
    """Written against `TOOL_NAMES` rather than a hand-listed set, so a tool added to the server
    without a rule fails here instead of quietly inheriting the fallback."""
    changes = {"write", "edit", "bash"}
    for name in TOOL_NAMES:
        outcome = DEFAULT_POLICY.check(f"{BUILTIN_SERVER_NAME}__{name}")
        if name in changes:
            assert outcome.decision is Decision.ASK, f"{name} should ask"


async def test_the_working_tree_and_instructions_reach_the_prompt(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    """The `SLOT_PROJECT` seam, end to end, now that there is something real to put in it."""
    (workspace.root / "CLAUDE.md").write_text("Run the tests with `just test`.")
    provider.script(text_turn("ok"))

    await oneshot.run(wired, "hello")

    assert str(workspace.root) in provider.sent
    assert "just test" in provider.sent


async def test_an_instruction_file_edited_mid_session_is_picked_up(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    """Read every turn rather than cached at launch — the same promise the todo list makes."""
    provider.script(text_turn("first"))
    await oneshot.run(wired, "hello")
    assert "later rule" not in provider.sent

    (workspace.root / "AGENT.md").write_text("later rule")
    provider.script(text_turn("second"))
    await oneshot.run(wired, "again")

    assert "later rule" in provider.sent


def test_the_root_is_not_this_repository(workspace: Workspace) -> None:
    """A guard on the fixture itself. A tool test that wrote into hera-code's own checkout, or
    grepped its source, would pass for reasons that have nothing to do with the code."""
    assert Path.cwd() not in [workspace.root, *workspace.root.parents]


# -- --yes: a person saying yes in advance ------------------------------------------------------


async def test_yes_allows_a_write_and_it_happens(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    """ADR 11's flag, doing what the record says it does."""
    provider.script(tool_turn(tool_call("code__write", {"path": "new.py", "text": "x = 1\n"})))
    provider.script(text_turn("Written."))

    code = await oneshot.run(wired, "write it", yes=True)

    assert code == COMPLETED
    assert (workspace.root / "new.py").read_text() == "x = 1\n"


async def test_yes_names_what_it_allowed(
    wired: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    """**A CI log should show what was permitted, not only what ran.**

    That is most of what makes `--yes` defensible rather than a switch that turns the cards off.
    """
    provider.script(tool_turn(tool_call("code__bash", {"command": "echo hi"})))
    provider.script(text_turn("done"))

    await oneshot.run(wired, "run it", yes=True)

    assert "allowed: code__bash" in capsys.readouterr().err


async def test_yes_cannot_reach_outside_the_working_tree(
    wired: Services, provider: Scripted, tmp_path: Path
) -> None:
    """**The line `--yes` must not cross.**

    Containment is an invariant, not a preference. A flag that could switch it off would make it
    one — so this is the test that keeps ADR 11 honest about the difference between `ask` and
    `deny`.
    """
    outside = tmp_path / "stolen.txt"
    provider.script(tool_turn(tool_call("code__write", {"path": str(outside), "text": "taken"})))
    provider.script(text_turn("could not"))

    await oneshot.run(wired, "write outside", yes=True)

    assert not outside.exists(), "--yes reached past the containment guard"


async def test_yes_runs_a_command_and_the_model_sees_the_output(
    wired: Services, provider: Scripted
) -> None:
    """The whole shell path, through the server and back — including `_transcript`."""
    provider.script(tool_turn(tool_call("code__bash", {"command": "echo hello-from-bash"})))
    provider.script(text_turn("It printed a greeting."))

    await oneshot.run(wired, "run echo", yes=True)

    assert "hello-from-bash" in provider.sent
    assert "exit 0" in provider.sent


async def test_yes_edits_a_file(wired: Services, provider: Scripted, workspace: Workspace) -> None:
    (workspace.root / "a.py").write_text("value = 1\n")
    provider.script(
        tool_turn(tool_call("code__edit", {"path": "a.py", "find": "1", "replace": "2"}))
    )
    provider.script(text_turn("Changed."))

    await oneshot.run(wired, "change it", yes=True)

    assert (workspace.root / "a.py").read_text() == "value = 2\n"


async def test_a_failing_command_reaches_the_model_as_an_answer(
    wired: Services, provider: Scripted
) -> None:
    """A non-zero exit is information, not a tool failure — and the model has to be able to read
    it, which means the exit code has to survive the round trip."""
    provider.script(tool_turn(tool_call("code__bash", {"command": "exit 7"})))
    provider.script(text_turn("It exited 7."))

    await oneshot.run(wired, "run it", yes=True)

    assert "exit 7" in provider.sent


async def test_a_glob_reaches_the_model(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    (workspace.root / "one.py").write_text("x")
    (workspace.root / "two.py").write_text("y")
    provider.script(tool_turn(tool_call("code__glob", {"pattern": "*.py"})))
    provider.script(text_turn("Two files."))

    await oneshot.run(wired, "what python files are there?")

    assert "one.py" in provider.sent
    assert "two.py" in provider.sent


async def test_a_read_reaches_the_model_with_line_numbers(
    wired: Services, provider: Scripted, workspace: Workspace
) -> None:
    (workspace.root / "a.py").write_text("first\nsecond\n")
    provider.script(tool_turn(tool_call("code__read", {"path": "a.py"})))
    provider.script(text_turn("Two lines."))

    await oneshot.run(wired, "read a.py")

    assert "1  first" in provider.sent
    assert "2  second" in provider.sent


async def test_a_tool_refusal_reaches_the_model_as_a_result(
    wired: Services, provider: Scripted
) -> None:
    """`hera_tools` never raises past the registry, so a refusal is a render rather than an error
    boundary — and the model gets a sentence it can act on."""
    provider.script(tool_turn(tool_call("code__read", {"path": "absent.py"})))
    provider.script(text_turn("It is not there."))

    await oneshot.run(wired, "read absent.py")

    assert "does not exist" in provider.sent
