# Changelog

Written per release, for somebody who was not here — not generated per commit. Past tense,
append-only.

The three documents this is easy to be confused with are separated in
[`docs/versions/README.md`](docs/versions/README.md): a version document is the *plan* and is
frozen when its tag is cut, [`docs/status.md`](docs/status.md) is the *present*, and this is the
*past*.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning is
[semantic](https://semver.org/) — a tag is the only thing that ships
([ADR 6](docs/adr/0006-github-flow-and-milestones-are-the-plan.md)).

## [Unreleased]

### Added

- The repository: a uv workspace with nine of hera's packages vendored byte-identically
  (`packages/VENDOR.md`), six packages of hera-code's own, and the application at `apps/cli`.
- `hera_code_home` — the paths under `~/.hera/code` and inside a working tree's `.hera`.
- `hera-code --version`. Every other verb prints what it is waiting on and exits `3`.
- Four meta-tests: `test_layering.py` (imports point downwards, and the two foundation packages
  import nothing of ours), `test_workspace.py` (mypy, coverage and `[tool.uv.sources]` cover every
  member), `test_docs.py` (no unindexed ADR, no dead link, no gap in the numbering) and
  `test_vendor.py` (a vendored copy still matches its recorded digest).
- Ten architecture decision records, `ARCHITECTURE.md`, `docs/tui.md`, `docs/tooling.md`,
  `docs/status.md`, and version documents for v0.1.0 through v0.3.0.

Nothing is released yet. See [`docs/status.md`](docs/status.md).
