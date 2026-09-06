"""Digests for the vendored packages, and the table in ``packages/VENDOR.md`` that records them.

A vendored package is a *copy*, not a fork — ADR 1. The only way that claim stays true is if
editing one is a failing build, so ``tests/test_vendor.py`` recomputes what is below and compares
it against the file.

One digest per package rather than one per file, because the table is meant to be read: a
person refreshing ``hera_tools`` wants one line to change, and a reviewer wants to see that
nothing else did. The digest covers every file in the package, so any edit moves it.

    uv run python -m tools.vendor_digest            # print the table
    uv run python -m tools.vendor_digest --write    # rewrite it in packages/VENDOR.md
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
VENDOR_FILE = PACKAGES / "VENDOR.md"

VENDORED = (
    "hera_home",
    "hera_storage",
    "hera_prompts",
    "hera_providers",
    "hera_permissions",
    "hera_tools",
    "hera_skillsets",
    "hera_profiles",
    "hera_chats",
)
"""The copies, in dependency order — which is also the order they are worth reading in.

Written out rather than derived from "everything not named ``hera_code_*``", because the point of
the list is to be the thing a new directory has to be added to deliberately.
"""

_ROW = re.compile(
    r"^\|\s*`(?P<package>hera_[a-z_]+)`\s*\|"
    r"\s*(?P<version>[^|]+?)\s*\|"
    r"\s*(?P<files>\d+)\s*\|"
    r"\s*`(?P<digest>[0-9a-f]{64})`\s*\|"
    r"\s*(?P<patched>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)

SKIP = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}


def files_of(package: Path) -> list[Path]:
    """Every file in a package, sorted, with tool caches left out.

    Caches are excluded rather than merely gitignored: a digest that changed because somebody ran
    the tests would be a digest nobody trusts, and a check nobody trusts gets deleted.
    """
    return sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and not (SKIP & set(path.relative_to(package).parts))
    )


def tree_digest(package: Path) -> str:
    """SHA-256 over the sorted ``path\\0sha256`` lines of every file in the package.

    The path is in the hash as well as the content, so moving a file changes the digest even
    when nothing inside it did.
    """
    lines = [
        f"{path.relative_to(package).as_posix()}\0{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in files_of(package)
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def declared_version(package: Path) -> str:
    with (package / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    version = data["project"]["version"]
    return str(version)


def measured() -> list[tuple[str, str, int, str]]:
    """``(package, version, file count, digest)`` for each vendored copy, in the listed order."""
    rows = []
    for name in VENDORED:
        package = PACKAGES / name
        rows.append((name, declared_version(package), len(files_of(package)), tree_digest(package)))
    return rows


def recorded(text: str) -> dict[str, tuple[str, int, str, str]]:
    """What ``VENDOR.md`` says, keyed by package: version, file count, digest, patched."""
    return {
        match["package"]: (
            match["version"],
            int(match["files"]),
            match["digest"],
            match["patched"],
        )
        for match in _ROW.finditer(text)
    }


def table() -> str:
    header = "| Package | Version | Files | Tree digest | Patched |\n|---|---|---|---|---|\n"
    rows = "".join(
        f"| `{name}` | {version} | {count} | `{digest}` | no |\n"
        for name, version, count, digest in measured()
    )
    return header + rows


def write() -> int:
    """Replace the table in ``VENDOR.md``, keeping the prose around it and the Patched column."""
    text = VENDOR_FILE.read_text()
    start = text.index("| Package | Version | Files | Tree digest | Patched |")
    end = len(text)
    for offset, line in enumerate(text[start:].splitlines(keepends=True)):
        del offset
        if not line.startswith("|"):
            end = start + text[start:].index(line)
            break
    VENDOR_FILE.write_text(text[:start] + table() + text[end:])
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vendor_digest", description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the table in VENDOR.md")
    args = parser.parse_args(argv)
    if args.write:
        return write()
    sys.stdout.write(table())
    return 0


if __name__ == "__main__":  # pragma: no cover - a script entry point
    raise SystemExit(main())
