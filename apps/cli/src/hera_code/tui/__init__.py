"""The terminal.

`docs/tui.md` is the design, and it governs everything here. What this package builds in v0.1.0 M3
is the *functional* half of it — every event variant renders, both cards can be answered, the
transcript goes to real scrollback and nothing draws into a pipe. The visual pass is v0.2.0 M1,
and `docs/versions/v0.1.0.md` names exactly what it defers.

The rules that are not negotiable, all of them inherited:

* **One renderer per event variant**, and an unknown one degrades *visibly*.
* **No parser.** A new thing the model can do is a new variant, never a regular expression.
* **Nothing else uses a ringed glyph** — that is the mark, and `ocellus.RESERVED` checks it.
* **Every colour says one of four sentences.** If you cannot say which, it does not belong.
* **The transcript belongs to the terminal.** Never the alternate screen buffer, never a repaint
  above the dock, and `| cat` must produce plain text.
"""

from __future__ import annotations

from hera_code.tui.ocellus import BEAT, MARK, RESERVED, frame, mark
from hera_code.tui.theme import DARK, LIGHT, MEASURE, Appearance, Meaning, Theme, detect
from hera_code.tui.transcript import collect, prose, render_turn

__all__ = [
    "BEAT",
    "DARK",
    "LIGHT",
    "MARK",
    "MEASURE",
    "RESERVED",
    "Appearance",
    "Meaning",
    "Theme",
    "collect",
    "detect",
    "frame",
    "mark",
    "prose",
    "render_turn",
]
