"""Running a command in the working tree.

The application's side of :class:`hera_code_mcp.Shell`. Small, and every line of it is about one
of three things: not hanging, not filling the context window, and not lying about what happened.

**There is no sandbox.** ADR 11 says so plainly and `docs/tooling.md` § 5 records the friction:
`bash` is `ask` by default and every invocation costs a card, until v0.3.0 answers *where does
code run*. Until then, the card is the sandbox — so nothing here tries to be one. A half-sandbox
that filtered commands by pattern would be worse than none, because it would look like protection.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time

from hera_code_mcp import Ran
from hera_code_workspace import Workspace

MAX_OUTPUT_CHARS = 30_000
"""How much of a command's output survives.

**Truncated in the middle, not at the end.** The last lines of a failing test run are the ones
that matter — the summary, the assertion, the traceback's final frame — and cutting the tail is
how a tool turns a useful failure into a useless one. The head matters too, so both are kept and
the middle is what goes.
"""

KEEP_HEAD = 8_000
KEEP_TAIL = MAX_OUTPUT_CHARS - KEEP_HEAD

CHUNK = 8192
DRAIN_GRACE_S = 5.0
"""How long the readers get to finish after the process has gone. Bounded, because a grandchild
holding the pipe open would otherwise keep them waiting forever."""


class WorkingShell:
    """:class:`hera_code_mcp.Shell`, over a real subprocess."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    async def run(self, command: str, *, timeout_s: float = 0) -> Ran:
        started = time.monotonic()
        # A new process *group*, so a timeout can kill what the shell started rather than only
        # the shell. `pytest` that spawned a server is the ordinary case, and killing the shell
        # alone leaves it running and holding a port.
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=self._workspace.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        # **Drained into our own buffers rather than through `communicate()`**, and that is the
        # whole reason this function is shaped like this. `communicate()` accumulates internally
        # and `wait_for` cancels it on a timeout, which throws away everything it had read — so a
        # command that printed three failures and then hung reported no output at all. Reading
        # incrementally means a timeout keeps what already arrived, which is the case the timeout
        # exists to survive.
        out: list[bytes] = []
        err: list[bytes] = []
        readers = [
            asyncio.create_task(_drain(process.stdout, out)),
            asyncio.create_task(_drain(process.stderr, err)),
        ]

        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_s or None)
        except TimeoutError:
            timed_out = True
            await _kill(process)
        finally:
            await _finish(readers)

        return Ran(
            command=command,
            # A killed process has no meaningful exit code of its own, and the sentinel says so
            # in the shell's own vocabulary rather than inventing one.
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=_trimmed(b"".join(out)),
            stderr=_trimmed(b"".join(err)),
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=timed_out,
        )


async def _drain(stream: asyncio.StreamReader | None, into: list[bytes]) -> None:
    """Read one pipe until it closes, keeping everything.

    Cancelled at the end of the run, so it never has to decide when it is done — the process
    going away closes the pipe, which is the only honest signal there is.
    """
    if stream is None:  # pragma: no cover - both pipes are always requested above
        return
    while True:
        chunk = await stream.read(CHUNK)
        if not chunk:
            return
        into.append(chunk)


async def _finish(readers: list[asyncio.Task[None]]) -> None:
    """Let the readers pick up what is still buffered, then stop them.

    Bounded by :data:`DRAIN_GRACE_S`: a grandchild that inherited the pipe and outlived the kill
    holds it open, and waiting on that forever would turn a timeout into a hang — which is the one
    thing a timeout may not do.
    """
    done, pending = await asyncio.wait(readers, timeout=DRAIN_GRACE_S)
    del done
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.wait(pending)


async def _kill(process: asyncio.subprocess.Process) -> None:
    """Stop a process group.

    `SIGKILL` on the group rather than `process.kill()`, which would signal the shell and leave
    its children — a `pytest` that spawned a server would keep running and keep its port.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    with contextlib.suppress(TimeoutError, ProcessLookupError):
        await asyncio.wait_for(process.wait(), timeout=DRAIN_GRACE_S)


def _trimmed(raw: bytes) -> str:
    """Output as the model reads it, cut in the middle if it is enormous."""
    text = raw.decode("utf-8", errors="replace")
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    dropped = len(text) - KEEP_HEAD - KEEP_TAIL
    cut = f"[... {dropped} characters cut from the middle ...]"
    return f"{text[:KEEP_HEAD]}\n\n{cut}\n\n{text[-KEEP_TAIL:]}"
