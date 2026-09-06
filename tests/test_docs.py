"""Guards on the documentation, because a map that is wrong is worse than no map.

`CLAUDE.md` exists to route somebody — a person or an agent — to the document that answers their
question. Every one of these checks is about a link that could rot silently: an ADR written and
never indexed, a package created and never described, a version document nobody points at.

None of this checks whether a document is *good*. It checks that the ones that claim to be
complete are, which is the only part a test can hold.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ADRS = DOCS / "adr"
VERSIONS = DOCS / "versions"
PACKAGES = ROOT / "packages"

REQUIRED = (
    "CLAUDE.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "README.md",
    "docs/status.md",
    "docs/tui.md",
    "docs/tooling.md",
    "docs/adr/README.md",
    "docs/versions/README.md",
    "packages/VENDOR.md",
)
"""The documents `CLAUDE.md` routes to. A missing one is a dead link in the first file read."""


def _adrs() -> list[Path]:
    return sorted(p for p in ADRS.glob("[0-9]*.md") if p.name != "README.md")


def _packages() -> list[Path]:
    return sorted(p for p in PACKAGES.iterdir() if (p / "pyproject.toml").is_file())


@pytest.mark.parametrize("relative", REQUIRED)
def test_the_documents_claude_md_routes_to_exist(relative: str) -> None:
    assert (ROOT / relative).is_file(), f"{relative} is routed to and does not exist"


def test_every_adr_is_in_the_index() -> None:
    """An ADR nobody links to is one nobody reads, which is the same as not writing it."""
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    missing = [adr.name for adr in _adrs() if adr.name not in index]
    assert not missing, f"add to docs/adr/README.md: {missing}"


def test_every_indexed_adr_exists() -> None:
    """The other direction: a link in the index that goes nowhere."""
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"\((\d{4}-[a-z0-9-]+\.md)\)", index))
    missing = sorted(name for name in linked if not (ADRS / name).is_file())
    assert not missing, f"docs/adr/README.md links to files that do not exist: {missing}"


def test_adrs_are_numbered_without_gaps() -> None:
    """A gap means a record was deleted, and a decision record is never deleted -- it is
    superseded, which leaves the file in place and adds a note to it."""
    numbers = [int(adr.name[:4]) for adr in _adrs()]
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"numbering has a gap or a repeat: {numbers}"
    )


def test_every_version_document_is_in_the_index() -> None:
    index = (VERSIONS / "README.md").read_text(encoding="utf-8")
    missing = [
        document.name for document in sorted(VERSIONS.glob("v*.md")) if document.name not in index
    ]
    assert not missing, f"add to docs/versions/README.md: {missing}"


@pytest.mark.parametrize("package", [p.name for p in _packages()])
def test_every_package_has_a_readme(package: str) -> None:
    """`pyproject.toml` names it as the long description, so a missing one fails the build --
    but an empty one does not, and this is the check for that."""
    readme = PACKAGES / package / "README.md"
    assert readme.is_file(), f"{package} has no README.md"
    assert len(readme.read_text(encoding="utf-8").strip()) > 200, (
        f"{package}/README.md is a stub. Say what it owns and what it never will."
    )


def test_architecture_describes_every_package() -> None:
    """A package the architecture document does not mention is one nobody agreed to."""
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    missing = [package.name for package in _packages() if package.name not in architecture]
    assert not missing, f"add to ARCHITECTURE.md: {missing}"


def test_claude_md_stays_a_map() -> None:
    """The predecessor of this file in hera grew to 98 KB and stopped being readable.

    The ceiling is arbitrary and that is fine -- its job is to fail while the fix is still
    "move this section into docs/", rather than after the file has become a changelog.
    """
    size = (ROOT / "CLAUDE.md").stat().st_size
    assert size < 16_384, (
        f"CLAUDE.md is {size} bytes. It is a map, not a changelog -- move a section into docs/."
    )
