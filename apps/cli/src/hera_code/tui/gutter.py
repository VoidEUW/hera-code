"""The activity gutter: everything the agent did, as a column of eyes.

Everything done before speaking stacks above the prose as collapsed rows, each with its ocellus on
a hairline. Quiet, dimmed, one line each. A turn with six tool calls draws six eyes down its left
gutter — **activity becomes a column you read at a glance**, which is how much it did and where.

```
┆◉  thought    61 words
┆▤  skill      fastapi                                    skill · pinned
┆◍  grep       def get_                                          8 matches
┆⌨  bash       pytest -q                                      2.1 s  exit 0
┆🔧 called Docker mcp find                                          210 ms
```

**Skills say why they are there.** hera's ADR 5 selects them in code — pinned, `/slash`, or
retrieved — and the row shows which of the three it was. A person needs to tell *it always has
this* from *it went and found this*, and it is the only feedback loop that reveals retrieval
picking the wrong thing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from rich.console import Group, RenderableType
from rich.text import Text

from hera_chats import SkillSelected, ToolResultEvent
from hera_code.tui.ocellus import GUTTER, MARK
from hera_code.tui.theme import Meaning, Theme

VERB_WIDTH = 11
LOUD: frozenset[str] = frozenset({"denied", "unavailable", "timeout"})
"""The failures worth a colour.

The other three — `unknown_tool`, `tool_error`, `repeated` — are **the system behaving
correctly**: a model correcting itself, a tool that worked and said no, a call the repeat limiter
caught. Alarming a person about those teaches them to ignore the colour that matters, which is the
whole reason this set is smaller than the failure list.
"""

GLYPHS: dict[str, str] = {
    "thought": "◉",
    "skill": "▤",
    "read": "▤",
    "glob": "◍",
    "grep": "◍",
    "write": "✎",
    "edit": "✎",
    "bash": "⌨",
    "ask": "?",
}
"""What each kind of row is marked with. Anything unlisted gets a wrench, which is what a foreign
server's tool should look like — see `transcript._verb`."""

FOREIGN = "🔧"


@dataclass
class Row:
    """One line of the gutter, filled in as the turn goes.

    Mutable, and that is the point: the started event creates it, the ready event fills in the
    target, and the result fills in the outcome. **One row, keyed on the call id**, which is what
    makes a live turn and a resumed one draw the same thing despite the resumed one having fewer
    events.
    """

    verb: str
    target: str
    theme: Theme
    detail: str = ""
    meaning: Meaning = Meaning.MUTED
    glyph: str = ""
    done: bool = False
    extra: list[str] = field(default_factory=list)

    def render(self) -> Text:
        glyph = self.glyph or GLYPHS.get(self.verb.split()[0], FOREIGN)
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(GUTTER, style=self.theme.style(Meaning.MUTED))
        line.append(f"{glyph} ", style=self.theme.style(self._glyph_meaning()))
        line.append(f"{self.verb:<{VERB_WIDTH}}", style=self.theme.style(Meaning.MUTED))
        line.append(self.target, style=self.theme.style(self.meaning))
        if self.detail:
            line.append(f"  {self.detail}", style=self.theme.style(Meaning.MUTED))
        return line

    def _glyph_meaning(self) -> Meaning:
        """Laurel while it is running, muted once it has finished.

        Where hera varies the ocellus by size, this varies it by state — *attention* means live,
        which is the sentence that colour is allowed to say.
        """
        if self.meaning is Meaning.FAILURE:
            return Meaning.FAILURE
        return Meaning.MUTED if self.done else Meaning.ATTENTION


def gutter(rows: Sequence[Row], theme: Theme) -> RenderableType:
    """The whole column. Nothing at all when there is nothing to say."""
    del theme
    return Group(*(row.render() for row in rows))


def row_for_thinking(text: str, theme: Theme) -> Row:
    """One reasoning block, collapsed to a count.

    **Blocks, not one row that grew.** It thinks, calls something, reads the result and thinks
    again — so that is two rows with the call between them. Folding a turn's reasoning into a
    single row at the top would put the second half of the thinking above the call that caused it,
    and the only way to read the turn in order would be to scroll back.

    The two-line tail hera's design shows is v0.2.0 M1; here a shut block is a count, which is
    honest about being a receipt.
    """
    words = len(text.split())
    return Row(
        verb="thought",
        target=f"{words} word{'' if words == 1 else 's'}",
        theme=theme,
        glyph=MARK,
        done=True,
    )


def row_for_skill(event: SkillSelected, theme: Theme) -> Row:
    """One skill, and **why it is there** — pinned, slash, or retrieved.

    hera's ADR 5 chose them in code, and the reason is persisted rather than derived because it is
    not recoverable later: it depended on what the pins were and what the scores came out as at
    that moment, and both change.
    """
    reason: str = event.reason
    if event.reason == "retrieved" and event.score is not None:
        # The score is shown only for retrieval, because it is the only one of the three where a
        # number means anything: pinned and slash are decisions, not matches.
        reason = f"retrieved · {event.score:.2f}"
    return Row(
        verb="skill",
        target=event.skill,
        theme=theme,
        detail=reason,
        meaning=Meaning.AUTHORITY,
        done=True,
    )


def row_for_result(row: Row, event: ToolResultEvent, theme: Theme, words: dict[str, str]) -> None:
    """Fill in what a call answered, in place.

    In place rather than appending, because the started row, the ready row and the result are one
    row keyed on the call id — which is what makes a resumed session draw the same gutter as the
    live turn did, despite having strictly fewer events in it.
    """
    del theme
    row.done = True
    if event.ok:
        row.detail = _duration(event.duration_ms)
        return

    failure = event.failure or "failed"
    row.meaning = Meaning.FAILURE if failure in LOUD else Meaning.MUTED
    # The words carry the meaning, not only the colour. This is what makes the gutter legible
    # with NO_COLOR set rather than merely usable.
    row.detail = f"{words.get(failure, failure)}  {_duration(event.duration_ms)}".strip()


def _duration(milliseconds: int) -> str:
    if milliseconds <= 0:
        return ""
    if milliseconds < 1000:
        return f"{milliseconds} ms"
    return f"{milliseconds / 1000:.1f} s"
