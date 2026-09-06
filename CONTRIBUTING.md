# Contributing

## Setup

```bash
git clone https://github.com/VoidEUW/hera-code.git
cd hera-code
uv sync --all-packages
```

One checkout, one sync. Every library is a workspace member under `packages/`, so an edit in one is
visible to the others immediately with no reinstall.

## The loop

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run coverage run -m pytest && uv run coverage report   # gate: 90 %
uv run pytest tests/                                      # the four meta-tests
```

`pre-commit install` runs the fast half of this before every commit, and the `commit-msg` hook
checks the message shape.

## Branching — GitHub Flow

`main` is always releasable and protected. Everything else is a short-lived branch off `main`:

| Prefix | For |
|---|---|
| `feat/` | new behaviour |
| `fix/` | a bug |
| `chore/` | tooling, dependencies, CI, a vendor refresh |
| `docs/` | documentation only |
| `refactor/` | structure, no behaviour change |
| `test/` · `perf/` · `ci/` · `build/` · `revert/` | as named |

Open a pull request, let CI run, squash-merge, delete the branch. No long-running branches, no
direct pushes to `main`, no merge commits — history stays linear.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat(todos): parse the four states`. The type drives the changelog — see
[CHANGELOG.md](CHANGELOG.md), which is written per release rather than generated per commit.

## Milestones are the plan

A version document in `docs/versions/` says what a version is *for* and is frozen when its tag is
cut. **The milestone and its issues are what stays current.** A plan in a file rots because
updating it is a separate act from doing the work; an issue is read at the moment it matters and
edited by whoever noticed it was wrong. [ADR 6](docs/adr/0006-github-flow-and-milestones-are-the-plan.md).

A milestone keeps its number even if what is in it changes. M4 means the todo list forever —
renumbering makes every commit message that says M4 wrong.

## Writing code here

- **Imports point downwards.** See the table in [ARCHITECTURE.md](ARCHITECTURE.md). A package
  importing from a package above it is a bug, and `tests/test_layering.py` fails on it.
- **Typed, strictly.** `mypy --strict` passes with no `# type: ignore` that lacks a reason on the
  same line. `from __future__ import annotations` at the top of every module.
- **Everything is English** — code, comments, docstrings, commit messages, terminal strings,
  prompts and stored content.
- **New table?** Prefix `__tablename__` with your package's prefix and add an Alembic revision in
  `apps/cli`. Cross-package references are bare `UUID` columns, never `ForeignKey`.
- **New model capability?** One new variant in the `hera_providers` event union, one branch where
  it is persisted, one renderer in `apps/cli/src/hera_code/tui`. If you are writing a parser, stop
  and check whether it should be a tool call instead.
- **New terminal component?** Read [`docs/tui.md`](docs/tui.md) first, and check which of the four
  colour meanings you are spending. A colour whose sentence you cannot say does not belong there.
- **Tests are not optional.** A package without a test for the behaviour you added does not reach
  90 % and CI fails. Model behaviour is tested against `hera_providers.FakeProvider`, never a live
  endpoint — anything needing a real one is marked `@pytest.mark.live` and stays out of CI.
- **Test module names are unique across the whole workspace.** Test directories carry no
  `__init__.py`, so two `test_home.py` files resolve to one module and pytest aborts collection.
  hera-code's are prefixed `test_code_` where they would otherwise collide with a vendored one.

## Vendored packages

Nine directories under `packages/` are **copies** of hera's, not forks:
`hera_home`, `hera_storage`, `hera_prompts`, `hera_providers`, `hera_permissions`, `hera_tools`,
`hera_skillsets`, `hera_profiles`, `hera_chats`.

**They are not edited.** Not to fix a bug, not to add a parameter, not to widen a type.
`tests/test_vendor.py` fails if one changes, and that is the point: keeping them byte-identical is
what makes swapping this directory for a git source a `pyproject.toml` edit and nothing else
([ADR 1](docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md)).

Everything hera-code needs to redirect is already injectable — the database URL, the mind path, the
MCP config path, the built-in server, the asking tool, and `SLOT_PROJECT` for everything about a
working tree. **If you find something that is not, that is the ADR to re-open, not the file to
patch.**

### Refreshing one

```bash
rsync -a --exclude='__pycache__' --exclude='*.py[cod]' --exclude='.*_cache' \
  ../hera/packages/hera_tools/ packages/hera_tools/
uv run python -m tools.vendor_digest --write
uv run pytest tests/test_vendor.py
```

Commit it on its own, as `chore(vendor): refresh hera_tools to <commit>`, and update the commit
recorded at the top of `packages/VENDOR.md`. A refresh mixed into a feature branch is a diff nobody
can review.

If a copy really has to be patched, it is recorded in the table in `packages/VENDOR.md` **first**,
with the reason and the upstream issue. There are no patches, and that is a claim worth keeping
true — `test_vendor.py::test_no_copy_claims_to_be_patched` is what notices when it stops being.

## Tags are the moving point

Nothing ships off a branch. A tag is the only thing that causes a release.

| Tag | Releases |
|---|---|
| `v1.2.3` | the application — five platform binaries and a checksum file |
| `hera-code-graph-v0.1.0` | one package, wheel attached |

`release.yml` refuses **any** tag whose version disagrees with the `pyproject.toml` it belongs to —
`packages/<name>/` for a package, `apps/cli/` for the application — so the version a person sees
can never be the release before it. `main` being green means it is *releasable*, not released.

**One version per releasable thing, declared once.** `pyproject.toml` is where it is written and
packaging is where it is read back: `hera_code.__version__` asks `importlib.metadata` rather than
repeating the number. To display it somewhere new, read that field — do not add a constant.

To cut an application release, bump `version` in `apps/cli/pyproject.toml` and tag `v1.2.3`.

## Architecture decisions

Anything that changes the shape of the system gets a file in [docs/adr/](docs/adr/): the context,
the decision, the consequences. Numbered, never edited after the fact — superseded instead.
`tests/test_docs.py` fails on an ADR that is not in the index, an index entry that goes nowhere, or
a gap in the numbering.
