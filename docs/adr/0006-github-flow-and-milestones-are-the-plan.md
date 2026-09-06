# 6. GitHub Flow, protected `main`, and milestones as the plan

- Status: accepted
- Date: 2026-09-06

## Context

Plans written into files rot. A `docs/plan.md` is accurate on the day it is committed and drifts
every day after, because updating it is a separate act from doing the work — and the person doing
the work already told the truth somewhere else, in a branch name or a commit message.

Issues do not have that problem. An issue is fetched when it is worked on, so it is read at the
moment it matters and edited by whoever noticed it was wrong. A milestone is a set of issues with
a name, which makes it exactly the right size for "the steps of a version".

The release side has its own version of the same problem: a version number written in two places
is a version number that will eventually disagree with itself, and the place a person notices is
an About box showing the release before the one they installed.

## Decision

**GitHub Flow.** `main` is always releasable and protected. Everything else is a short-lived
branch off `main`, opened as a pull request, squash-merged, deleted. No long-running branches, no
direct pushes to `main`, no merge commits.

| Prefix | For |
|---|---|
| `feat/` | new behaviour |
| `fix/` | a bug |
| `chore/` | tooling, dependencies, CI, a vendor refresh |
| `docs/` | documentation only |
| `refactor/` | structure, no behaviour change |
| `test/`, `perf/`, `ci/`, `build/`, `revert/` | as named |

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) —
`feat(todos): parse the four states` — enforced by a `commit-msg` hook. The type drives
`CHANGELOG.md`, which is written per release rather than generated per commit.

**Milestones are the plan.** A version document in `docs/versions/` says what a version is *for*
and is frozen when its tag is cut; the milestone and its issues are what stays current. If the two
disagree, the issues are right and the version document is a record of what was believed at the
time — which is worth keeping rather than quietly correcting.

**Tags are the only thing that ships.**

| Tag | Releases |
|---|---|
| `v1.2.3` | the application — binaries for five platforms |
| `hera-code-graph-v0.1.0` | one package, wheel attached |

`release.yml` refuses any tag whose version disagrees with the `pyproject.toml` it belongs to.
One version per releasable thing, declared once, read back from packaging: `hera_code.__version__`
asks `importlib.metadata` rather than repeating the number. To display it somewhere new, read that
field — do not add a constant.

## Consequences

- **A milestone that changes says so in place, and keeps its number.** M4 means the todo list
  forever, even if what is in it changes; renumbering after the fact makes every commit message
  and status entry that says M4 wrong. Dropping one silently is what turns *we decided not to*
  into *we forgot*.
- **`docs/status.md` is a snapshot and nothing else.** Present tense, rewritten as milestones
  land. It is not a changelog and not a plan; the three documents that are easy to collapse into
  each other are separated in `docs/versions/README.md`, and that table is worth re-reading before
  adding to any of them.
- **CI is the gate, not review alone.** lint, `mypy --strict`, tests on 3.12 and 3.13, and the
  four meta-tests. `main` being green means it is *releasable*, not released.
- The binary release matrix means a tag produces five artifacts and a checksum file, and
  `install.sh` picks by platform. A tag that fails to build on one platform fails the release
  rather than shipping four — a partial release is worse than a late one, because the person who
  gets the missing platform cannot tell it from a network problem.
