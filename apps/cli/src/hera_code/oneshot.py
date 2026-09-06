"""`hera-code -p "…"` — one turn, printed, no terminal.

The milestone's deliverable: the whole turn loop with none of the rendering, so a bug found once
the terminal exists has an unambiguous answer to *is this the loop or the drawing*. It is also
what CI drives and what a script uses.

**Plain text, always.** No dock, no colour, no motion — stdout here is usually a pipe, and an
escape code in a pipe is the failure mode ADR 3 says this design is most exposed to. There is no
`isatty` check in this module because there is nothing here that would draw differently either
way; that is the point of keeping it separate from the terminal rather than a flag inside it.

**Thinking is not printed.** It is not the answer, and a pipe wants the answer.

**A suspended turn is not an allow.** A turn that stops on a permission card or a question has
nobody to answer it here, so it exits :data:`SUSPENDED` and says which call is waiting. Silently
running the call instead would be the one failure a person could not detect from the output.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hera_chats import AnswerRequired, PermissionRequired, TurnClosed
from hera_code import session as sessions
from hera_code.wiring import Services
from hera_providers import TextDelta

COMPLETED = 0
FAILED = 1
SUSPENDED = 4
"""The turn stopped waiting for a person, and there is none.

Its own code rather than :data:`FAILED`, because a script should be able to tell *the model asked
for permission* from *the endpoint is down*. The first is answerable by re-running with `--yes` or
in the terminal; the second is not.
"""


async def run(services: Services, prompt: str, *, root: Path | None = None) -> int:
    """Run one turn against the configured endpoint and print the answer.

    Returns the exit code rather than calling ``sys.exit``, so it is testable.
    """
    with services.database.session() as db:
        chat = sessions.open_session(db, services)
        exchange = sessions.begin(db, services, chat, prompt, root=root)

        closed: TurnClosed | None = None
        waiting: list[str] = []
        async for event in sessions.run(db, exchange):
            if isinstance(event, TextDelta):
                # Written as it arrives rather than collected and printed at the end: a turn that
                # takes two minutes should show that it is working, and a pipe is free to buffer.
                sys.stdout.write(event.text)
                sys.stdout.flush()
            elif isinstance(event, PermissionRequired):
                waiting.append(f"{event.tool} needs permission — {event.reason or 'no rule'}")
            elif isinstance(event, AnswerRequired):
                waiting.append(f"{event.tool} asked: {event.question}")
            elif isinstance(event, TurnClosed):
                closed = event

        if sys.stdout.isatty():
            # A trailing newline so the shell prompt does not land on the last word. Skipped when
            # piped, where a stray newline is somebody else's parsing problem.
            sys.stdout.write("\n")
            sys.stdout.flush()

        return _code(closed, waiting)


def _code(closed: TurnClosed | None, waiting: list[str]) -> int:
    """What the exit code says, and what stderr says beside it.

    ``closed is None`` means the stream ended without a terminator, which `hera_chats` does not do
    — every path through `Turn.stream` closes the turn. Treated as a failure rather than a success
    because an absent terminator means something went wrong in a way nothing else reported.
    """
    if closed is None:
        print("the turn ended without closing — nothing was recorded", file=sys.stderr)
        return FAILED

    if closed.reason in {"awaiting_permission", "awaiting_answer"}:
        for line in waiting:
            print(line, file=sys.stderr)
        print(
            "the turn is waiting for a person and there is none here. "
            "Run it in the terminal, or re-run with --yes to allow the calls it asked for.",
            file=sys.stderr,
        )
        return SUSPENDED

    if closed.reason == "failed":
        print(closed.error or "the turn failed", file=sys.stderr)
        return FAILED

    if closed.reason == "cancelled":
        print("the turn was interrupted", file=sys.stderr)
        return FAILED

    if closed.reason == "max_iterations":
        # Not a failure. The wrap-up round means she answered with what she had, and that answer
        # is on stdout -- so the exit code says completed and stderr says why it was short.
        print(
            f"stopped after {closed.iterations} rounds of tool calls and answered with what it had",
            file=sys.stderr,
        )

    return COMPLETED
