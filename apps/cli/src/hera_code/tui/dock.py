"""The pinned dock: the three rows that never scroll away.

```
────────────────────────────────────────────────────────────
 ┆ TODOS  1/4   ▸ a2  add the token bucket           ^T all
 ›  _
   ＋ coding          main ✱3      ⏎ send  ⇧⏎ newline  ^C stop
────────────────────────────────────────────────────────────
```

**Row one is the todo strip**, and it is why the todo list is a feature rather than a printout — a
list that scrolled away three screens ago is not steering anything. It is empty until v0.1.0 M4
fills it, and the row is here now so that landing the list is one function rather than a
restructure.

**Row two is the composer.** Multi-line, `⏎` sends, `⇧⏎` newline, `/` opens the command menu and
`@` completes a path. Focused on load, because the first thing a person does is type.

**Row three is the status line.** Profile, branch and dirty count, and the keys that apply right
now — which change while a turn is running, and saying `^C stop` only when there is something to
stop is the difference between a hint and a decoration.

Below 80 columns it drops to two rows and the todo strip shortens. Nothing is removed, only the
resting state is quieter — hera's mobile rule, kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_toolkit.formatted_text import StyleAndTextTuples

from hera_code.tui.ocellus import GUTTER, MARK
from hera_code.tui.theme import Meaning, Theme

NARROW = 80
"""Where the dock drops to two rows. One breakpoint, shared, rather than each row choosing its
own — the same discipline hera's single 780px breakpoint has."""


@dataclass
class Todo:
    """One item on the strip. The real model is `hera_code_todos` in M4; this is what it renders
    to, so landing that milestone does not have to reshape the dock."""

    id: str
    text: str
    state: str = " "


@dataclass
class Status:
    """What the dock knows about right now."""

    profile: str = ""
    branch: str = ""
    dirty: int = 0
    running: bool = False
    todos: list[Todo] = field(default_factory=list)
    expanded: bool = False
    """`^T`. Expands the strip into the whole list, in place — the dock grows and the transcript
    scrolls up, which is what the terminal does anyway."""

    @property
    def done(self) -> int:
        return sum(1 for todo in self.todos if todo.state == "x")

    @property
    def blocked(self) -> int:
        return sum(1 for todo in self.todos if todo.state == "!")

    @property
    def current(self) -> Todo | None:
        """The one in progress, or the first that is not done.

        Falling back rather than showing nothing: a list where nothing is marked in progress is
        still a list somebody is working through, and the next item is the useful thing to show.
        """
        for todo in self.todos:
            if todo.state == ">":
                return todo
        return next((todo for todo in self.todos if todo.state == " "), None)


def todo_strip(status: Status, theme: Theme, width: int) -> StyleAndTextTuples:
    """Row one. Progress, and the one item in progress.

    **Blocked items are counted separately**, because an item nobody could decide is visibly
    different from an item nobody started — and collapsing the two is how a stalled run looks like
    a slow one.

    With no list at all this is an invitation rather than an empty bar: empty states say what the
    thing is for.
    """
    muted = theme.style(Meaning.MUTED)
    if not status.todos:
        return [(muted, f" {GUTTER} no plan yet — say what you want and we will make one")]

    parts: StyleAndTextTuples = [
        (muted, f" {GUTTER} "),
        (theme.style(Meaning.AUTHORITY), "TODOS"),
        (muted, f"  {status.done}/{len(status.todos)}"),
    ]
    if status.blocked:
        parts.append((theme.style(Meaning.AUTHORITY), f" · {status.blocked} blocked"))

    current = status.current
    if current is not None:
        room = max(width - 40, 12)
        label = current.text if len(current.text) <= room else f"{current.text[: room - 1]}…"
        parts.append((muted, "   ▸ "))
        parts.append((muted, f"{current.id}  " if width >= NARROW else ""))
        parts.append(("", label))

    parts.append((muted, "   ^T all" if not status.expanded else "   ^T less"))
    return parts


def todo_list(status: Status, theme: Theme) -> StyleAndTextTuples:
    """The whole list, when `^T` is on. One line each, with the state as a glyph."""
    glyphs = {" ": "○", ">": "▸", "x": "✓", "!": "!"}
    meanings = {
        " ": Meaning.MUTED,
        ">": Meaning.ATTENTION,
        "x": Meaning.MUTED,
        "!": Meaning.AUTHORITY,
    }
    lines: StyleAndTextTuples = []
    for todo in status.todos:
        style = theme.style(meanings.get(todo.state, Meaning.MUTED))
        lines.append((theme.style(Meaning.MUTED), f" {GUTTER} "))
        lines.append((style, f"{glyphs.get(todo.state, '○')} {todo.id}  "))
        lines.append((style, todo.text))
        lines.append(("", "\n"))
    return lines


def status_line(status: Status, theme: Theme, width: int) -> StyleAndTextTuples:
    """Row three. What is true, and what the keys do right now.

    The keys change with the state — `^C stop` appears only while there is a turn to stop, because
    a hint that is always there is one nobody reads.
    """
    muted = theme.style(Meaning.MUTED)
    parts: StyleAndTextTuples = [(muted, "   ")]

    if status.profile:
        parts.append((theme.style(Meaning.ITS_OWN), status.profile))
    if status.branch and width >= NARROW:
        parts.append((muted, f"   {status.branch}"))
        if status.dirty:
            parts.append((theme.style(Meaning.AUTHORITY), f" ✱{status.dirty}"))

    keys = "^C stop" if status.running else "⏎ send   ⇧⏎ newline   ^T todos   ^C quit"
    parts.append((muted, f"      {keys}"))
    return parts


def header(theme: Theme, version: str, root: str, status: Status) -> StyleAndTextTuples:
    """The one line printed above the transcript when a session opens.

    Printed into scrollback rather than pinned, because it is true once and a person scrolling
    back should find it where the session started.
    """
    muted = theme.style(Meaning.MUTED)
    parts: StyleAndTextTuples = [
        (theme.style(Meaning.AUTHORITY), f"  {MARK}  "),
        (theme.style(Meaning.ITS_OWN), "hera-code"),
        (muted, f" {version}    {root}"),
    ]
    if status.branch:
        parts.append((muted, f"  {status.branch}"))
        if status.dirty:
            parts.append((theme.style(Meaning.AUTHORITY), f" ✱{status.dirty}"))
    return parts
