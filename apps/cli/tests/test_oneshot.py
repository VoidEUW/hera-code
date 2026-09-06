"""One turn, end to end, against a scripted provider.

**M1's deliverable, and the reason it comes before the terminal**: this is the whole loop with
none of the rendering, so a bug found once the terminal exists has an unambiguous answer to *is
this the loop or the drawing*.

Every test here drives `hera_providers.FakeProvider`, so nothing reaches a network. What it
exercises is real: the config, the prompt slot, `hera_chats.TurnOrchestrator`, the permission
suspension, and the persistence.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from code_support import Scripted

from hera_chats import ChatRepository, MessageRepository, ToolResultEvent
from hera_code import oneshot
from hera_code.oneshot import COMPLETED, FAILED, SUSPENDED
from hera_code.wiring import Services
from hera_providers import TextDelta, text_turn, thinking_turn, tool_call, tool_turn


async def test_a_plain_turn_prints_the_answer(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    provider.script(text_turn("Two files changed: `limit.py` and `app.py`."))

    code = await oneshot.run(prepared, "what did you change?")

    assert code == COMPLETED
    assert "Two files changed" in capsys.readouterr().out


async def test_thinking_is_not_printed(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    """It is not the answer, and a pipe wants the answer."""
    provider.script(thinking_turn("Let me check the middleware first.", "Done."))

    await oneshot.run(prepared, "go")

    out = capsys.readouterr().out
    assert "Done." in out
    assert "middleware" not in out


async def test_nothing_writes_an_escape_code(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The failure mode ADR 3 says this design is most exposed to.**

    `-p` output is usually a pipe. A dock that leaked escape codes into one would be invisible in
    a terminal and corrupt in a file, which is the worst possible pairing.
    """
    provider.script(text_turn("plain text only"))

    await oneshot.run(prepared, "go")

    captured = capsys.readouterr()
    assert "\x1b" not in captured.out
    assert "\x1b" not in captured.err


async def test_the_turn_is_persisted(
    prepared: Services, provider: Scripted, owner_id: UUID
) -> None:
    provider.script(text_turn("stored"))

    await oneshot.run(prepared, "remember this")

    with prepared.database.session() as session:
        chats = ChatRepository(session).for_owner(owner_id)
        assert len(chats) == 1
        messages = MessageRepository(session).for_chat(chats[0].id)
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].content == "remember this"
        assert messages[1].content == "stored"


async def test_a_failed_turn_still_persists_what_arrived(
    prepared: Services, provider: Scripted, owner_id: UUID
) -> None:
    """`FakeProvider` with nothing scripted raises on the first request.

    The user message and an assistant row are written *before* the turn runs, so what a person
    typed is never lost to a failure — and `session.run` persists in a `finally`.
    """
    code = await oneshot.run(prepared, "this will fail")

    assert code == FAILED
    with prepared.database.session() as session:
        chats = ChatRepository(session).for_owner(owner_id)
        messages = MessageRepository(session).for_chat(chats[0].id)
        assert [m.role for m in messages] == ["user", "assistant"]


async def test_a_failure_says_what_happened_on_stderr(
    prepared: Services, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sentence, not a traceback."""
    code = await oneshot.run(prepared, "go")

    captured = capsys.readouterr()
    assert code == FAILED
    assert captured.err.strip()
    assert "Traceback" not in captured.err


async def test_the_session_title_comes_from_the_first_message(
    prepared: Services, provider: Scripted, owner_id: UUID
) -> None:
    provider.script(text_turn("ok"))

    await oneshot.run(prepared, "add rate limiting to the api")

    with prepared.database.session() as session:
        chat = ChatRepository(session).for_owner(owner_id)[0]
        assert "rate limiting" in chat.title


async def test_the_working_tree_reaches_the_prompt(
    prepared: Services, provider: Scripted, tmp_path: Path
) -> None:
    """`SLOT_PROJECT` is the seam that keeps every vendored package unedited (ADR 5).

    If the working tree stops arriving in the prompt, that seam has broken — so this asserts on
    the request the provider actually received rather than on the composition in isolation.
    """
    provider.script(text_turn("ok"))

    await oneshot.run(prepared, "go", root=tmp_path)

    sent = provider.requests[-1]
    system = "\n".join(str(message.content) for message in sent.messages)
    assert str(tmp_path) in system
    assert "The deliverable is a change to the working tree" in system


async def test_the_model_name_from_the_config_is_what_is_sent(
    prepared: Services, provider: Scripted
) -> None:
    provider.script(text_turn("ok"))

    await oneshot.run(prepared, "go")

    assert provider.requests[-1].model == "test-model"


async def test_a_suspended_turn_is_not_an_allow(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The one failure a person could not detect from the output.**

    There is nobody here to answer a permission card, so the turn stops and says so. Running the
    call anyway would be indistinguishable from a turn that was allowed to.
    """
    provider.script(tool_turn(tool_call("shell__rm", {"path": "/"})))

    code = await oneshot.run(prepared, "delete everything")

    assert code == SUSPENDED
    err = capsys.readouterr().err
    assert "waiting for a person" in err


async def test_a_suspended_turn_names_the_call_that_is_waiting(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    provider.script(tool_turn(tool_call("shell__git", {"args": "push"})))

    await oneshot.run(prepared, "push it")

    assert "shell__git" in capsys.readouterr().err


async def test_a_second_turn_carries_the_history(
    prepared: Services, provider: Scripted, owner_id: UUID
) -> None:
    """A resumed session has to reproduce the conversation, which is what `build_history` does."""
    provider.script(text_turn("The first answer."))
    await oneshot.run(prepared, "first question")

    with prepared.database.session() as session:
        # The id, not the row: a `Chat` fetched inside this block is detached the moment it
        # closes, and touching an attribute afterwards raises rather than reloading.
        chat_id = ChatRepository(session).for_owner(owner_id)[0].id

    provider.script(text_turn("The second answer."))
    await _run_in(prepared, chat_id, "second question")

    sent = "\n".join(str(m.content) for m in provider.requests[-1].messages)
    assert "first question" in sent
    assert "The first answer." in sent


async def _run_in(services: Services, chat_id: UUID, prompt: str) -> int:
    """A turn in an existing session. `--resume` is M5; this is what it will call."""
    from hera_code import session as sessions

    with services.database.session() as db:
        found = sessions.open_session(db, services, chat_id=chat_id)
        exchange = sessions.begin(db, services, found, prompt)
        async for _ in sessions.run(db, exchange):
            pass
    return COMPLETED


def test_the_exit_codes_are_distinguishable() -> None:
    """A script should be able to tell *the model asked for permission* from *the endpoint is
    down*. The first is answerable by re-running in the terminal; the second is not."""
    assert len({COMPLETED, FAILED, SUSPENDED}) == 3


def test_tool_result_is_importable() -> None:
    """A guard on the vendored union: `-p` renders nothing for a tool result today, and M2 will.

    Here so that a change to `hera_chats.ChatEvent` that removed the variant fails in this suite
    rather than in the terminal three milestones later.
    """
    assert ToolResultEvent(call_id="1", tool="x").type == "tool_result"
    assert TextDelta(text="x").type == "text_delta"


async def test_a_spent_tool_budget_still_answers(
    prepared: Services, provider: Scripted, capsys: pytest.CaptureFixture[str]
) -> None:
    """`max_iterations` is not a failure — she answers with what she has.

    `hera_chats` withholds the tools on a final round rather than simply stopping, because an
    empty tool list is the only thing that reliably ends a loop: telling a model in prose to stop
    is advice, and this is arithmetic. What a person gets is an answer, so the exit code says
    completed and stderr says why it was short.
    """
    prepared.orchestrator.settings = prepared.orchestrator.settings.model_copy(
        update={"max_iterations": 1}
    )
    # An allowed tool, so it dispatches rather than suspending. There are no servers, so the
    # result is `unknown_tool` -- which is the system behaving correctly and keeps the loop going.
    provider.script(tool_turn(tool_call("code__read", {"path": "a.py"})))
    provider.script(text_turn("I could not read it, so here is what I know."))

    code = await oneshot.run(prepared, "read a.py")

    captured = capsys.readouterr()
    assert code == COMPLETED
    assert "here is what I know" in captured.out
    assert "answered with what it had" in captured.err


def test_a_cancelled_turn_is_a_failure_that_says_so() -> None:
    """`^C` is the ordinary way a turn ends early once the terminal exists, and the work so far is
    already persisted — but from a script's side nothing completed, so the code is not success."""
    from hera_chats import TurnClosed

    assert oneshot._code(TurnClosed(reason="cancelled"), []) == FAILED


def test_a_stream_that_never_closed_is_a_failure() -> None:
    """`hera_chats` closes the turn on every path, so this cannot happen — which is exactly why it
    is treated as a failure rather than a success. An absent terminator means something went wrong
    in a way nothing else reported."""
    assert oneshot._code(None, []) == FAILED
