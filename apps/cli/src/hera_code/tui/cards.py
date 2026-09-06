"""The two cards that suspend a turn.

Both are drawn from the **event**, not from the call. The call, the card and the synthesised
result are all about one question; drawing three of them would be machinery pretending to be
conversation.

**The permission card is brass — this is authority.** The one moment the terminal blocks. Tool,
arguments, and the deciding rule's own `reason` as the third line: filling that field in is why it
exists, because *why am I being asked this* should not be a question only a configuration file can
answer.

**The question card is laurel, not brass**, and the difference is the whole point. A question is
the agent turning towards you; drawing it in the permission colour would make being asked feel
like being stopped. **Nothing here may be the failure colour: no question it can ask is an error.**
"""

from __future__ import annotations

from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from hera_chats import AnswerGiven, AnswerRequired, PermissionDecided, PermissionRequired
from hera_code.tui.theme import Meaning, Theme

KINDS: dict[str, tuple[str, Meaning]] = {
    "unsure": ("it is unsure", Meaning.MUTED),
    "blocked": ("it cannot go on", Meaning.AUTHORITY),
    "choice": ("it needs you to choose", Meaning.MUTED),
}
"""The closed set of three, and **the person's wording rather than the tool's**.

Only `blocked` is set apart, because it is the one where the turn is genuinely stopped on the
reply. A kind this build does not recognise draws **nothing** rather than the raw word — the only
way to get one is a turn persisted before the set was closed, and an unfamiliar label on a
question card is a puzzle rather than information.
"""

CHOICES = ("Allow once", "Always allow", "Deny")
"""In the order they are offered, and **`Deny` is what `Esc` reaches**.

Denying is the safe default, so it is the one a mistyped key should land on. `Always allow` writes
a rule and says so afterwards, because a person should never wonder whether a decision stuck.
"""


class Card:
    """A card that can be answered, and that knows when it has been.

    A class rather than a function because a resumed session has to show a *settled* card rather
    than live buttons, and the events that settle it (`PermissionDecided`, `AnswerGiven`) arrive
    separately from the ones that raise it. Inferring it from whether a result turned up later
    would be a rule about event ordering living in the renderer, which is the shape this design
    exists to avoid.
    """

    def __init__(self, call_id: str, theme: Theme) -> None:
        self.call_id = call_id
        self.theme = theme
        self.answer: str = ""
        self.answered = False

    def settle(self, event: PermissionDecided | AnswerGiven) -> None:
        self.answered = True
        if isinstance(event, PermissionDecided):
            if not event.allowed:
                self.answer = "Denied"
            else:
                self.answer = "Always allowed" if event.remembered else "Allowed once"
        else:
            self.answer = event.text.strip()

    def __rich__(self) -> RenderableType:  # pragma: no cover - overridden below
        raise NotImplementedError


class PermissionCard(Card):
    """*May I?* — brass, and the one moment the terminal blocks."""

    def __init__(self, event: PermissionRequired, theme: Theme) -> None:
        super().__init__(event.call_id, theme)
        self.event = event

    def __rich__(self) -> RenderableType:
        style = self.theme.style(Meaning.AUTHORITY)
        body: list[RenderableType] = [Text(f"Run {self.event.tool}?", style=style)]

        arguments = _arguments(self.event.arguments)
        if arguments:
            body.append(Text(arguments, style=self.theme.style(Meaning.MUTED), overflow="ellipsis"))
        if self.event.reason:
            # The rule's own words. This line is why `Rule.reason` exists.
            body.append(Text(self.event.reason, style=self.theme.style(Meaning.MUTED)))

        body.append(Text(""))
        body.append(self._footer())
        return Panel(Group(*body), border_style=style, expand=False)

    def _footer(self) -> Text:
        if self.answered:
            # An action keeps its name all the way through: **Always allow** produces
            # *Always allowed*, so nobody has to wonder whether it stuck.
            return Text(self.answer, style=self.theme.style(Meaning.MUTED))
        line = Text()
        for index, choice in enumerate(CHOICES):
            if index:
                line.append("   ")
            line.append(f"[ {choice} ]", style=self.theme.style(Meaning.AUTHORITY))
        line.append("    ←→ ⏎   Esc denies", style=self.theme.style(Meaning.MUTED))
        return line


class QuestionCard(Card):
    """*I need to know something* — laurel, because this is not being stopped."""

    def __init__(self, event: AnswerRequired, theme: Theme) -> None:
        super().__init__(event.call_id, theme)
        self.event = event

    def __rich__(self) -> RenderableType:
        style = self.theme.style(Meaning.ATTENTION)
        body: list[RenderableType] = []

        label = KINDS.get(self.event.kind)
        if label is not None:
            # An unrecognised kind draws nothing rather than the raw word.
            body.append(Text(label[0], style=self.theme.style(label[1])))
        body.append(Text(self.event.question or "(no question)", style=style))
        body.append(Text(""))
        body.append(self._footer())
        return Panel(Group(*body), border_style=style, expand=False)

    def _footer(self) -> Text:
        if self.answered:
            return Text(f"› {self.answer}", style=self.theme.style(Meaning.MUTED))
        return Text("›  (type your answer, ⏎ to send)", style=self.theme.style(Meaning.MUTED))


def permission_card(event: PermissionRequired, theme: Theme) -> PermissionCard:
    return PermissionCard(event, theme)


def question_card(event: AnswerRequired, theme: Theme) -> QuestionCard:
    return QuestionCard(event, theme)


def _arguments(arguments: dict[str, Any]) -> str:
    """The call's arguments on one line.

    Shortened, because a card showing a whole file's contents is a card nobody reads — and a
    person deciding whether to allow a write is deciding about the *path*, which is what stays.
    """
    parts = []
    for key, value in arguments.items():
        text = value if isinstance(value, str) else repr(value)
        if len(text) > 60:
            text = f"{text[:57]}…"
        parts.append(f"{key}={text}" if len(arguments) > 1 else text)
    return "  ".join(parts)
