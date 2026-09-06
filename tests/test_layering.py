"""The layering rule from ARCHITECTURE.md, enforced.

Nothing in a uv workspace physically stops one package from importing another, so the rule that
dependencies point downwards is checked here instead: every `hera_*` import inside a package's
source tree must appear in that package's allow-list below.

Adding an entry to `ALLOWED` is a deliberate act. If a package needs something from a package
above it, the dependency is wrong, not this table.

**Nine of these packages are vendored copies of hera's** (`packages/VENDOR.md`), and their rows
are hera's rows unchanged. That is not laziness — it is the check that the vendoring is honest.
A copy whose allow-list had to be widened here would be a copy that is no longer the same
package, and `test_vendor.py` would already have caught the edit that did it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
APPLICATION = "hera_code"

ALLOWED: dict[str, frozenset[str]] = {
    # -- vendored from hera, with hera's own rows --------------------------------------------
    #
    # Foundation. The first two are domain-free by contract: they must work unchanged in a
    # project that has nothing to do with Hera, so they import nothing of ours -- not even each
    # other. hera-code is the unrelated project that claim was always about, and these two empty
    # sets are the only place it gets tested rather than asserted.
    "hera_storage": frozenset(),
    "hera_prompts": frozenset(),
    # hera_home is not domain-free -- it says the word "hera" and knows the shape of ~/.hera --
    # but it is below everything, depends on nothing, and answers one question.
    "hera_home": frozenset(),
    # The model boundary and pure policy. Neither touches persistence.
    "hera_providers": frozenset(),
    "hera_permissions": frozenset(),
    # Capability layer. hera_tools mounts whatever in-process server it is handed and does not
    # know that hera_code_mcp exists; the application is what puts the two together.
    "hera_tools": frozenset({"hera_home", "hera_permissions"}),
    "hera_skillsets": frozenset({"hera_home", "hera_storage"}),
    # Assembly layer.
    "hera_profiles": frozenset({"hera_home", "hera_storage", "hera_prompts"}),
    # Orchestration. The turn loop, reused unchanged -- ADR 5.
    "hera_chats": frozenset(
        {
            "hera_home",
            "hera_storage",
            "hera_prompts",
            "hera_providers",
            "hera_permissions",
            "hera_tools",
            "hera_skillsets",
            "hera_profiles",
        }
    ),
    # -- hera-code's own ---------------------------------------------------------------------
    #
    # The paths package, mirroring hera_home one layer up: it answers where ~/.hera/code and a
    # working tree's .hera are, and hera_home answers for everything shared.
    "hera_code_home": frozenset({"hera_home"}),
    # The server hera-code *is*. Empty for the reason hera_mcp's is empty: it is entirely about
    # hera-code, but what it needs arrives as a port, so it imports nothing of ours. That is
    # what makes it servable over a transport in v0.3.0 rather than only in-process.
    "hera_code_mcp": frozenset(),
    # The working tree, the todo list, the shadow tree. Each knows where its files are and
    # nothing else -- no model, no turn, no tool.
    "hera_code_workspace": frozenset({"hera_code_home"}),
    "hera_code_todos": frozenset({"hera_code_home"}),
    "hera_code_shadow": frozenset({"hera_code_home"}),
    # The graph is the one that persists, so it is the one that gets hera_storage.
    "hera_code_graph": frozenset({"hera_code_home", "hera_storage"}),
}


def _packages() -> list[str]:
    if not PACKAGES.is_dir():
        return []
    return sorted(p.name for p in PACKAGES.iterdir() if (p / "pyproject.toml").is_file())


def _hera_imports(source: Path) -> set[str]:
    """Every top-level `hera_*` module name imported by one file."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return {name for name in found if name.startswith("hera")}


def test_every_package_has_an_allow_list() -> None:
    """A new package must declare where it sits before its imports can be checked."""
    undeclared = set(_packages()) - set(ALLOWED)
    assert not undeclared, (
        f"{sorted(undeclared)} have no entry in ALLOWED. Add one, and update ARCHITECTURE.md."
    )


@pytest.mark.parametrize("package", _packages())
def test_imports_point_downwards(package: str) -> None:
    permitted = ALLOWED[package] | {package}
    offences: list[str] = []

    for source in sorted((PACKAGES / package / "src").rglob("*.py")):
        for imported in sorted(_hera_imports(source)):
            if imported not in permitted:
                offences.append(f"{source.relative_to(ROOT)} imports {imported}")

    assert not offences, "\n".join(
        [f"{package} may import {sorted(permitted)} and nothing else:", *offences]
    )


@pytest.mark.parametrize("package", _packages())
def test_no_package_imports_the_application(package: str) -> None:
    """apps/cli wires the packages together; a package that knows about it is inverted."""
    offences = [
        str(source.relative_to(ROOT))
        for source in sorted((PACKAGES / package / "src").rglob("*.py"))
        if APPLICATION in _hera_imports(source)
    ]
    assert not offences, f"{package} imports the application layer: {offences}"


@pytest.mark.parametrize("package", ["hera_storage", "hera_prompts", "hera_code_mcp"])
def test_the_packages_that_import_nothing_of_ours_still_import_nothing(package: str) -> None:
    """Stated separately from the table because it is the claim, not a consequence of one.

    The first two are hera's promise that they are liftable into an unrelated project; this
    repository *is* that project, so an empty set here is the proof. The third is hera-code's
    own promise that its MCP server can be served over any transport, which stops being true
    the moment it reaches for something in-process.
    """
    assert ALLOWED[package] == frozenset()
