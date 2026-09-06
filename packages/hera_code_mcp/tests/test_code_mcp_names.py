"""The two constants that travel, and the import rule that lets them.

The server itself lands in v0.1.0 M2. These two names exist now because other packages are
written against them, and a constant agreed on in two places is one that can disagree.
"""

from __future__ import annotations

import hera_code_mcp
from hera_code_mcp import ASK_TOOL, BUILTIN_SERVER_NAME


def test_the_server_names_itself() -> None:
    """``hera_tools`` mounts a server under its own ``name``, so the word is written once."""
    assert BUILTIN_SERVER_NAME == "code"


def test_the_asking_tool_is_named_for_whoever_has_to_recognise_it() -> None:
    """``hera_chats`` suspends a turn on this name and may not import this package."""
    assert ASK_TOOL == "ask"


def test_it_declares_what_it_exports() -> None:
    assert set(hera_code_mcp.__all__) == {"ASK_TOOL", "BUILTIN_SERVER_NAME"}
