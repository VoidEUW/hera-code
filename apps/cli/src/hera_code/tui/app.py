"""The terminal: a pinned dock, and a transcript in real scrollback.

[ADR 3](../../../../../docs/adr/0003-the-transcript-lives-in-scrollback.md) is the decision this
module implements, and the two halves of it are:

**The transcript is printed into the terminal's own scrollback.** The terminal scrolls it, the
mouse selects it, `| less` works, and it is still there after the process exits. Nothing here ever
takes the alternate screen buffer and nothing ever repaints above the dock — which means streaming
output has to be *correct as it goes*, because there is no going back to fix it.

**The dock is a `prompt_toolkit.Application(full_screen=False)`**, anchored at the bottom and
redrawn in place. `run_in_terminal` is what lets us print above it without the two fighting.

The suspension model is inherited whole and is why a card is answerable at all: a turn that needs a
person **closes**, its events are persisted, and answering starts a *new* turn that resumes the
same message. Nothing here holds a turn open waiting.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console, RenderableType
from rich.text import Text
from sqlmodel import Session as DbSession

from hera_chats import AnswerRequired, ChatEvent, PermissionRequired, TurnClosed
from hera_code import __version__
from hera_code import session as sessions
from hera_code.session import Exchange
from hera_code.tui import commands as slash
from hera_code.tui import prompt
from hera_code.tui.dock import Status, header, status_line, todo_list, todo_strip
from hera_code.tui.gutter import gutter
from hera_code.tui.theme import Meaning, Theme
from hera_code.tui.transcript import closing, collect, unknown_event
from hera_code.wiring import Services
from hera_providers import TextDelta


@dataclass
class Settled:
    """What a person answered, in the shape `hera_chats.TurnContext` wants.

    Three ways to settle a call and they arrive on the same footing — allowed, refused, replied to.
    The turn decides which are dispatched; a refusal still produces a result, which is what lets
    the model try something else instead of hanging.
    """

    confirmed: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)


@dataclass
class Pending:
    """A turn that stopped and what it is waiting for.

    Held rather than acted on immediately, because answering is a *new turn* — the loop below
    picks this up on the next pass rather than recursing, which is what keeps `^C` meaningful at
    every point.
    """

    permissions: list[PermissionRequired] = field(default_factory=list)
    questions: list[AnswerRequired] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.permissions or self.questions)


class Terminal:
    """One interactive session.

    Deliberately thin. Everything it draws comes from `transcript.py` and everything it runs comes
    from `session.py`, so the two are exercised by the snapshot suite and the turn tests rather
    than only by driving this.
    """

    def __init__(self, services: Services, theme: Theme, *, root: Path | None = None) -> None:
        self.services = services
        self.theme = theme
        self.root = root or services.workspace.root
        self.status = Status(
            profile="coding",
            branch=services.workspace.branch,
            dirty=services.workspace.dirty,
        )
        # `stderr=False` matters: rich would otherwise decide colour from a stream we are not
        # writing to. `force_terminal` follows the theme so a pipe gets plain text through the
        # same path a terminal gets colour through -- one renderer, two outputs.
        self.console = Console(
            force_terminal=theme.colour or None,
            no_color=not theme.colour,
            soft_wrap=False,
        )
        self._chat_id: UUID | None = None
        self._held: list[ChatEvent] = []
        self._flushed = 0
        self.buffer = Buffer(multiline=True, completer=self._completer())
        self.application = self._build()

    # -- drawing -------------------------------------------------------------------------

    def say(self, renderable: RenderableType) -> None:
        """Print into scrollback, above the dock.

        Everything a person reads goes through here. `run_in_terminal` is what stops the dock and
        the output fighting over the same lines; without it the two interleave and the result is
        a dock printed halfway up the screen.
        """
        self.console.print(renderable)

    def open(self) -> None:
        self.console.print(_plain(header(self.theme, __version__, str(self.root), self.status)))
        self.console.print()

    # -- the loop ------------------------------------------------------------------------

    async def run(self) -> int:
        """Read, run, draw, repeat.

        Returns an exit code so the CLI stays the only thing that calls `sys.exit`.
        """
        self.open()
        with patch_stdout(raw=True):
            while True:
                text = await self._read()
                if text is None:
                    return 0
                if not text.strip():
                    continue

                command = slash.is_command(text)
                if command:
                    if self._builtin(command):
                        return 0
                    continue

                await self._turn(text)

    def _builtin(self, command: str) -> bool:
        """Run one built-in. Returns whether the session should end."""
        if command in {"quit", "exit"}:
            return True
        if command == "help":
            self.say(_styled(_HELP, self.theme, Meaning.MUTED))
        elif command == "skills":
            names = sorted(skill.id for skill in self.services.library.all())
            self.say(
                _styled("  " + ("  ".join(names) or "no skills yet"), self.theme, Meaning.MUTED)
            )
        elif command == "todos":
            self.status.expanded = not self.status.expanded
        elif command == "clear":
            # A *new* session, keeping this one. Nothing is deleted for you -- the old session is
            # still there to resume once M5 gives it a way to be named.
            self._chat_id = None
            self.say(_styled("— new session", self.theme, Meaning.MUTED))
        return False

    async def _read(self) -> str | None:
        """One message from the composer, or ``None`` when the person is done."""
        self.buffer.reset()
        result = await self.application.run_async()
        return None if result is None else str(result)

    async def _turn(self, text: str) -> None:
        """One message, run and drawn — and then answered, for as long as it keeps asking.

        **A loop rather than a recursion**, because a turn can suspend several times: it asks
        whether it may write, writes, then asks whether it may run the tests. Each pass is a whole
        turn that closed and was persisted, which is what makes `^C` meaningful at every point and
        what makes a card survive the process going away.
        """
        self.status.running = True
        try:
            pending = await self._run_once(text)
            while pending:
                settled = await self._settle(pending)
                if settled is None:
                    # Walked away. The turn stays suspended and persisted; nothing is assumed.
                    self.say(_styled("— left waiting", self.theme, Meaning.MUTED))
                    return
                pending = await self._resume(settled)
        except (asyncio.CancelledError, KeyboardInterrupt):
            # `^C`. The turn is already persisted with whatever arrived -- `session.run` records
            # in a `finally` -- so there is nothing to save here, only something to say.
            self.say(_styled("— stopped", self.theme, Meaning.MUTED))
        finally:
            self.status.running = False

    async def _run_once(self, text: str) -> Pending:
        with self.services.database.session() as db:
            # The same session for every message until `/clear`, so a conversation is a
            # conversation rather than a series of unrelated first messages.
            chat = sessions.open_session(db, self.services, chat_id=self._chat_id)
            self._chat_id = chat.id
            exchange = sessions.begin(db, self.services, chat, text, root=self.root)
            return await self._drive(db, exchange)

    async def _resume(self, settled: Settled) -> Pending:
        """Answer the cards and carry on, in the same assistant message."""
        with self.services.database.session() as db:
            chat = sessions.open_session(db, self.services, chat_id=self._chat_id)
            assistant = sessions.latest_assistant(db, chat)
            if assistant is None:  # pragma: no cover - a turn always leaves one
                return Pending()
            exchange = sessions.resume(
                db,
                self.services,
                chat,
                assistant,
                confirmed=settled.confirmed,
                denied=settled.denied,
                answers=settled.answers,
                root=self.root,
            )
            return await self._drive(db, exchange)

    async def _drive(self, db: DbSession, exchange: Exchange) -> Pending:
        # Seeded with the paused half. A resumed turn does not re-stream what the person has
        # already read, so the events that arrive are the *new* ones only -- and a `tool_result`
        # without the `tool_call_ready` that preceded it builds a gutter row with no path on it.
        # The row is printed again rather than updated, because a printed line cannot be rewritten
        # in scrollback; what it must not do is come back emptier than it went.
        self._held = list(exchange.turn.context.resume)
        async for event in sessions.run(db, exchange):
            self._stream(event)
        # **`turn.recorded`, not the events that were yielded.** A resumed turn yields only its
        # *new* events -- the paused half is inherited and deliberately not re-streamed, because
        # the person is already looking at it -- so rendering the yielded list would draw a tool
        # result whose call is missing, and the row would lose the path it was about. `recorded`
        # is the whole turn and is exactly what was persisted.
        recorded = exchange.turn.recorded
        self._finish(recorded)
        return _pending(recorded)

    async def _settle(self, pending: Pending) -> Settled | None:
        """Put every waiting card to the person, in the order they were raised."""
        settled = Settled()
        for event in pending.permissions:
            answer = await prompt.ask_permission(event, self.theme)
            if answer.allowed:
                settled.confirmed.append(event.call_id)
            else:
                settled.denied.append(event.call_id)
            if answer.remembered:
                # **Always allow writes a rule and says so afterwards**, because a person should
                # never wonder whether a decision stuck.
                self.services.always_allow(event.tool, event.reason)
                self.say(_styled(f"— always allowing {event.tool}", self.theme, Meaning.AUTHORITY))
        for question in pending.questions:
            settled.answers[question.call_id] = await prompt.ask_question(question, self.theme)
        return settled

    def _stream(self, event: ChatEvent) -> None:
        """Draw one event as it arrives.

        **Prose is streamed and is never re-printed**, which is the one place scrollback makes the
        design different from hera's. There, `done` replaces the optimistic view; here there is
        nothing above the cursor to replace, so re-rendering the prose at the end would simply
        print the answer twice — which is what it did, until somebody watched it happen.

        The gutter cannot be streamed the same way, because a row is written three times as a call
        starts, becomes ready and answers, and a printed line cannot be rewritten. So the rows are
        held and flushed **once, just before the first word of prose** — which is also where they
        belong: everything done before speaking stacks above what was said.
        """
        if isinstance(event, TextDelta):
            self._flush_gutter()
            self.console.print(event.text, end="", markup=False, highlight=False)
        else:
            self._held.append(event)

    def _flush_gutter(self) -> None:
        """Print the rows held since the last flush, if any."""
        if not self._held:
            return
        held, self._held = self._held, []
        rows = collect(held, self.theme).rows
        if rows:
            self.say(gutter(rows, self.theme))
            self._flushed += len(rows)
        self.console.print()

    def _finish(self, events: Sequence[ChatEvent]) -> None:
        """Draw what streaming could not: the rows still held, the cards, and why it stopped.

        Deliberately **not** a re-render of the whole turn. In scrollback there is nothing above
        the cursor to replace, so printing the persisted list again would print the answer twice.
        What the persisted list is still authoritative for is everything a person has *not* seen
        yet — which after streaming is the cards and the closing line.
        """
        self._flush_gutter()
        turn = collect(events, self.theme)
        pending = _pending(events)

        # **Only the cards still waiting.** `events` is the whole turn including the paused half,
        # so an answered card is in there -- and drawing it again would ask a person something
        # they have already decided.
        waiting = {event.call_id for event in pending.permissions}
        waiting |= {event.call_id for event in pending.questions}
        for card in turn.cards:
            if card.call_id in waiting:
                self.say(card)

        for unknown in turn.unknown:
            self.say(unknown_event(unknown, self.theme))
        if turn.closed is not None and turn.closed.reason != "completed":
            self.say(closing(turn.closed, self.theme))
        self.console.print()

    # -- the dock ------------------------------------------------------------------------

    def _build(self) -> Application[str | None]:
        keys = KeyBindings()

        @keys.add("enter")
        def _send(event: object) -> None:
            self.application.exit(result=self.buffer.text)

        @keys.add("escape", "enter")
        def _newline(event: object) -> None:
            self.buffer.insert_text("\n")

        @keys.add("c-t")
        def _todos(event: object) -> None:
            self.status.expanded = not self.status.expanded

        @keys.add("c-c")
        @keys.add("c-d")
        def _quit(event: object) -> None:
            self.application.exit(result=None)

        application: Application[str | None] = Application(
            layout=Layout(
                HSplit(
                    [
                        Window(
                            FormattedTextControl(self._strip),
                            height=lambda: len(self.status.todos) if self.status.expanded else 1,
                        ),
                        Window(BufferControl(self.buffer), height=1),
                        Window(FormattedTextControl(self._status), height=1),
                    ]
                )
            ),
            key_bindings=keys,
            full_screen=False,
            erase_when_done=True,
        )
        return application

    def _strip(self) -> StyleAndTextTuples:
        width = self.console.width
        if self.status.expanded:
            return todo_list(self.status, self.theme)
        return todo_strip(self.status, self.theme, width)

    def _status(self) -> StyleAndTextTuples:
        return status_line(self.status, self.theme, self.console.width)

    def _completer(self) -> slash.Composer:
        return slash.Composer(
            slash.SlashCompleter(lambda: [s.id for s in self.services.library.all()]),
            slash.PathCompleter(self._paths),
        )

    def _paths(self) -> list[str]:
        root = self.services.workspace.root
        return [str(path.relative_to(root)) for path in self.services.workspace.walk()]


def _pending(events: Sequence[ChatEvent]) -> Pending:
    """What a turn stopped for, if it stopped.

    **The last `turn_closed`, not the first.** A resumed turn's `recorded` begins with the paused
    half, which already has a terminator on it saying `awaiting_permission` — so reading the first
    one meant a turn that had *just been answered and finished* still looked like it was waiting,
    and the card was drawn again. `hera_chats.Turn.close_reason` reads the last for the same
    reason; this now agrees with it.

    The cards are filtered the same way: only ones raised *after* that terminator are still open.
    """
    pending = Pending()
    last = next(
        (i for i in reversed(range(len(events))) if isinstance(events[i], TurnClosed)), None
    )
    if last is None:
        return pending
    closed = events[last]
    if not isinstance(closed, TurnClosed):  # pragma: no cover - narrowed by the search above
        return pending
    if closed.reason not in {"awaiting_permission", "awaiting_answer"}:
        return pending

    # Everything since the previous terminator. A turn that suspended twice has two paused halves
    # in it, and only the newest one is unanswered.
    previous = next(
        (i for i in reversed(range(last)) if isinstance(events[i], TurnClosed)),
        -1,
    )
    recent = events[previous + 1 : last]
    pending.permissions = [e for e in recent if isinstance(e, PermissionRequired)]
    pending.questions = [e for e in recent if isinstance(e, AnswerRequired)]
    return pending


_HELP = """  ⏎ send   ⇧⏎ newline   ^T todos   ^C stop or quit
  /help  /skills  /todos  /clear  /quit      /<skill> to use one
  @path completes a file from the working tree"""


def _plain(parts: StyleAndTextTuples) -> Text:
    """prompt_toolkit's formatted text as something rich can print.

    The dock and the header share their composition — one place decides what the header says — and
    only the *output* differs, because one is pinned and the other goes into scrollback.
    """
    text = Text()
    # A fragment is `(style, text)` or `(style, text, handler)` -- the third element is a mouse
    # handler, which scrollback has no use for. Unpacked by index rather than by shape so a
    # clickable fragment does not become a crash.
    for fragment in parts:
        text.append(fragment[1], style=fragment[0] or None)
    return text


def _styled(text: str, theme: Theme, meaning: Meaning) -> Text:
    return Text(text, style=theme.style(meaning))
