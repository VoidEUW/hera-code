<!-- Title follows Conventional Commits: feat(todos): parse the four states -->

## What and why

<!-- The change in a sentence, and the reason it exists. Link the issue — the issue is the plan
     (ADR 6), so a PR without one is a PR nobody agreed to. -->

Closes #

## How it was verified

<!-- Which tests cover it, and what you actually ran. "CI is green" alone is not an answer for
     anything a person sees. For a terminal change, say what it looked like — and say what it
     looked like with NO_COLOR, at 70 columns, and through a pipe. -->

## Checklist

- [ ] Imports still point downwards (`ARCHITECTURE.md`); `uv run pytest tests/` passes
- [ ] **No vendored package under `packages/` was edited** — a fix goes upstream, ADR 1
- [ ] `ruff`, `mypy --strict` and the coverage gate pass locally
- [ ] New behaviour has a test; model behaviour is tested against `FakeProvider`, not a live
      endpoint
- [ ] New tables carry a package-prefixed `__tablename__` and an Alembic revision in `apps/cli`
- [ ] Everything written is English
- [ ] Docs updated if the shape of the system changed; an ADR added if a decision was made

<!-- If you touched the terminal, also: -->

- [ ] One renderer per event variant, and an unknown variant still degrades visibly
- [ ] Every colour used is saying one of the four sentences in `docs/tui.md`
- [ ] Nothing new draws a ringed glyph
- [ ] `NO_COLOR`, a non-TTY stdout and `TERM=dumb` each still produce something legible
