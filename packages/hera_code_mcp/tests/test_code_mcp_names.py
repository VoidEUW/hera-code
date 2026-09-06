"""The server hera-code is: what it offers, and what it says when a port is missing.

Two constants travel out of this package because two other packages have to agree with it without
importing it — `hera_tools` mounts a server under its own name, and `hera_chats` suspends a turn
on the asking tool's. A constant agreed on in two places is one that can disagree.

The rest is about the degradation story: a deployment with no ports still lists every tool, and
each one says why it cannot run rather than vanishing.
"""

from __future__ import annotations

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import hera_code_mcp
from hera_code_mcp import (
    ASK_KINDS,
    ASK_TOOL,
    BUILTIN_SERVER_NAME,
    TOOL_NAMES,
    build_server,
)


def test_the_server_names_itself() -> None:
    """`hera_tools` mounts a server under its own `name`, so the word is written once."""
    assert BUILTIN_SERVER_NAME == "code"
    assert build_server().name == "code"


def test_the_asking_tool_is_named_for_whoever_has_to_recognise_it() -> None:
    """`hera_chats` suspends a turn on this name and may not import this package."""
    assert ASK_TOOL == "ask"
    assert ASK_TOOL in TOOL_NAMES


def test_ask_has_a_closed_set_of_kinds() -> None:
    """In the tool's own schema, so there is nothing for the model to invent (hera's ADR 17)."""
    assert ASK_KINDS == ("unsure", "blocked", "choice")


async def test_every_declared_tool_is_registered() -> None:
    """`TOOL_NAMES` is what the seeded permission policy is written against.

    A tool registered but not listed gets no rule and falls through to `ask`; one listed but not
    registered gets a rule that matches nothing. Both are silent, which is why they are a test.
    """
    tools = await build_server().list_tools()

    assert {tool.name for tool in tools} == set(TOOL_NAMES)


async def test_every_tool_describes_itself_for_a_model() -> None:
    """Descriptions are prompt text — the model reads them and nothing else explains these."""
    for tool in await build_server().list_tools():
        assert tool.description, f"{tool.name} has no description"
        assert len(tool.description) > 80, f"{tool.name}'s description is too thin to be useful"


async def test_a_deployment_with_no_ports_still_lists_everything() -> None:
    """**The degradation story of ADR 4.** A model that cannot see `read` concludes it cannot read
    files and tells the person so, which is worse than a tool that says why."""
    tools = await build_server(files=None, shell=None).list_tools()

    assert len(tools) == len(TOOL_NAMES)


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("read", {"path": "a.py"}),
        ("write", {"path": "a.py", "text": "x"}),
        ("edit", {"path": "a.py", "find": "a", "replace": "b"}),
        ("glob", {"pattern": "*.py"}),
        ("grep", {"pattern": "x"}),
    ],
)
async def test_an_unwired_file_tool_says_why(tool: str, arguments: dict[str, str]) -> None:
    with pytest.raises(ToolError, match="no working tree"):
        await build_server().call_tool(tool, arguments)


async def test_an_unwired_shell_says_why() -> None:
    with pytest.raises(ToolError, match="no shell"):
        await build_server().call_tool("bash", {"command": "ls"})


async def test_ask_outside_a_turn_says_nobody_was_asked() -> None:
    """Reached only when this server is driven directly — over the v0.3.0 transport, or by a test.

    Inside a turn `hera_chats` recognises the name before dispatch and suspends. Saying so plainly
    beats returning something that looks like an answer nobody gave.
    """
    with pytest.raises(ToolError, match="not put to anybody"):
        await build_server().call_tool("ask", {"question": "which backend?"})


def test_it_exports_what_the_application_needs() -> None:
    assert {"ASK_TOOL", "BUILTIN_SERVER_NAME", "build_server", "Files", "Shell"} <= set(
        hera_code_mcp.__all__
    )


async def test_read_is_told_to_prefer_grep() -> None:
    """**The thing a coding agent gets wrong most expensively.**

    Reading a whole file to find one function spends context that the change itself will want. It
    is said in `read`'s own description rather than in a system prompt, because that is where a
    model is looking when it decides.
    """
    tools = await build_server().list_tools()
    read = next(tool for tool in tools if tool.name == "read")

    assert "grep" in (read.description or "")


async def test_a_tool_error_message_survives_to_the_model() -> None:
    """The distinction the whole error design rests on.

    The SDK passes a `ToolError`'s own message through and replaces every other exception with
    "Error executing tool <name>", so a crash cannot leak internals. Everything raised in this
    package is written to be read by a model, which means it has to be a `ToolError` — this is
    what proves the message is not generalised away on the path out.
    """
    with pytest.raises(ToolError) as caught:
        await build_server().call_tool("read", {"path": "a.py"})

    assert "there is no working tree in this deployment" in str(caught.value)
