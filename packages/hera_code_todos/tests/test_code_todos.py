"""The run's red line, and the promise it has not kept yet.

A stub package: it lands in v0.1.0 M4. This test exists so that the workspace resolves and
CI is green from the first push, and so that the contract in the module docstring is somewhere
a failure can point at.
"""

from __future__ import annotations

import hera_code_todos


def test_the_package_imports() -> None:
    assert hera_code_todos.__doc__


def test_it_declares_what_it_exports() -> None:
    """``__all__`` is the public surface. Empty is a valid answer; missing is not."""
    assert isinstance(hera_code_todos.__all__, list)
