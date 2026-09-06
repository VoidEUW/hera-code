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

- **It can do work.** `hera_code_mcp` — the MCP server hera-code *is* — mounted in-process as
  `code`: `read`, `write`, `edit`, `glob`, `grep`, `bash` and `ask`. Every path goes through one
  containment guard, with symlinks resolved before they are compared.
- `hera_code_workspace`: root discovery, branch and dirty count, `.gitignore`-aware walks, and the
  `AGENT.md` / `AGENTS.md` / `CLAUDE.md` lookup — all three, read every turn, so a file edited
  mid-session is followed by the next one.
- The default permission policy, and `--yes`
  ([ADR 11](docs/adr/0011-the-default-policy-and-what-ask-means-with-nobody-there.md)): reads run
  without a card, changes ask, and anything outside the working tree is denied outright — which
  `--yes` cannot reach, because containment is an invariant rather than a preference.
- **A turn runs end to end.** `hera-code init` seeds the shared `~/.hera` (mind, skills,
  `mcp.json`) and hera-code's own `~/.hera/code`; `hera-code check` reports whether they are
  usable without changing anything; `hera-code -p "…"` sends one turn to a configured endpoint and
  prints the answer as plain text.
- `~/.hera/code/config.toml`, written mode 600 because it holds an API key. Seeded once from
  hera's own endpoints if it has any and from `HERA_PROVIDER_*` otherwise, and the file wins
  afterwards.
- A `coding` profile carrying the register as three behaviour traits, and the working tree
  composed into `SLOT_PROJECT`. No mind region is written: the mind is shared with hera.
- Alembic, owning the sessions schema at `~/.hera/code/sessions.sqlite3` — its own database
  rather than a table in hera's, because a coding agent writes a turn every few seconds.
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
