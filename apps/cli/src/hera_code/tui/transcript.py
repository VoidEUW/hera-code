"""One renderer per `ChatEvent` variant, and **no parser anywhere**.

This is the rule the whole design hangs on, inherited from hera where it is the single largest
source of bugs in the previous generation and is designed out: the terminal renders event variants
it is handed. A new thing the model can do is a new variant, never a regular expression.
Typesetting Markdown is not that parser and may not become one — it draws text as what it is and
reads no meaning back out of it.

**An unknown variant degrades visibly.** A row saying `? unknown event: <type>` is information;
nothing at all is a bug that hides itself, and a build that silently dropped a variant it did not
know would look identical to one where the model never emitted it.

**The started row and the ready row are the same row.** `tool_call_started` is never persisted, so
a resumed session has strictly fewer events than the live one had — and the renderer has to
produce the same rows from both. Keying on the call id is what makes that true, and it is why
`render_turn` builds a merged view rather than drawing events in the order they arrive.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.text import Text

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
from hera_code.tui.cards import Card, permission_card, question_card
from hera_code.tui.gutter import Row, gutter, row_for_result, row_for_skill, row_for_thinking
from hera_code.tui.theme import Meaning, Theme
from hera_providers import TextDelta, ThinkingDelta, ToolCallReady, ToolCallStarted

FAILURE_WORDS: dict[str, str] = {
    "denied": "not allowed",
    "unknown_tool": "no such tool",
    "unavailable": "not running",
    "timeout": "gave up waiting",
    "tool_error": "said no",
    "repeated": "already asked",
}
"""What each `Failure` reads as.

**The words carry the meaning, not only the colour**, which is what makes the transcript legible
with `NO_COLOR` set. `gutter.py` decides which of these is loud and which is muted, and that
split is the deliberate part: `unknown_tool`, `tool_error` and `repeated` are the system behaving
correctly, and alarming a person about them teaches them to ignore the colour that matters.
"""


@dataclass
class Turn:
    """A turn, merged into what is drawn.

    Not a list of events in arrival order. Tool calls are keyed by id so that the started row, the
    ready row and the result are one row; everything else keeps its place relative to them.
    """

    rows: list[Row] = field(default_factory=list)
    prose: list[str] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    """Typed as `Card` rather than `RenderableType` so a caller can ask which one is waiting.
    A renderable that has to be `getattr`-ed for its identity is one nothing can filter."""
    unknown: list[str] = field(default_factory=list)
    closed: TurnClosed | None = None

    _by_call: dict[str, Row] = field(default_factory=dict, repr=False)


def render_turn(events: Sequence[ChatEvent], theme: Theme, *, width: int = 0) -> RenderableType:
    """Everything a turn produced, as one renderable.

    Used for the persisted re-render at `turn_closed` and by the snapshot suite. The live view
    draws the same pieces as they arrive, through the same functions — which is what stops the two
    disagreeing.
    """
    turn = collect(events, theme)
    blocks: list[RenderableType] = []

    if turn.rows:
        blocks.append(gutter(turn.rows, theme))
    blocks.extend(turn.cards)

    text = "".join(turn.prose).strip()
    if text:
        blocks.append(prose(text, theme, width=width))

    for kind in turn.unknown:
        blocks.append(unknown_event(kind, theme))

    if turn.closed is not None and turn.closed.reason != "completed":
        blocks.append(closing(turn.closed, theme))

    return Group(*blocks)


def collect(events: Sequence[ChatEvent], theme: Theme) -> Turn:
    """Fold an event list into what gets drawn.

    Exhaustive over the union on purpose: the `else` at the bottom is what catches a variant added
    upstream that nothing here knows about, and it produces a visible row rather than silence.
    """
    turn = Turn()
    for event in events:
        _fold(turn, event, theme)
    return turn


def _fold(turn: Turn, event: ChatEvent, theme: Theme) -> None:
    if isinstance(event, TextDelta):
        turn.prose.append(event.text)

    elif isinstance(event, ThinkingDelta):
        turn.rows.append(row_for_thinking(event.text, theme))

    elif isinstance(event, ToolCallStarted):
        # Progress, never persisted. It creates the row so a person sees something is happening
        # minutes before the arguments finish arriving -- and the ready event finds it again.
        turn._by_call[event.id] = _tool_row(turn, event.id, event.name, theme)

    elif isinstance(event, ToolCallReady):
        row = turn._by_call.get(event.id) or _tool_row(turn, event.id, event.name, theme)
        row.target = _target(event.name, event.arguments)

    elif isinstance(event, ToolResultEvent):
        row = turn._by_call.get(event.call_id) or _tool_row(turn, event.call_id, event.tool, theme)
        row_for_result(row, event, theme, FAILURE_WORDS)

    elif isinstance(event, SkillSelected):
        turn.rows.append(row_for_skill(event, theme))

    elif isinstance(event, PermissionRequired):
        turn.cards.append(permission_card(event, theme))

    elif isinstance(event, AnswerRequired):
        turn.cards.append(question_card(event, theme))

    elif isinstance(event, PermissionDecided | AnswerGiven):
        # Recorded so a resumed turn shows a settled card rather than live buttons. The card
        # itself carries the outcome, so there is nothing further to draw.
        _settle(turn, event)

    elif isinstance(event, TurnClosed):
        turn.closed = event

    else:
        # Unreachable while the union is what this module was written against, which is exactly
        # when it stops being unreachable. Degrade visibly.
        turn.unknown.append(getattr(event, "type", type(event).__name__))


def _tool_row(turn: Turn, call_id: str, tool: str, theme: Theme) -> Row:
    row = Row(verb=_verb(tool), target="", theme=theme)
    turn.rows.append(row)
    turn._by_call[call_id] = row
    return row


def _settle(turn: Turn, event: PermissionDecided | AnswerGiven) -> None:
    """Mark a card as answered, so a resumed session does not show live buttons."""
    for card in turn.cards:
        if card.call_id == event.call_id:
            card.settle(event)


def _verb(tool: str) -> str:
    """What a gutter row calls this tool.

    **Its own tools name what they did; everybody else's name where they came from.** The mark has
    already said whose tool it is, so `called code read` spends half a short row repeating it —
    where a reader wants *which file*. A foreign tool is the opposite: the server is the most
    important thing about `mcp-find`.

    The mapping reads `code__*` only. A table that learned somebody else's server would make one
    you have not configured look broken beside one you have.
    """
    if not tool.startswith("code__"):
        server, _, rest = tool.partition("__")
        return f"called {server} {rest.replace('_', ' ')}" if rest else f"called {tool}"
    return tool.removeprefix("code__").replace("_", " ")


def _target(tool: str, arguments: dict[str, Any]) -> str:
    """The one argument worth putting on a one-line row.

    Chosen by name rather than by taking the first, because *which* argument matters differs per
    tool and a row showing `limit=2000` instead of the path would be worse than showing nothing.
    """
    for key in ("path", "pattern", "command", "question", "name", "key"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    del tool
    return ""


def prose(text: str, theme: Theme, *, width: int = 0) -> RenderableType:
    """The model's answer, typeset as Markdown and capped at the measure.

    **Not a parser.** It draws text as what it is and reads no meaning back out of it — nothing
    downstream branches on what the Markdown said. That distinction is the whole of ADR 11 in
    hera, and it is why this returns a renderable rather than a parsed structure.

    TeX is dropped. A terminal cannot set a formula, and rendering `$x^2$` as itself is honest
    where a fake would not be.
    """
    if not theme.colour:
        # Markdown rendering without colour would still restyle headings and rules into something
        # that reads as decoration. Plain text is the honest answer, and it is what a pipe wants.
        # `Text` has no width of its own -- the console it is printed to decides. The measure is
        # applied by the caller, which is the thing that knows how wide the terminal is.
        return Text(text, no_wrap=False)
    return Markdown(text, justify="left")


def unknown_event(kind: str, theme: Theme) -> Text:
    """A variant this build does not know, drawn rather than dropped.

    `docs/tui.md`: *degrade visibly, never silently*. A build that swallowed a variant it did not
    recognise would look identical to one where the model never emitted it, and the difference is
    the whole bug.
    """
    return Text(f"? unknown event: {kind}", style=theme.style(Meaning.MUTED))


def closing(closed: TurnClosed, theme: Theme) -> Text:
    """What ended the turn, when it was not simply finished.

    A completed turn draws nothing — the answer is the answer. Everything else says what happened
    in the person's words rather than the union's: `awaiting_permission` is not a failure and must
    not read as one.
    """
    words = {
        "cancelled": ("stopped", Meaning.MUTED),
        "awaiting_permission": ("waiting for you to decide", Meaning.AUTHORITY),
        "awaiting_answer": ("waiting for your answer", Meaning.ATTENTION),
        "max_iterations": ("answered with what it had", Meaning.MUTED),
        "failed": (closed.error or "something went wrong", Meaning.FAILURE),
    }
    text, meaning = words.get(closed.reason, (closed.reason, Meaning.MUTED))
    return Text(f"— {text}", style=theme.style(meaning))
