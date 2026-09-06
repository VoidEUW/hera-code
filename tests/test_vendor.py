"""A vendored package is a copy, and the only way that claim survives is if editing one fails.

``packages/VENDOR.md`` says nine packages are byte-identical to hera's at a named commit. That is
the sentence this file makes true. Without it the claim decays the first time somebody fixes a
typo in a docstring, and the decay is invisible until the next refresh throws the fix away.

The check is a digest per package rather than per file, so the table stays readable — see
``tools.vendor_digest``.
"""

from __future__ import annotations

import pytest

from tools.vendor_digest import (
    PACKAGES,
    VENDOR_FILE,
    VENDORED,
    declared_version,
    files_of,
    measured,
    recorded,
    tree_digest,
)


@pytest.fixture(scope="module")
def documented() -> dict[str, tuple[str, int, str, str]]:
    return recorded(VENDOR_FILE.read_text())


@pytest.mark.parametrize("name", VENDORED)
def test_the_copy_matches_what_vendor_md_recorded(
    name: str, documented: dict[str, tuple[str, int, str, str]]
) -> None:
    """If this fails: either revert the edit, or refresh the table and say why in VENDOR.md.

    uv run python -m tools.vendor_digest --write
    """
    assert name in documented, f"{name} is vendored but has no row in packages/VENDOR.md"
    version, count, digest, _ = documented[name]
    package = PACKAGES / name
    assert declared_version(package) == version
    assert len(files_of(package)) == count
    assert tree_digest(package) == digest


def test_every_documented_package_still_exists(
    documented: dict[str, tuple[str, int, str, str]],
) -> None:
    """A row for a directory that is gone is a row nobody is checking."""
    assert set(documented) == set(VENDORED)


def test_the_table_is_in_the_listed_order(documented: dict[str, tuple[str, int, str, str]]) -> None:
    """Dependency order, which is also the order the packages are worth reading in."""
    assert list(documented) == list(VENDORED)


def test_no_copy_claims_to_be_patched(
    documented: dict[str, tuple[str, int, str, str]],
) -> None:
    """*There are no patches* is a claim VENDOR.md makes. This is what keeps it honest.

    A patch is allowed — it is recorded in the table with its reason. This test failing means
    somebody wrote one down, at which point the *other* half of the promise applies: it goes
    upstream, and the copy is refreshed rather than carried.
    """
    patched = [name for name, (_, _, _, mark) in documented.items() if mark != "no"]
    assert not patched, f"recorded patches, which VENDOR.md says should not exist: {patched}"


def test_hera_mcp_is_not_vendored() -> None:
    """The server *hera* is. hera-code has its own, and mounting hers would give a coding agent
    ``remember``, ``forget`` and a chat scratchpad it has no business having."""
    assert not (PACKAGES / "hera_mcp").exists()


def test_the_generated_table_round_trips() -> None:
    """What ``--write`` would produce is what is already there, so the tool and the file agree."""
    documented = recorded(VENDOR_FILE.read_text())
    for name, version, count, digest in measured():
        assert documented[name] == (version, count, digest, "no")
