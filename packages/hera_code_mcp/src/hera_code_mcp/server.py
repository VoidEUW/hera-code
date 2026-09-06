"""hera-code's capabilities, as an MCP server like any other.

`read`, `edit` and `bash` are not privileged. They are registered on a real
:class:`~mcp.server.mcpserver.MCPServer`, reached over an in-memory transport by the same client
that reaches a filesystem server, listed in the same catalogue, and checked by the same permission
policy. ADR 4 asked for that on the grounds that a special case here would have to be unpicked in
v0.3.0, when this server is exposed to hera — at which point the only change should be which
transport it is served over.

**The tool descriptions are prompt text.** The model reads them and nothing else explains what
these do, so they are written for it: short, imperative, and clear about when *not* to call. They
also carry the one thing a coding agent gets wrong most expensively — reading a whole file when a
`grep` would have answered — which is why `read` says so in its own description rather than
leaving it to a system prompt somewhere else.

**Failures raise ``ToolError`` and nothing else.** The SDK passes a `ToolError` message through to
the model as the content of a failed result, and replaces every other exception with "Error
executing tool <name>" so a crash cannot leak internals. Everything raised here is written to be
read by a model, so it has to be the kind that survives.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from hera_code_mcp.ports import Files, Shell

BUILTIN_SERVER_NAME = "code"
"""hera-code's tools are namespaced ``code__read``, ``code__edit``, ``code__bash``.

The name travels on the server object rather than being agreed on twice: ``hera_tools`` mounts
whatever it is handed under ``server.name``, so this constant is the only place the word is
written and renaming the server does not need the client's permission.
"""

ASK_TOOL = "ask"
"""The one tool here that is answered by a *person* rather than run.

Named as a constant because the layer that suspends the turn is ``hera_chats``, which does not
import this package and must not learn what its tools are. The application reads this and
configures ``ChatsSettings.asking_tools`` with the qualified name, so the string is written once
and travels rather than being agreed on twice.
"""

AskKind = Literal["unsure", "blocked", "choice"]
"""What sort of question is being asked, from a closed set.

Three occasions: something only they know (*unsure*), something that cannot go on until they
decide (*blocked*), or two readings of the request that lead somewhere genuinely different
(*choice*). Closed rather than free text, and in the tool's own input schema, so there is nothing
for the model to invent and nothing for the card to look up.

Inherited from hera's ADR 17 rather than re-derived. What that record found the hard way is that
an open vocabulary produces a label nobody can act on.
"""

ASK_KINDS: tuple[AskKind, ...] = ("unsure", "blocked", "choice")

TOOL_NAMES: tuple[str, ...] = (
    "read",
    "write",
    "edit",
    "glob",
    "grep",
    "bash",
    ASK_TOOL,
)
"""Every tool on this server, for whoever has to enumerate them — the seeded permission policy,
and the test that holds the policy and the server together."""

READ_LIMIT = 2_000
"""How many lines one `read` returns by default.

A ceiling rather than a preference. A model that reads a 40,000-line generated file has spent its
context window on something it will not use, and the failure is invisible: the answer that comes
out is worse and nothing says why. `offset` is how to see the rest, and saying `truncated` out
loud is what makes that discoverable.
"""

GREP_LIMIT = 100
"""How many matching lines one `grep` returns. Same reasoning as :data:`READ_LIMIT`: a search that
returns a thousand lines has replaced the answer with a haystack."""

GLOB_LIMIT = 200

BASH_TIMEOUT_S = 120.0
"""How long a command gets before it is killed.

Generous enough for a test suite and short enough that a hung process does not hold a turn open
until the provider's own timeout. A command that needs longer is one a person should run.
"""


def build_server(
    *,
    files: Files | None = None,
    shell: Shell | None = None,
    version: str = "0.1.0",
) -> MCPServer:
    """Assemble the in-process server, wired to whichever ports this deployment has.

    Everything is optional. What is missing still appears in the catalogue and answers with a tool
    error saying it is unavailable — better than vanishing, because a model that cannot see `read`
    concludes it cannot read files and tells the person so.
    """
    server: MCPServer = MCPServer(BUILTIN_SERVER_NAME, title="hera-code", version=version)

    # -- the person -----------------------------------------------------------------------

    @server.tool(
        name=ASK_TOOL,
        title="Ask the person a question",
        description=(
            "Ask the person something and wait for their answer. This stops your turn: they see "
            "your question, type a reply, and you continue with it. Use it when being wrong "
            "would cost them real work — a fact only they have, two readings of the request that "
            "lead to different code, or something hard to undo. Ask only what changes what you "
            "build: not the name of a variable, but which backend, which endpoints, whether to "
            "extend what is there or replace it. Ask one question rather than a list, and do not "
            "use it to check in or to be reassured. If you can sensibly choose and say what you "
            "chose, do that instead. `kind` says what sort of question it is: `unsure` when you "
            "need a fact only they have, `blocked` when you cannot go on until they answer, "
            "`choice` when two readings are both sensible and they should pick."
        ),
    )
    async def ask(question: str, kind: AskKind = "unsure") -> str:
        del question, kind
        # Reached only when this server is driven directly -- over the transport v0.3.0 exposes,
        # or by a test. Inside a turn the question never gets here: `hera_chats` recognises the
        # name before dispatch and suspends. Saying so plainly beats returning something that
        # looks like an answer nobody gave.
        raise ToolError(
            "this question was not put to anybody: `ask` suspends a turn so a person can reply, "
            "and nothing here is running one"
        )

    # -- files ----------------------------------------------------------------------------

    @server.tool(
        name="read",
        title="Read a file",
        description=(
            "Read a file from the working tree, with line numbers. Use `offset` and `limit` to "
            "read part of a large one; you will be told when there is more. Prefer `grep` when "
            "you are looking for something and only need to know where it is — reading a whole "
            "file to find one function spends context you will want later for the change itself."
        ),
    )
    async def read(path: str, offset: int = 0, limit: int = 0) -> str:
        if files is None:
            raise ToolError("there is no working tree in this deployment")
        with _readable(f"read {path}"):
            found = await files.read(path, offset=offset, limit=limit or READ_LIMIT)
        body = found.text
        if found.truncated:
            body += (
                f"\n\n[{found.path} continues past line {offset + found.lines}. "
                f"Read on with offset={offset + found.lines}.]"
            )
        if found.note:
            # Delivered with the file rather than fetched (ADR 9), behind a marker so a caller
            # that does not care can ignore the tail.
            body += f"\n\n--- what you worked out about this file before ---\n{found.note}"
        return body

    @server.tool(
        name="write",
        title="Write a file",
        description=(
            "Write a file whole, creating it and any missing directories. This replaces "
            "everything that was there. For a change to a file that already exists, use `edit` — "
            "it is cheaper and it cannot silently lose the parts you did not mean to touch."
        ),
    )
    async def write(path: str, text: str) -> str:
        if files is None:
            raise ToolError("there is no working tree in this deployment")
        with _readable(f"write {path}"):
            size = await files.write(path, text)
        return f"wrote {path} ({size} bytes)"

    @server.tool(
        name="edit",
        title="Replace a passage in a file",
        description=(
            "Replace one passage of a file. `find` must appear exactly once — include enough of "
            "the surrounding lines to make it unique, and keep the indentation exactly as it is "
            "in the file. If it matches nothing or matches several times you will be told which, "
            "and nothing is changed. To delete a passage, give an empty `replace`."
        ),
    )
    async def edit(path: str, find: str, replace: str) -> str:
        if files is None:
            raise ToolError("there is no working tree in this deployment")
        with _readable(f"edit {path}"):
            size = await files.edit(path, find, replace)
        return f"edited {path} ({size} bytes)"

    @server.tool(
        name="glob",
        title="Find files by name",
        description=(
            "Find files in the working tree whose path matches a glob — `src/**/*.py`, "
            "`**/test_*.py`. Newest first, so what is being worked on comes up first. Ignored "
            "directories and anything in .gitignore are skipped."
        ),
    )
    async def glob(pattern: str, limit: int = 0) -> str:
        if files is None:
            raise ToolError("there is no working tree in this deployment")
        with _readable(f"match {pattern}"):
            found = await files.glob(pattern, limit=limit or GLOB_LIMIT)
        if not found:
            return f"nothing matches {pattern}"
        return "\n".join(found)

    @server.tool(
        name="grep",
        title="Search file contents",
        description=(
            "Search the working tree for a regular expression and get the matching lines with "
            "their paths and line numbers. Narrow it with `path` (a directory) or `glob` (a file "
            "pattern). This is the first thing to reach for when you are looking for where "
            "something is — it answers in one call what several `read`s would."
        ),
    )
    async def grep(pattern: str, path: str = "", glob: str = "", limit: int = 0) -> str:
        if files is None:
            raise ToolError("there is no working tree in this deployment")
        with _readable(f"search for {pattern}"):
            found = await files.grep(pattern, path=path, glob=glob, limit=limit or GREP_LIMIT)
        if not found:
            return f"no line matches {pattern}"
        lines = [f"{match.path}:{match.line}: {match.text}" for match in found]
        if len(found) >= (limit or GREP_LIMIT):
            lines.append(f"[stopped at {len(found)} matches; narrow the search to see the rest]")
        return "\n".join(lines)

    # -- the shell ------------------------------------------------------------------------

    @server.tool(
        name="bash",
        title="Run a command",
        description=(
            "Run a shell command in the working tree and get its output and exit code. Use it to "
            "run the tests, a linter, or a build — the project's own instructions usually say "
            "which. A non-zero exit is an answer, not a failure: read it. Do not use it to read "
            "or edit files, which `read` and `edit` do better, and do not use it for anything "
            "that needs to still be running when the command returns."
        ),
    )
    async def bash(command: str, timeout_s: float = 0) -> str:
        if shell is None:
            raise ToolError("there is no shell in this deployment")
        with _readable("run that command"):
            ran = await shell.run(command, timeout_s=timeout_s or BASH_TIMEOUT_S)
        return _transcript(ran)

    return server


@contextmanager
def _readable(what: str) -> Iterator[None]:
    """Let whatever the adapter said reach the model, instead of the SDK's generic sentence.

    Without this the SDK replaces any exception that is not a `ToolError` with "Error executing
    tool read", which tells the model nothing to act on — and the adapter's refusals are the ones
    most worth reading: *that is outside the working tree*, *`find` matched three times*. Both
    have an obvious next move and neither survives being generalised.

    Broad on purpose, and it hides nothing: a `ToolError` already carries its own message and
    passes through untouched.
    """
    try:
        yield
    except ToolError:
        raise
    except Exception as cause:
        raise ToolError(f"could not {what}: {cause}") from cause


def _transcript(ran: object) -> str:
    """What a command did, as the model reads it.

    The exit code first, because it is the thing that decides what happens next and a model
    scanning a wall of output should not have to find it at the bottom.
    """
    from hera_code_mcp.ports import Ran

    if not isinstance(ran, Ran):  # pragma: no cover - a port returning the wrong thing
        raise ToolError("the shell returned something unusable")

    if ran.timed_out:
        head = f"timed out after {ran.duration_ms} ms and was killed"
    else:
        head = f"exit {ran.exit_code} in {ran.duration_ms} ms"

    parts = [head]
    if ran.stdout.strip():
        parts.append(f"--- stdout ---\n{ran.stdout.rstrip()}")
    if ran.stderr.strip():
        parts.append(f"--- stderr ---\n{ran.stderr.rstrip()}")
    if len(parts) == 1:
        parts.append("(no output)")
    return "\n".join(parts)
