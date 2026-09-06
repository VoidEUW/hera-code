"""hera-code — the application.

The only layer that knows every other one exists. It reads the settings, seeds ``~/.hera`` and
``~/.hera/code``, builds the provider from a registered endpoint, mounts ``hera_code_mcp`` into
``hera_tools``, composes the working tree and the todo list into the prompt's project slot, hands
the lot to ``hera_chats.TurnOrchestrator``, and draws what comes back in a terminal.

Everything below it is a library that could be used by something else. This is the thing that
could not.

The version is declared in ``pyproject.toml`` and read back from packaging rather than repeated
here, so ``--version`` and a release tag cannot disagree — ``release.yml`` refuses a tag that does
not match the file.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hera-code")
except PackageNotFoundError:  # pragma: no cover - only when running from a source tree uninstalled
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
