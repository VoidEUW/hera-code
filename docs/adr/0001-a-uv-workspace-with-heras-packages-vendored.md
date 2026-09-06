# 1. A uv workspace of its own, with hera's packages vendored

- Status: accepted
- Date: 2026-09-06

## Context

hera-code is built on hera's libraries: `hera_providers` for the model boundary, `hera_tools` for
MCP, `hera_skillsets` for `SKILL.md` routing, `hera_permissions`, `hera_prompts`, `hera_storage`,
`hera_profiles` and `hera_chats` for the turn loop. That is settled — it is most of why building
it is worth doing.

Where it lives is not. hera's own [v0.3.0 document](https://github.com/VoidEUW/hera/blob/main/docs/versions/v0.3.0.md)
names two options and calls both undecided: a second `apps/` member inside hera, which is nearly
free because the uv workspace already does it and which keeps both applications building in one
CI run; or its own repository consuming published packages, which is a real packaging decision
that project has never had to make.

The complication is that hera **publishes nothing**. `CONTRIBUTING.md` there documents consuming a
package through a git subdirectory pinned to a tag, and the tags for these nine do not exist yet.
So "its own repository consuming published packages" is not currently an option — only "its own
repository consuming *something*".

## Decision

**Its own repository**, a uv workspace with the same shape as hera's: libraries under `packages/`,
one application under `apps/`.

Nine of hera's packages are **vendored** — copied into `packages/`, byte-identical, with
`packages/VENDOR.md` recording the upstream commit and a digest per package.
`tests/test_vendor.py` fails if any copy is edited.

The copies are not forks and are never patched. When a copy needs to change, the change goes
upstream and the copy is refreshed. When hera publishes tags, each directory is deleted and each
row in `[tool.uv.sources]` becomes:

```toml
hera-chats = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_chats", tag = "hera-chats-v0.1.0" }
```

That is the entire migration, and keeping it that cheap is the reason for the no-edit rule.

## Why not a second `apps/` member in hera

It is genuinely cheaper, and the argument for it — one CI run keeps the packages honest — is
good. Three things outweigh it:

- **A second application in the same repository is not an independent consumer.** The claim being
  tested is that `hera_storage` and `hera_prompts` are liftable into *an unrelated project*. A
  sibling directory that shares a lockfile, a ruff configuration and a `uv sync` is not that. This
  repository is, and `tests/test_layering.py` gives those two an empty allow-list here for the
  same reason it does there — except that here it means something.
- **hera-code releases differently.** hera ships a Docker image and a wheel; hera-code ships a
  binary per platform, five of them, built by PyInstaller. Two release workflows keyed off two tag
  shapes in one repository is a `release.yml` nobody wants to read.
- **The dependency runs one way.** hera-code needs hera's packages; hera needs nothing of
  hera-code's, and in v0.3.0 it reaches hera-code over MCP like any other server. A shared
  repository would imply a mutual coupling that does not exist.

## Consequences

- **A bug fixed here has to be fixed there.** This is the real cost and it is not small: nine
  packages are now duplicated on disk, and the vendored copy is the one that runs. The no-edit
  rule is what stops it becoming two codebases — a bug found here is reported and fixed upstream,
  and arrives on the next refresh.
- **Refreshing is a chore, and a visible one.** `chore(vendor): refresh hera_tools to <commit>` is
  its own commit, and the digest table means the diff is reviewable.
- **The claim about the foundation packages becomes testable.** Every leak found here is a leak
  hera is already paying for quietly. That is the payoff, and it starts the moment the first
  `uv sync` succeeds.
- **hera's CI does not run hera-code's tests.** A change upstream that breaks something here is
  found at refresh time rather than at merge time. Acceptable while hera-code is the only
  consumer; if a third one appears, hera should publish.
- One thing that did **not** turn out to be a cost: not a single vendored package needed
  modification. Everything hera-code redirects — the database URL, the config path, the mind
  directory, the built-in MCP server, the asking tool — was already injectable. If that stops
  being true, this ADR is the thing to re-open.
