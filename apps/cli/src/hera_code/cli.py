"""``hera-code`` on the command line.

Four verbs, no framework. ``argparse`` is in the standard library, this is not a general-purpose
tool, and a dependency whose value is nicer ``--help`` output is not worth a line in the lockfile.
The shape is ``hera_core.cli``'s, deliberately — two applications that disagree about how a CLI is
built are two things to remember.

``run`` is the default: typing ``hera-code`` with no verb starts the terminal, because that is
what a person means every time but the first.

Only ``--version`` works today. The rest arrive in v0.1.0 M1 (``init``, ``check``, ``--print``)
and M2 (the terminal), and each prints what it is waiting on rather than a traceback — a verb
that exists and says "not yet" is a promise, and one that does not exist is a surprise.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from hera_code import __version__

NOT_YET = 3
"""Exit code for a verb that is planned and not built.

Not ``1``, because a script should be able to tell "this failed" from "this is not here yet",
and not ``0``, because nothing happened.
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a status code rather than calling ``sys.exit``, so it is testable."""
    parser = _parser()
    args = parser.parse_args(argv)
    return _run(args)


def _parser() -> argparse.ArgumentParser:
    """The verbs, and `run`'s options hung on the top-level parser as well as on `run`.

    ``run`` is the default verb, so ``hera-code -p "…"`` has to parse without it — a default
    that only works when you type the thing it is a default for is not a default. argparse has
    no built-in for that, so the options are declared once and added to both parsers, and
    ``_run`` reads them off whichever one matched.
    """
    parser = argparse.ArgumentParser(prog="hera-code", description="A terminal coding agent.")
    parser.add_argument("--version", action="version", version=f"hera-code {__version__}")
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
        "--continue", dest="resume_last", action="store_true", help="resume the last session"
    )
    parser.add_argument(
        "--resume", dest="session", default=None, metavar="ID", help="resume a session"
    )


def _run(args: argparse.Namespace) -> int:
    command = args.command or "run"
    waiting = {
        "run": "one-shot --print lands in v0.1.0 M1, the terminal in M3",
        "init": "seeding ~/.hera and ~/.hera/code lands in v0.1.0 M1",
        "check": "the data-directory check lands in v0.1.0 M1",
    }
    print(
        f"hera-code {__version__}: `{command}` is not built yet — {waiting[command]}.",
        file=sys.stderr,
    )
    return NOT_YET
