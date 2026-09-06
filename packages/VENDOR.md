# Vendored packages

Nine of the packages under `packages/` are **copies** of hera's, not forks of them. They are here
because hera does not publish to an index yet, and for no other reason.

**Upstream:** `https://github.com/VoidEUW/hera`
**Commit:** `5800b71f4d8924615f01bfb4d11fff19807c69c4`
**Taken:** 2026-09-06

## The rule

**A vendored package is not edited.** Not to fix a bug, not to add a parameter, not to widen a
type. If one needs to change, the change goes upstream first and the copy is refreshed — which is
the whole point of keeping them byte-identical: swapping this directory for a git source is a
`pyproject.toml` edit and nothing else.

```toml
# what packages/ becomes once hera publishes tags
[tool.uv.sources]
hera-chats = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_chats", tag = "hera-chats-v0.1.0" }
```

Everything hera-code needs to redirect is already injectable, so that rule has cost nothing so far:
`StorageSettings.url` points the database at `~/.hera/code/sessions.sqlite3`,
`ToolsSettings.config_path` and `MindRepository(path=...)` default to the shared `~/.hera`, and
`ToolRegistry.from_config(builtin=...)` mounts `hera_code_mcp` under its own name. See
[ADR 1](../docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md).

## Refreshing one

```bash
rsync -a --exclude='__pycache__' --exclude='*.py[cod]' --exclude='.*_cache' \
  ../hera/packages/hera_tools/ packages/hera_tools/
uv run python tools/vendor_digest.py --write     # rewrites the table below
uv run pytest tests/test_vendor.py
```

Commit that on its own, as `chore(vendor): refresh hera_tools to <commit>`. A refresh mixed into a
feature branch is a diff nobody can review.

## If a copy really has to be patched

Then it is recorded **here first**, in the table below, with the reason and the upstream issue —
and `tests/test_vendor.py` reads this file, so an undocumented edit is a failing build rather than
a surprise at the next refresh.

There are no patches. That is a claim worth keeping true.

## Digests

One row per package. The digest is SHA-256 over the sorted `path\0sha256` lines of every file in
the package, so it changes if any file does.

| Package | Version | Files | Tree digest | Patched |
|---|---|---|---|---|
| `hera_home` | 0.1.0 | 5 | `3a04580b1b04b3f778bf2702b4e1f057453816e3c10532aa438d4db04c50db2c` | no |
| `hera_storage` | 0.1.0 | 18 | `ffb9e1cdff2237e13253e084253f05eadb92ff47342b7a33dd9b39605b06d090` | no |
| `hera_prompts` | 0.1.2 | 21 | `0112a8378afb1b2c846f3503ad04511bf700406ea2121e6e31ae4669f346322d` | no |
| `hera_providers` | 0.1.0 | 17 | `90fb342553d93216e4be139e6899c661b53df21ce547d0f762c0e58cd6969ea3` | no |
| `hera_permissions` | 0.1.0 | 9 | `51d90533f79fc6ee6953efff97275a4eef0cc90c2717515a6865b32d819aa544` | no |
| `hera_tools` | 0.1.0 | 21 | `4e397b85a55a39b9c30fd811437a980c381fff18852e9294467b6d0a3baa72b1` | no |
| `hera_skillsets` | 0.1.0 | 18 | `87f1e28b4bca69c214bd29255bf4236908c1a979ab9d43abfc64c37ac63fe91a` | no |
| `hera_profiles` | 0.1.0 | 16 | `2f342a9cdb9092a4399e71af60719b3b09f26846f5e1d0cc3a78575dc7b1b334` | no |
| `hera_chats` | 0.1.0 | 17 | `613a893aa23016c36db81b7f72fd1a47757f141fd8cd240d8e600804002722f3` | no |

## What is *not* vendored, and why

| | |
|---|---|
| `hera_mcp` | The server **hera** is. hera-code has its own — `hera_code_mcp` — and mounting hers would give a coding agent `remember`, `forget` and a chat scratchpad it has no business having |
| `hera_memories` | What she knows about **you**, across chats. Wanted, but v0.2.0 M4: a coding agent's memory of a repository is the shadow tree, and the two want designing together rather than one inherited |
| `hera_promptevo` | Does not exist upstream yet |
| `apps/core` | The FastAPI application and the SvelteKit interface. hera-code's application is `apps/cli` |
