"""``hera-code`` on the command line.

Four verbs, no framework. ``argparse`` is in the standard library, this is not a general-purpose
tool, and a dependency whose value is nicer ``--help`` output is not worth a line in the lockfile.
The shape is hera's ``hera_core.cli``, deliberately — two applications that disagree about how a
CLI is built are two things to remember.

``run`` is the default: typing ``hera-code`` with no verb starts the terminal, because that is what
a person means every time but the first. Its options therefore hang on the top-level parser as
well, since a default that only works when you type the thing it is a default for is not a default.

**Nothing here prints a traceback at a person.** A configuration problem, a data directory from a
newer build and a missing endpoint are all things somebody has to *do* something about, and a
stack trace buries the one line that says what.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from hera_code import __version__

if TYPE_CHECKING:
    # Type-only, so `--version` and `--help` do not pay for importing SQLAlchemy and httpx.
    from hera_code.boot import Prepared
    from hera_code.wiring import Services

NOT_YET = 3
"""Exit code for a verb that is planned and not built.

Not ``1``, because a script should be able to tell *this failed* from *this is not here yet*, and
not ``0``, because nothing happened.
"""

FAILED = 1
BAD_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a status code rather than calling ``sys.exit``, so it is testable."""
    parser = _parser()
    args = parser.parse_args(argv)
    _quieten(verbose=bool(getattr(args, "verbose", False)))
    try:
        return _run(args)
    except _Reportable as exc:
        # Not a traceback. Every one of these is a person being told what to do, and the message
        # is the whole value of the exception.
        print(str(exc), file=sys.stderr)
        return FAILED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hera-code", description="A terminal coding agent.")
    parser.add_argument("--version", action="version", version=f"hera-code {__version__}")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show the library logging that is normally hidden",
    )
    _session_options(parser)

    commands = parser.add_subparsers(dest="command")
    _session_options(commands.add_parser("run", help="start the terminal (the default)"))
    commands.add_parser("init", help="prepare ~/.hera and ~/.hera/code without starting anything")
    commands.add_parser("check", help="report whether the data directories are usable")
    return parser


def _session_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--print",
        dest="prompt",
        default=None,
        metavar="TEXT",
        help="run one turn, print the answer, exit — no terminal",
    )
    parser.add_argument(
        "--yes",
        dest="yes",
        action="store_true",
        help="allow the calls that would have asked. Cannot reach what is denied outright",
    )
    parser.add_argument(
        "--continue", dest="resume_last", action="store_true", help="resume the last session"
    )
    parser.add_argument(
        "--resume", dest="session", default=None, metavar="ID", help="resume a session"
    )


def _run(args: argparse.Namespace) -> int:
    command = args.command or "run"
    if command == "init":
        return _init()
    if command == "check":
        return _check()
    if getattr(args, "prompt", None):
        return _one_shot(str(args.prompt), yes=bool(getattr(args, "yes", False)))

    print(
        f"hera-code {__version__}: the terminal is not built yet — it lands in v0.1.0 M3. "
        'Until then, `hera-code -p "…"` runs one turn and prints the answer.',
        file=sys.stderr,
    )
    return NOT_YET


def _init() -> int:
    """Seed both data directories and say what was created.

    Idempotent. A second run reports that there was nothing to do, which is the sentence that
    tells somebody their install is already fine.
    """
    services = _services()
    try:
        report = _prepare(services)
    finally:
        services.database.dispose()

    if not report.anything:
        print("Everything was already in place. Nothing was created.")
        return 0

    for path in report.created:
        print(f"created  {path}")
    if report.migrated:
        print("migrated sessions.sqlite3 to the current schema")
    print(
        "\n`<your repo>/.hera` is yours to commit or ignore — "
        "hera-code will not touch your .gitignore."
    )
    return 0


def _check() -> int:
    """Look and report; create nothing. Exit 0 when usable, 1 when not."""
    from hera_code.check import inspect

    report = inspect()
    print(report.render())
    if report.usable:
        return 0
    print("\nSomething above needs attention before a turn can run.", file=sys.stderr)
    return FAILED


def _one_shot(prompt: str, *, yes: bool = False) -> int:
    from hera_code import oneshot

    services = _services()
    # Prepared before the first request rather than lazily: a person running `-p` on a fresh
    # machine should get a working turn, not a missing-table error from inside the loop.
    _prepare(services)

    async def go() -> int:
        # One `asyncio.run`, not two. Closing the provider in a second one tears down an httpx
        # client whose transport belongs to the loop that has already been closed, which surfaces
        # as `RuntimeError: Event loop is closed` on the way out of an otherwise successful turn.
        try:
            return await oneshot.run(services, prompt, root=Path.cwd(), yes=yes)
        finally:
            await services.aclose()

    return asyncio.run(go())


def _services() -> Services:
    """Assemble the application, turning a bad configuration into a sentence.

    Imported inside the function rather than at module scope: ``--version`` and ``--help`` should
    not pay for importing SQLAlchemy, alembic and httpx, and on a cold start that is most of the
    time a person waits.
    """
    from hera_code.config import ConfigError
    from hera_code.wiring import build_services

    try:
        return build_services()
    except ConfigError as exc:
        raise _Reportable(str(exc)) from exc


def _prepare(services: Services) -> Prepared:
    """Bring the data directories up to date, turning a database from the future into a sentence."""
    from hera_code.boot import DatabaseAhead, prepare

    try:
        return prepare(
            services.database,
            services.mind,
            owner_id=services.settings.owner_id,
            config=services.config,
        )
    except DatabaseAhead as exc:
        raise _Reportable(str(exc)) from exc


NOISY_LOGGERS = ("alembic", "sqlalchemy", "httpx", "httpcore", "mcp")
"""Libraries whose INFO output is not addressed to a person using hera-code.

**Alembic is the one that made this necessary.** It logs a line per autogenerate plugin at INFO,
so the first thing anybody saw on a fresh install was fourteen lines about
`alembic.autogenerate.schemas` before `created ~/.hera/mind`. hera can afford that because it
logs to a server's stderr; a terminal cannot, and neither can a pipe.

Quietened rather than disabled: `--verbose` puts them back, because somebody debugging a
migration wants exactly these lines.
"""


def _quieten(*, verbose: bool) -> None:
    """Set the logging up before anything logs.

    Called from :func:`main` immediately after parsing, which is the last moment before the first
    import that configures a handler of its own. A library that has already emitted at import
    time cannot be un-emitted, so the ordering here is the whole of it.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    # Set either way rather than returning early on `--verbose`. Returning left a logger that an
    # earlier call had quietened still quiet, so `--verbose` was a no-op in any process that had
    # already run without it -- which is every test, and would be a REPL or an embedding too.
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET if verbose else logging.WARNING)


class _Reportable(RuntimeError):
    """An error whose message is the whole point. Printed as one line, never as a traceback."""
