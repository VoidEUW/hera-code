"""Answering a card.

Two small prompts, and the thing they have in common is that **the safe answer is the one a
mistyped key reaches**. `Esc` denies a permission and abandons a question; there is no key that
allows something by accident.

Each is its own short-lived `Application` rather than a mode the main dock enters. A card is a
thing that happens *between* turns — the turn has already closed and been persisted — so there is
no state to keep and nothing to unwind if a person walks away.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

from hera_chats import AnswerRequired, PermissionRequired
from hera_code.tui.cards import CHOICES, KINDS
from hera_code.tui.theme import Meaning, Theme

ALLOW_ONCE, ALWAYS_ALLOW, DENY = 0, 1, 2


@dataclass(frozen=True)
class Answer:
    """What a person said to a permission card."""

    allowed: bool
    remembered: bool = False
    """Whether it should also become a rule. **Always allow must be visibly different from Allow
    once afterwards**, or nobody can tell whether it stuck."""


async def ask_permission(event: PermissionRequired, theme: Theme) -> Answer:
    """Draw the three choices and wait.

    `←`/`→` move, `⏎` chooses, and **`Esc` denies** — denying is the safe default, so it is what a
    mistyped key should land on. `a`, `w` and `d` are shortcuts for people who would rather not
    arrow.
    """
    selected = ALLOW_ONCE
    keys = KeyBindings()

    def choose(index: int) -> None:
        application.exit(result=index)

    @keys.add("left")
    def _left(_: object) -> None:
        nonlocal selected
        selected = max(0, selected - 1)

    @keys.add("right")
    def _right(_: object) -> None:
        nonlocal selected
        selected = min(len(CHOICES) - 1, selected + 1)

    @keys.add("enter")
    def _enter(_: object) -> None:
        choose(selected)

    @keys.add("escape")
    @keys.add("c-c")
    def _escape(_: object) -> None:
        choose(DENY)

    @keys.add("a")
    def _allow(_: object) -> None:
        choose(ALLOW_ONCE)

    @keys.add("w")
    def _always(_: object) -> None:
        choose(ALWAYS_ALLOW)

    @keys.add("d")
    def _deny(_: object) -> None:
        choose(DENY)

    def render() -> StyleAndTextTuples:
        return _choices(selected, theme, event)

    application: Application[int] = Application(
        layout=Layout(HSplit([Window(FormattedTextControl(render), height=2)])),
        key_bindings=keys,
        full_screen=False,
        erase_when_done=True,
    )
    picked = await application.run_async()
    return Answer(allowed=picked != DENY, remembered=picked == ALWAYS_ALLOW)


async def ask_question(event: AnswerRequired, theme: Theme) -> str:
    """Draw the question and take a reply.

    Returns `""` when a person walked away, which the caller treats as *no answer* rather than as
    an empty one — `hera_chats` already renders that to the model as *they replied with nothing;
    take it as no answer and carry on*.
    """
    buffer = Buffer(multiline=False)
    keys = KeyBindings()

    @keys.add("enter")
    def _send(_: object) -> None:
        application.exit(result=buffer.text)

    @keys.add("escape")
    @keys.add("c-c")
    def _abandon(_: object) -> None:
        application.exit(result="")

    def render() -> StyleAndTextTuples:
        label = KINDS.get(event.kind)
        parts: StyleAndTextTuples = []
        if label is not None:
            parts.append((theme.style(label[1]), f"  {label[0]}\n"))
        parts.append((theme.style(Meaning.ATTENTION), f"  {event.question}\n"))
        return parts

    application: Application[str] = Application(
        layout=Layout(
            HSplit(
                [
                    Window(FormattedTextControl(render), height=2),
                    Window(BufferControl(buffer), height=1),
                ]
            )
        ),
        key_bindings=keys,
        full_screen=False,
        erase_when_done=True,
    )
    return str(await application.run_async())


def _choices(selected: int, theme: Theme, event: PermissionRequired) -> StyleAndTextTuples:
    muted = theme.style(Meaning.MUTED)
    brass = theme.style(Meaning.AUTHORITY)

    parts: StyleAndTextTuples = [(brass, f"  Run {event.tool}?"), (muted, "\n  ")]
    for index, choice in enumerate(CHOICES):
        marker = "▸" if index == selected else " "
        style = brass if index == selected else muted
        parts.append((style, f"{marker} [ {choice} ]  "))
    parts.append((muted, "   ←→ ⏎    Esc denies"))
    return parts
