"""The terminal, rendered into a recording console.

**This is what makes the rules checkable rather than asserted.** `docs/tui.md` says one renderer
per event variant, an unknown one degrades visibly, every colour says one of four sentences, and
nothing else uses a ringed glyph — and a design document with nothing holding it to the code is a
document.

Every test here renders through `rich.console.Console(record=True)` and asserts on the export,
which is what a person would actually see.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from rich.console import Console

from hera_chats import (
    AnswerGiven,
    AnswerRequired,
    ChatEvent,
    PermissionDecided,
    PermissionRequired,
    SkillSelected,
    ToolResultEvent,
    TurnClosed,
)
from hera_code.tui import MARK, RESERVED, Meaning, Theme, detect, frame, render_turn
from hera_code.tui.ocellus import BEAT, GUTTER
from hera_code.tui.theme import DARK, LIGHT, MEASURE
from hera_providers import TextDelta, ThinkingDelta, ToolCallReady, ToolCallStarted

DARK_THEME = Theme(dark=True, colour=True, motion=True)
PLAIN = Theme(dark=True, colour=False, motion=False)


def draw(events: Sequence[ChatEvent], theme: Theme = DARK_THEME, *, width: int = 100) -> str:
    """One turn, as a person would see it."""
    console = Console(
        record=True, width=width, force_terminal=theme.colour, no_color=not theme.colour
    )
    console.print(render_turn(events, theme, width=width))
    return console.export_text()


# -- one renderer per variant -----------------------------------------------------------------


EVERY_VARIANT: list[tuple[str, ChatEvent]] = [
    ("text_delta", TextDelta(text="Here is the answer.")),
    ("thinking_delta", ThinkingDelta(text="Let me look at the middleware first.")),
    ("tool_call_started", ToolCallStarted(id="c1", name="code__read")),
    ("tool_call_ready", ToolCallReady(id="c1", name="code__read", arguments={"path": "api.py"})),
    ("tool_result", ToolResultEvent(call_id="c1", tool="code__read", duration_ms=12)),
    ("skill_selected", SkillSelected(skill="fastapi", reason="pinned")),
    (
        "permission_required",
        PermissionRequired(call_id="c2", tool="code__bash", reason="runs a command"),
    ),
    ("permission_decided", PermissionDecided(call_id="c2", allowed=True)),
    (
        "answer_required",
        AnswerRequired(call_id="c3", tool="code__ask", question="Redis?", kind="choice"),
    ),
    ("answer_given", AnswerGiven(call_id="c3", text="Redis.")),
    ("turn_closed", TurnClosed(reason="completed")),
]


@pytest.mark.parametrize(("name", "event"), EVERY_VARIANT, ids=[n for n, _ in EVERY_VARIANT])
def test_every_variant_renders_without_raising(name: str, event: ChatEvent) -> None:
    """**One renderer per variant**, and none of them may explode on its own.

    Parametrised over the union rather than a hand-picked few, so a variant added upstream that
    nothing here knows about arrives as a failure in this file.
    """
    del name
    draw([event])


def test_the_union_is_fully_covered() -> None:
    """A guard on the list above. `ChatEvent` gaining a variant should fail *here*, where the fix
    is to write a renderer — not silently in a terminal three milestones later."""
    from typing import get_args

    from hera_chats import ChatEvent as Union

    known = {type(event) for _, event in EVERY_VARIANT}
    declared = set(get_args(get_args(Union)[0]))

    assert declared == known, f"unrendered: {sorted(t.__name__ for t in declared - known)}"


def test_an_unknown_variant_degrades_visibly() -> None:
    """**Never silently.**

    A build that swallowed a variant it did not recognise would look identical to one where the
    model never emitted it, and the difference is the whole bug.
    """

    class FromTheFuture:
        type = "dreamt"

    out = draw([FromTheFuture()])  # type: ignore[list-item]

    assert "unknown event" in out
    assert "dreamt" in out


# -- the gutter -------------------------------------------------------------------------------


def test_a_tool_call_draws_one_row_not_three() -> None:
    """The started row, the ready row and the result are **one row**, keyed on the call id."""
    out = draw(
        [
            ToolCallStarted(id="c1", name="code__read"),
            ToolCallReady(id="c1", name="code__read", arguments={"path": "src/api.py"}),
            ToolResultEvent(call_id="c1", tool="code__read", duration_ms=12),
        ]
    )

    assert out.count(GUTTER) == 1
    assert "src/api.py" in out


def test_a_resumed_turn_draws_the_same_gutter_as_the_live_one() -> None:
    """**The property that makes a reload safe.**

    A persisted turn has strictly fewer events — `tool_call_started` is never stored — and the two
    must produce the same rows. If this ever fails, a person reloading a session sees a different
    history from the one they watched happen.
    """
    live: list[ChatEvent] = [
        ToolCallStarted(id="c1", name="code__grep"),
        ToolCallReady(id="c1", name="code__grep", arguments={"pattern": "def get"}),
        ToolResultEvent(call_id="c1", tool="code__grep", duration_ms=8),
        TextDelta(text="Found it."),
    ]
    persisted = [event for event in live if not isinstance(event, ToolCallStarted)]

    assert draw(live) == draw(persisted)


def test_a_skill_says_why_it_is_there() -> None:
    """hera's ADR 5. A person needs to tell *it always has this* from *it went and found this*."""
    assert "pinned" in draw([SkillSelected(skill="fastapi", reason="pinned")])
    assert "slash" in draw([SkillSelected(skill="tdd", reason="slash")])

    retrieved = draw([SkillSelected(skill="writing", reason="retrieved", score=0.82)])
    assert "retrieved" in retrieved
    assert "0.82" in retrieved


def test_its_own_tools_name_what_they_did() -> None:
    """The mark has already said whose tool it is; a reader wants *which file*."""
    out = draw([ToolCallReady(id="c", name="code__read", arguments={"path": "a.py"})])

    assert "read" in out
    assert "code__read" not in out


def test_a_foreign_tool_names_where_it_came_from() -> None:
    """The opposite: the server is the most important thing about `mcp-find`."""
    out = draw([ToolCallReady(id="c", name="docker__mcp_find", arguments={})])

    assert "docker" in out


def test_thinking_is_one_row_per_block() -> None:
    """It thinks, calls something, reads the result and thinks again — two rows with the call
    between them, not one row that grew."""
    out = draw(
        [
            ThinkingDelta(text="one two three"),
            ToolCallReady(id="c", name="code__read", arguments={"path": "a.py"}),
            ThinkingDelta(text="four five"),
        ]
    )

    assert out.count("thought") == 2


def test_thinking_is_collapsed_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    """It is not the answer. A shut block is a receipt, and the words stay out of the transcript."""
    out = draw([ThinkingDelta(text="a secret deliberation nobody asked for")])

    assert "secret deliberation" not in out
    assert "thought" in out


# -- failures ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "reads"),
    [
        ("denied", "not allowed"),
        ("unknown_tool", "no such tool"),
        ("unavailable", "not running"),
        ("timeout", "gave up"),
        ("tool_error", "said no"),
        ("repeated", "already asked"),
    ],
)
def test_every_failure_says_what_happened_in_words(failure: str, reads: str) -> None:
    """**The words carry the meaning, not only the colour.** This is what makes the gutter legible
    with `NO_COLOR` set rather than merely usable."""
    out = draw([ToolResultEvent(call_id="c", tool="code__read", ok=False, failure=failure)], PLAIN)

    assert reads in out


def test_the_quiet_failures_are_not_coloured() -> None:
    """`unknown_tool`, `tool_error` and `repeated` are the system behaving correctly. Alarming a
    person about them teaches them to ignore the colour that matters."""
    from hera_code.tui.gutter import LOUD

    assert "unknown_tool" not in LOUD
    assert "tool_error" not in LOUD
    assert "repeated" not in LOUD
    assert "denied" in LOUD


# -- the cards --------------------------------------------------------------------------------


def test_the_permission_card_shows_the_rules_own_reason() -> None:
    """*Why am I being asked this* should not be a question only a configuration file can answer."""
    out = draw(
        [
            PermissionRequired(
                call_id="c",
                tool="code__bash",
                arguments={"command": "pytest -q"},
                reason="runs a command in your working tree",
            )
        ]
    )

    assert "code__bash" in out
    assert "pytest -q" in out
    assert "runs a command in your working tree" in out


def test_the_permission_card_offers_three_choices() -> None:
    out = draw([PermissionRequired(call_id="c", tool="code__write")])

    assert "Allow once" in out
    assert "Always allow" in out
    assert "Deny" in out


def test_an_answered_permission_card_shows_what_stuck() -> None:
    """**An action keeps its name all the way through.** *Always allow* produces *Always allowed*,
    so nobody wonders whether the decision stuck."""
    out = draw(
        [
            PermissionRequired(call_id="c", tool="code__write"),
            PermissionDecided(call_id="c", allowed=True, remembered=True),
        ]
    )

    assert "Always allowed" in out
    assert "[ Allow once ]" not in out, "a settled card must not show live buttons"


def test_a_denied_card_says_so() -> None:
    out = draw(
        [
            PermissionRequired(call_id="c", tool="code__bash"),
            PermissionDecided(call_id="c", allowed=False),
        ]
    )

    assert "Denied" in out


@pytest.mark.parametrize(
    ("kind", "reads"),
    [("unsure", "it is unsure"), ("blocked", "it cannot go on"), ("choice", "needs you to choose")],
)
def test_the_question_card_uses_the_persons_wording(kind: str, reads: str) -> None:
    out = draw([AnswerRequired(call_id="c", tool="code__ask", question="Which?", kind=kind)])

    assert reads in out
    assert "Which?" in out


def test_an_unrecognised_kind_draws_nothing_rather_than_the_raw_word() -> None:
    """The only way to get one is a turn persisted before the set was closed, and an unfamiliar
    label on a question card is a puzzle rather than information."""
    out = draw([AnswerRequired(call_id="c", tool="code__ask", question="Which?", kind="curious")])

    assert "curious" not in out
    assert "Which?" in out


def test_an_answered_question_shows_the_reply() -> None:
    out = draw(
        [
            AnswerRequired(call_id="c", tool="code__ask", question="Redis?"),
            AnswerGiven(call_id="c", text="Yes, redis."),
        ]
    )

    assert "Yes, redis." in out


def test_a_question_is_never_drawn_as_a_failure() -> None:
    """**No question it can ask is an error.** Drawing one in the failure colour would make being
    asked feel like being stopped."""
    from hera_code.tui.cards import KINDS

    assert all(meaning is not Meaning.FAILURE for _, meaning in KINDS.values())


# -- the close --------------------------------------------------------------------------------


def test_a_completed_turn_says_nothing_extra() -> None:
    """The answer is the answer."""
    out = draw([TextDelta(text="Done."), TurnClosed(reason="completed")])

    assert out.strip() == "Done."


@pytest.mark.parametrize(
    ("reason", "reads"),
    [
        ("cancelled", "stopped"),
        ("awaiting_permission", "waiting for you to decide"),
        ("awaiting_answer", "waiting for your answer"),
        ("max_iterations", "answered with what it had"),
    ],
)
def test_a_turn_that_stopped_says_why(reason: str, reads: str) -> None:
    """`awaiting_permission` is **not a failure** and must not read as one."""
    assert reads in draw([TurnClosed(reason=reason)])


def test_a_failed_turn_shows_its_message() -> None:
    out = draw([TurnClosed(reason="failed", error="the endpoint refused the connection")])

    assert "refused the connection" in out


# -- the theme --------------------------------------------------------------------------------


def test_no_color_emits_no_escape_codes() -> None:
    """**The failure mode ADR 3 says this design is most exposed to.**"""
    out = draw(EVERY_VARIANT_EVENTS := [event for _, event in EVERY_VARIANT], PLAIN)

    del EVERY_VARIANT_EVENTS
    assert "\x1b" not in out


def test_no_color_is_honoured_absolutely() -> None:
    theme = detect(environ={"NO_COLOR": "", "TERM": "xterm"}, isatty=True)

    assert not theme.colour
    assert not theme.motion, "colour off means animation off too"
    assert theme.style(Meaning.AUTHORITY) == ""


def test_a_pipe_gets_no_colour_and_no_motion() -> None:
    theme = detect(environ={"TERM": "xterm-256color"}, isatty=False)

    assert not theme.colour
    assert not theme.motion


def test_a_dumb_terminal_gets_no_colour() -> None:
    assert not detect(environ={"TERM": "dumb"}, isatty=True).colour


def test_motion_can_be_turned_off_on_its_own() -> None:
    theme = detect(environ={"TERM": "xterm", "HERA_CODE_MOTION": "off"}, isatty=True)

    assert theme.colour, "colour and motion are separate switches"
    assert not theme.motion


def test_the_config_overrides_detection() -> None:
    """The key exists because detection cannot be relied on, and getting it wrong means brass on a
    light terminal, which is unreadable."""
    env = {"COLORFGBG": "15;0", "TERM": "xterm"}

    assert detect("light", environ=env, isatty=True).dark is False
    assert detect("dark", environ={"COLORFGBG": "0;15"}, isatty=True).dark is True


def test_a_light_terminal_is_detected() -> None:
    assert detect(environ={"COLORFGBG": "0;15", "TERM": "xterm"}, isatty=True).dark is False


def test_dark_is_the_default_when_nothing_says() -> None:
    """Being wrong that way is survivable: the light palette on a dark background is dim but
    readable, and the dark palette on a light one is not."""
    assert detect(environ={"TERM": "xterm"}, isatty=True).dark is True


def test_every_meaning_has_a_colour_in_both_palettes() -> None:
    for meaning in Meaning:
        assert DARK[meaning]
        assert LIGHT[meaning]


def test_prose_is_capped_at_the_measure() -> None:
    """A reading column that runs the width of a monitor is the fastest way to make a text
    interface tiring, and every wide terminal is a monitor's width."""
    theme = Theme()

    assert theme.measure(200) == MEASURE
    assert theme.measure(40) == 40


# -- the mark ---------------------------------------------------------------------------------


def test_the_beat_is_still_when_motion_is_off() -> None:
    """`prefers-reduced-motion`, inherited without softening. A still frame shows the *open* eye —
    the terminal must be completely legible with all motion off."""
    assert frame(PLAIN, 0.0) == MARK
    assert frame(PLAIN, 1.7) == MARK


def test_the_beat_moves_when_motion_is_on() -> None:
    seen = {frame(DARK_THEME, t) for t in (0.0, 0.7, 1.3, 2.0)}

    assert len(seen) > 1
    assert seen <= set(BEAT)


def test_nothing_else_uses_a_ringed_glyph() -> None:
    """**The one absolute visual rule**, and a rule with no way to check it is a convention.

    The mark is what the interface is remembered by. A well-meant `●` in a list would take that
    away one bullet at a time, and nobody would notice in review.
    """
    import inspect

    from hera_code.tui import cards, gutter, transcript

    allowed = {"◉", "▤"}  # the mark, and the flat glyph for a skill or a read
    for module in (cards, transcript):
        source = inspect.getsource(module)
        used = RESERVED & set(source)
        assert not used - allowed, f"{module.__name__} uses a reserved glyph: {sorted(used)}"

    # The gutter is where the mark legitimately lives, so it is checked differently: only the
    # ocellus itself, and only via the constant.
    assert "MARK" in inspect.getsource(gutter.row_for_thinking)


def test_the_gutter_hairline_is_not_a_ringed_glyph() -> None:
    assert GUTTER not in RESERVED


# -- prose ------------------------------------------------------------------------------------


def test_markdown_is_typeset_not_shown_as_source() -> None:
    out = draw([TextDelta(text="# Heading\n\nSome **bold** words.")])

    assert "**bold**" not in out
    assert "bold" in out


def test_tex_is_left_as_itself() -> None:
    """A terminal cannot set a formula, and a fake is worse than the source."""
    out = draw([TextDelta(text="The bound is $O(n^2)$ here.")], PLAIN)

    assert "O(n^2)" in out


def test_plain_text_is_plain_when_colour_is_off() -> None:
    """Markdown without colour would still restyle headings into something that reads as
    decoration. Plain text is the honest answer, and it is what a pipe wants."""
    out = draw([TextDelta(text="# Heading\n\nbody")], PLAIN)

    assert "# Heading" in out


def test_a_turn_with_nothing_in_it_draws_nothing(capsys: Any) -> None:
    del capsys
    assert draw([]).strip() == ""
