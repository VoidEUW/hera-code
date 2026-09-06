"""What the terminal prints, and — as often — what it prints only once.

Driving a pty is how the real bugs here were found, but it is a terrible place to *keep* the
knowledge: the evidence is a screenful of escape codes. So each thing that went wrong when a
person watched it is a test in here, asserting on the console's export.
"""

from __future__ import annotations

from collections.abc import Coroutine, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from code_support import Scripted
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from rich.console import Console

from hera_chats import ChatEvent, PermissionDecided, PermissionRequired, ToolResultEvent
from hera_code.tui.app import Terminal
from hera_code.tui.dock import Status, Todo
from hera_code.tui.theme import Theme
from hera_code.wiring import Services
from hera_code_workspace import Workspace
from hera_providers import (
    TextDelta,
    ToolCallReady,
    ToolCallStarted,
    text_turn,
    tool_call,
    tool_turn,
)

PLAIN = Theme(dark=True, colour=False, motion=False)


@pytest.fixture
def terminal(prepared: Services, workspace: Workspace) -> Terminal:
    """A terminal whose console records instead of writing to a screen."""
    term = Terminal(prepared, PLAIN, root=workspace.root)
    term.console = Console(record=True, width=100, no_color=True, force_terminal=False)
    return term


def _text(parts: StyleAndTextTuples) -> str:
    """The words out of a formatted-text fragment list.

    By index, because a fragment is `(style, text)` *or* `(style, text, handler)` — the same
    reason `app._plain` does it that way.
    """
    return "".join(fragment[1] for fragment in parts)


def shown(terminal: Terminal) -> str:
    """Everything printed so far.

    `clear=False`, because rich's default *drains* the record buffer — so a test that looked twice
    found nothing the second time, which is a confusing way to be told your assertion is fine.
    """
    return terminal.console.export_text(clear=False)


# -- the bugs a person found by looking -------------------------------------------------------


async def test_the_answer_is_printed_once(terminal: Terminal, provider: Scripted) -> None:
    """**It was printed twice.**

    hera replaces its optimistic view at `done`; in scrollback there is nothing above the cursor
    to replace, so re-rendering the turn at the end simply printed the answer again. Nothing but
    watching it catches that — the events were right and the render was right.
    """
    provider.script(text_turn("There is one getter."))

    await terminal._turn("what getters are there?")

    assert shown(terminal).count("There is one getter.") == 1


async def test_a_resumed_row_keeps_what_it_was_about(
    terminal: Terminal, provider: Scripted, prepared: Services
) -> None:
    """**The row came back emptier than it went.**

    A resumed turn does not re-stream the paused half, so what arrives is the `tool_result`
    without the `tool_call_ready` before it — and the gutter row lost the path it was about. The
    streamed view is seeded from `turn.context.resume` so it does not.

    Driven through `_drive` rather than `_turn`, because `_turn` would stop at the card and wait
    for a keyboard. What is being tested is the seeding, and that is one layer down.
    """
    from hera_code import session as sessions

    provider.script(tool_turn(tool_call("code__write", {"path": "notes.md", "text": "hi"})))
    provider.script(text_turn("Written."))

    with prepared.database.session() as db:
        chat = sessions.open_session(db, prepared)
        await terminal._drive(db, sessions.begin(db, prepared, chat, "add a note"))
        assert "notes.md" in shown(terminal), "the first pass should name the file"

        terminal.console = Console(record=True, width=100, no_color=True, force_terminal=False)
        assistant = sessions.latest_assistant(db, chat)
        assert assistant is not None
        resumed = sessions.resume(db, prepared, chat, assistant, denied=["call_code__write"])
        await terminal._drive(db, resumed)

    assert "notes.md" in shown(terminal), "the resumed row lost what it was about"
    assert "not allowed" in shown(terminal)


async def test_an_answered_card_is_not_drawn_again(terminal: Terminal, provider: Scripted) -> None:
    """**It asked twice.**

    `turn.recorded` includes the paused half, so the card that was already answered is in the list
    the resumed turn is rendered from. Drawing it again would ask a person something they have
    already decided.
    """
    events: list[ChatEvent] = [
        ToolCallReady(id="c1", name="code__write", arguments={"path": "a.py"}),
        PermissionRequired(call_id="c1", tool="code__write", reason="replaces a file"),
        PermissionDecided(call_id="c1", allowed=False),
        ToolResultEvent(call_id="c1", tool="code__write", ok=False, failure="denied"),
        TextDelta(text="I did not write it."),
    ]

    terminal._finish(events)

    assert "[ Allow once ]" not in shown(terminal)


async def test_a_card_that_is_still_waiting_is_drawn(terminal: Terminal) -> None:
    """The other half of the same rule — a card nobody has answered has to appear."""
    from hera_chats import TurnClosed

    events: list[ChatEvent] = [
        ToolCallReady(id="c1", name="code__bash", arguments={"command": "pytest"}),
        PermissionRequired(call_id="c1", tool="code__bash", reason="runs a command"),
        TurnClosed(reason="awaiting_permission"),
    ]

    terminal._finish(events)
    out = shown(terminal)

    assert "Run code__bash?" in out
    assert "runs a command" in out


# -- streaming --------------------------------------------------------------------------------


def test_the_gutter_is_flushed_before_the_first_word(terminal: Terminal) -> None:
    """Everything done before speaking stacks above what was said.

    A row is written three times as a call starts, becomes ready and answers, and a printed line
    cannot be rewritten — so the rows are held and flushed once, just before the prose.
    """
    for event in (
        ToolCallStarted(id="c1", name="code__grep"),
        ToolCallReady(id="c1", name="code__grep", arguments={"pattern": "def get"}),
        ToolResultEvent(call_id="c1", tool="code__grep", duration_ms=8),
        TextDelta(text="Found it."),
    ):
        terminal._stream(event)

    out = shown(terminal)
    assert out.index("grep") < out.index("Found it.")


def test_one_row_per_call_not_three(terminal: Terminal) -> None:
    for event in (
        ToolCallStarted(id="c1", name="code__read"),
        ToolCallReady(id="c1", name="code__read", arguments={"path": "a.py"}),
        ToolResultEvent(call_id="c1", tool="code__read", duration_ms=3),
        TextDelta(text="done"),
    ):
        terminal._stream(event)

    assert shown(terminal).count("read") == 1


async def test_thinking_never_reaches_the_transcript(
    terminal: Terminal, provider: Scripted
) -> None:
    """It is not the answer, and a person reading a diff does not want the deliberation."""
    from hera_providers import thinking_turn

    provider.script(thinking_turn("I should check the middleware first", "Checked."))

    await terminal._turn("go")

    out = shown(terminal)
    assert "middleware" not in out
    assert "Checked." in out
    assert "thought" in out, "it should still say that it thought"


# -- the header and the dock ------------------------------------------------------------------


def test_the_header_names_the_working_tree(terminal: Terminal, workspace: Workspace) -> None:
    # A wide console, because the assertion is about *what* the header says and a temporary
    # directory's path is long enough to wrap at any realistic width.
    terminal.console = Console(record=True, width=400, no_color=True, force_terminal=False)

    terminal.open()

    out = shown(terminal)
    assert "hera-code" in out
    assert str(workspace.root) in out


def test_the_header_carries_the_mark(terminal: Terminal) -> None:
    from hera_code.tui.ocellus import MARK

    terminal.open()

    assert MARK in shown(terminal)


def test_the_dock_says_there_is_no_plan_yet(terminal: Terminal) -> None:
    """Empty states are invitations. `docs/tui.md` § Voice."""
    from hera_code.tui.dock import todo_strip

    parts = todo_strip(terminal.status, PLAIN, 100)

    assert "no plan yet" in _text(parts)


def test_the_keys_change_while_a_turn_is_running(terminal: Terminal) -> None:
    """A hint that is always there is one nobody reads."""
    from hera_code.tui.dock import status_line

    idle = _text(status_line(terminal.status, PLAIN, 100))
    terminal.status.running = True
    busy = _text(status_line(terminal.status, PLAIN, 100))

    assert "^C stop" in busy
    assert "^C stop" not in idle
    assert "⏎ send" in idle


# -- built-in commands ------------------------------------------------------------------------


def test_help_lists_the_keys(terminal: Terminal) -> None:
    assert terminal._builtin("help") is False
    assert "⏎ send" in shown(terminal)


def test_quit_ends_the_session(terminal: Terminal) -> None:
    assert terminal._builtin("quit") is True


def test_clear_starts_a_new_session_and_keeps_the_old_one(terminal: Terminal) -> None:
    """**Nothing is deleted for you.** The old session is still there; `/clear` only stops adding
    to it."""
    terminal._chat_id = uuid4()

    terminal._builtin("clear")

    assert terminal._chat_id is None
    assert "new session" in shown(terminal)


def test_skills_lists_what_is_available(terminal: Terminal) -> None:
    terminal._builtin("skills")
    assert "no skills yet" in shown(terminal)


# -- what a person types ----------------------------------------------------------------------


def test_a_slash_that_is_not_a_builtin_goes_to_the_router() -> None:
    """**Skill selection is code.** `/tdd` is a person choosing, and it travels to
    `hera_skillsets` untouched rather than becoming an error about an unknown command."""
    from hera_code.tui.commands import is_command

    assert is_command("/quit") == "quit"
    assert is_command("/tdd") == ""
    assert is_command("not a command") == ""


def test_a_path_completes_from_the_working_tree(terminal: Terminal, workspace: Workspace) -> None:
    (workspace.root / "api.py").write_text("x")

    assert "api.py" in terminal._paths()


def test_completion_offers_paths_after_an_at_sign(terminal: Terminal, workspace: Workspace) -> None:

    (workspace.root / "api.py").write_text("x")
    completer = terminal._completer()

    offered = [c.text for c in completer.get_completions(Document("look at @api"), None)]

    assert "api.py" in offered


def test_completion_offers_commands_after_a_slash(terminal: Terminal) -> None:

    completer = terminal._completer()

    offered = [c.text for c in completer.get_completions(Document("/qu"), None)]

    assert "quit" in offered


def test_a_slash_mid_sentence_is_not_a_command(terminal: Terminal) -> None:
    """A `/` inside a sentence is a path separator, and offering a menu there would fire
    constantly while somebody types `src/api.py`."""

    completer = terminal._completer()

    offered = list(completer.get_completions(Document("look at src/api"), None))

    assert not [c for c in offered if c.text in {"quit", "help"}]


def _events(*events: ChatEvent) -> Sequence[ChatEvent]:
    return events


def test_the_terminal_refuses_a_pipe() -> None:
    """A dock drawn into a pipe is the failure ADR 3 says this design is most exposed to, and
    there is a better answer than a corrupted transcript: say what to use instead."""
    import sys

    from hera_code.cli import BAD_USAGE, _terminal

    class NotATty:
        def isatty(self) -> bool:
            return False

        def write(self, text: str) -> int:
            return len(text)

        def flush(self) -> None:
            return None

    original = sys.stdout
    sys.stdout = NotATty()
    try:
        assert _terminal() == BAD_USAGE
    finally:
        sys.stdout = original


def test_a_working_tree_path_is_relative(terminal: Terminal, workspace: Workspace) -> None:
    (workspace.root / "deep").mkdir()
    (workspace.root / "deep" / "x.py").write_text("x")

    assert "deep/x.py" in terminal._paths()
    assert str(workspace.root) not in " ".join(terminal._paths())


def test_the_path_list_skips_the_expensive_directories(
    terminal: Terminal, workspace: Workspace
) -> None:
    (workspace.root / "node_modules").mkdir()
    (workspace.root / "node_modules" / "x.js").write_text("x")

    assert not [p for p in terminal._paths() if "node_modules" in p]


def test_the_console_is_not_coloured_when_the_theme_says_so(prepared: Services) -> None:
    term = Terminal(prepared, PLAIN)
    assert term.console.no_color


def test_paths_are_offered_from_the_walk_not_a_raw_scan(terminal: Terminal) -> None:
    """One answer to *what files are there*. A completer that offered `node_modules/...` would be
    a second, and the two would disagree the moment a `.gitignore` changed."""
    assert isinstance(terminal._paths(), list)


def test_a_pending_turn_is_recognised() -> None:
    from hera_chats import TurnClosed
    from hera_code.tui.app import _pending

    waiting = _pending(
        [
            PermissionRequired(call_id="c", tool="code__bash"),
            TurnClosed(reason="awaiting_permission"),
        ]
    )
    finished = _pending([TurnClosed(reason="completed")])

    assert waiting
    assert not finished


def test_root_defaults_to_the_workspace(prepared: Services, workspace: Workspace) -> None:
    assert Terminal(prepared, PLAIN).root == workspace.root


def test_an_explicit_root_wins(prepared: Services, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()

    assert Terminal(prepared, PLAIN, root=other).root == other


# -- answering a card, through the real key bindings ------------------------------------------


async def _drive_keys[T](coroutine: Coroutine[Any, Any, T], keys: str) -> T:
    """Run one prompt Application with `keys` typed into it.

    prompt_toolkit's own test harness: a pipe for input and a dummy output, so the real key
    bindings run. Worth the setup — *Esc denies* is a safety claim, and asserting it against the
    actual binding is the only way to know it holds.
    """
    import asyncio

    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        with create_app_session(input=pipe, output=DummyOutput()):
            return await asyncio.wait_for(coroutine, timeout=5)


async def test_enter_allows_once() -> None:
    from hera_code.tui.prompt import ask_permission

    event = PermissionRequired(call_id="c", tool="code__write", reason="replaces a file")
    answer = await _drive_keys(ask_permission(event, PLAIN), "\r")

    assert answer.allowed
    assert not answer.remembered


async def test_escape_denies() -> None:
    """**The safe answer is the one a mistyped key reaches.**

    There is no key that allows something by accident, and this is the test that says so.
    """
    from hera_code.tui.prompt import ask_permission

    event = PermissionRequired(call_id="c", tool="code__bash")
    answer = await _drive_keys(ask_permission(event, PLAIN), "\x1b")

    assert not answer.allowed


async def test_arrowing_to_always_allow_remembers() -> None:
    """**Always allow must be visibly different from Allow once afterwards**, which starts with it
    being a different answer."""
    from hera_code.tui.prompt import ask_permission

    event = PermissionRequired(call_id="c", tool="code__write")
    answer = await _drive_keys(ask_permission(event, PLAIN), "\x1b[C\r")

    assert answer.allowed
    assert answer.remembered


async def test_d_denies_without_arrowing() -> None:
    from hera_code.tui.prompt import ask_permission

    event = PermissionRequired(call_id="c", tool="code__bash")
    answer = await _drive_keys(ask_permission(event, PLAIN), "d")

    assert not answer.allowed


async def test_a_question_takes_a_reply() -> None:
    from hera_chats import AnswerRequired
    from hera_code.tui.prompt import ask_question

    event = AnswerRequired(call_id="c", tool="code__ask", question="Redis?", kind="choice")
    reply = await _drive_keys(ask_question(event, PLAIN), "in-process\r")

    assert reply == "in-process"


async def test_walking_away_from_a_question_is_no_answer() -> None:
    """`hera_chats` already renders an empty reply to the model as *they replied with nothing;
    take it as no answer and carry on*, so `""` is a real answer rather than a missing one."""
    from hera_chats import AnswerRequired
    from hera_code.tui.prompt import ask_question

    event = AnswerRequired(call_id="c", tool="code__ask", question="Which?")
    reply = await _drive_keys(ask_question(event, PLAIN), "\x1b")

    assert reply == ""


def test_the_choices_render_with_the_selection_marked() -> None:
    from hera_code.tui.prompt import ALWAYS_ALLOW, _choices

    parts = _choices(ALWAYS_ALLOW, PLAIN, PermissionRequired(call_id="c", tool="code__write"))
    text = _text(parts)

    assert "▸ [ Always allow ]" in text
    assert "Esc denies" in text


# -- the dock -----------------------------------------------------------------------------------


def _status_with(*todos: tuple[str, str, str]) -> Status:
    return Status(todos=[Todo(id=i, text=t, state=s) for i, t, s in todos])


def test_the_strip_shows_progress_and_the_current_item() -> None:
    from hera_code.tui.dock import todo_strip

    status = _status_with(("a1", "read the middleware", "x"), ("a2", "add the bucket", ">"))
    text = _text(todo_strip(status, PLAIN, 100))

    assert "1/2" in text
    assert "add the bucket" in text


def test_blocked_items_are_counted_separately() -> None:
    """**An item nobody could decide is visibly different from an item nobody started**, and
    collapsing the two is how a stalled run looks like a slow one."""
    from hera_code.tui.dock import todo_strip

    status = _status_with(("a1", "done", "x"), ("a2", "stuck", "!"), ("a3", "next", " "))
    text = _text(todo_strip(status, PLAIN, 100))

    assert "1 blocked" in text


def test_the_strip_falls_back_to_the_next_unstarted_item() -> None:
    """A list where nothing is marked in progress is still a list somebody is working through."""
    from hera_code.tui.dock import todo_strip

    status = _status_with(("a1", "done", "x"), ("a2", "the next thing", " "))

    assert "the next thing" in _text(todo_strip(status, PLAIN, 100))


def test_a_long_item_is_shortened_rather_than_wrapping() -> None:
    from hera_code.tui.dock import todo_strip

    status = _status_with(("a1", "x" * 300, ">"))
    text = _text(todo_strip(status, PLAIN, 80))

    assert "…" in text
    assert len(text) < 200


def test_expanding_shows_every_item() -> None:
    from hera_code.tui.dock import todo_list

    status = _status_with(("a1", "first", "x"), ("a2", "second", ">"), ("a3", "third", "!"))
    text = _text(todo_list(status, PLAIN))

    assert "first" in text
    assert "second" in text
    assert "third" in text


def test_the_strip_offers_the_key_to_expand() -> None:
    from hera_code.tui.dock import todo_strip

    status = _status_with(("a1", "x", " "))

    assert "^T all" in _text(todo_strip(status, PLAIN, 100))
    status.expanded = True
    assert "^T less" in _text(todo_strip(status, PLAIN, 100))


def test_a_narrow_terminal_drops_the_branch_not_the_keys() -> None:
    """Nothing is removed, only the resting state is quieter."""
    from hera_code.tui.dock import Status, status_line

    status = Status(profile="coding", branch="main", dirty=3)

    wide = _text(status_line(status, PLAIN, 120))
    narrow = _text(status_line(status, PLAIN, 60))

    assert "main" in wide
    assert "main" not in narrow
    assert "⏎ send" in narrow
