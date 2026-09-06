# 3. The transcript lives in scrollback, and the dock is pinned

- Status: accepted
- Date: 2026-09-06

## Context

hera-code is a terminal application and the brief for it is specific: it should feel like Claude
Code — the conversation always visible, scrolling that works the way the terminal's own scrolling
works — and it must show the todo list at all times, because the todo list is the feature the rest
of the design is built around.

Those two requirements pull against each other. A persistently visible panel is what a full-screen
TUI is for; native scrollback is what a full-screen TUI gives up. Taking the alternate screen
buffer means the terminal's scroll wheel scrolls nothing, selection has to be reimplemented, and
closing the session leaves an empty terminal where the conversation was.

Three arrangements were considered:

- **Full screen**, alternate buffer, panes. Most room for hera-code's own features, and it loses
  every one of the properties above.
- **Textual in inline mode.** Renders a fixed region below the cursor and leaves scrollback alone.
  Correct in principle.
- **`prompt_toolkit` for the pinned region, `rich` for everything drawn into scrollback.**

## Decision

The transcript is **printed into the terminal's real scrollback**. The dock is a
`prompt_toolkit.Application(full_screen=False)` anchored at the bottom, redrawn in place, and
never scrolled away. Everything inside either is rendered by `rich`.

The dock is three rows and the top one is the todo strip, which is how the always-visible
requirement is met without a pane: progress, the item in progress, and `^T` to expand the whole
list in place. Overlays — the todo board, the session picker, settings — are `Float`s in the same
layout, not a second full-screen mode.

**Consequences of scrollback that are load-bearing, not incidental:** the terminal scrolls, the
mouse selects, `| less` works, and the conversation is still there after the process exits.

## Why not Textual

Textual's inline mode does the same thing and the widget model is genuinely nicer to build a dock
in. Two reasons it lost:

- **Textual owns the render loop.** Writing arbitrary output into scrollback from inside a Textual
  app is working against the framework rather than with it, and the transcript is the majority of
  what this application draws.
- **Its strengths are for a layout we do not have.** CSS, focus management and the widget tree pay
  off across a full-screen composition. A three-row dock with one input in it is not that, and the
  thing we *do* need a lot of — completion for `/commands` and `@file` — is `prompt_toolkit`'s
  built-in machinery.

If the dock grows into something with panes and focus cycling, this is the record to re-open.

## Consequences

- **The transcript cannot be retroactively edited**, because it has already been printed. This is
  why "the server render is authoritative at `turn_closed`" is implemented as *re-render the
  finished turn once, below the optimistic one is not an option* — the coalesced list is printed
  when the turn closes and the streaming output above it is what it is. Streaming output is
  therefore written to be correct as it goes rather than fixed up later.
- **A dock writing escape codes into a pipe is the failure mode this design is most exposed to.**
  Non-TTY stdout disables the dock entirely and prints plain text — `hera-code -p "…" | cat` is a
  test in the suite, not a manual check.
- Terminal width changes require reflowing only the dock. The transcript keeps the width it was
  printed at, which is what every other scrollback-based tool does and what people expect.
- **68 columns for prose regardless of terminal width.** Inherited from hera's `docs/frontend.md`,
  and it survives the conversion intact: a reading column the width of a monitor is the fastest
  way to make a text interface tiring. Code blocks and tables are not prose and use the width.
- `prompt_toolkit` and `rich` are two dependencies where a full-screen framework would have been
  one. Both are mature, widely deployed, and — relevant for [ADR 6](0006-github-flow-and-milestones-are-the-plan.md)
  — straightforward for PyInstaller to bundle, which a framework with a CSS parser and its own
  asset loading is less reliably.
