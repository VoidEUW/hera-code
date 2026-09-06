"""The mark, and the one absolute visual rule.

**The ocellus** — a single peacock eye — is the element the interface is remembered by. Argus
Panoptes had a hundred eyes and never slept; when he was killed, Hera set his eyes into the tail of
the peacock, so that she would still see everything. An interface whose strongest functional
requirement is *show me everything you did* is not decorated with peacock eyes: it **is** the
hundred eyes.

hera's `favicon.svg` is four concentric circles — ground, brass ring, laurel iris, punched pupil.
In a terminal that is one glyph, and where hera varies it by *size* this varies it by **colour**,
which happens to carry more.

**Nothing else in the terminal may use a ringed glyph.** That is the rule the mark earns its
meaning from, and it is the one visual rule in `docs/tui.md` that is absolute. `RESERVED` is what
makes it checkable.
"""

from __future__ import annotations

from hera_code.tui.theme import Meaning, Theme

MARK = "◉"
"""The eye at rest. The header, and the first eye of every turn."""

BEAT: tuple[str, ...] = ("◌", "◍", "◎", "◉")
"""The eye opening. Four frames of the thinking indicator.

Slow enough to read as attention rather than as a spinner — hera's is 2.4 seconds for a whole
cycle, and that number is a design instruction rather than a preference: *nothing here should
flicker*.
"""

BEAT_SECONDS = 2.4

GUTTER = "┆"
"""The hairline down the left of an activity block. What turns six tool calls into a column."""

RESERVED: frozenset[str] = frozenset({*BEAT, MARK, "◉", "◯", "⊙", "◦", "●", "○"})
"""Every ringed or dotted glyph, reserved for the mark.

The rule is *nothing else uses a ringed glyph*, and a rule with no way to check it is a
convention. `test_tui_theme.py` walks the renderers and fails if one of these appears outside this
module — which is how a well-meant `●` in a list stops being a thing somebody has to notice in
review.
"""


def mark(theme: Theme, *, meaning: Meaning = Meaning.AUTHORITY) -> tuple[str, str]:
    """The mark and the style to draw it in.

    A tuple rather than a rendered string, because the caller composes it into a line and knows
    the width it has. Brass at rest — the mark is authority; laurel while something is running,
    which is the caller's business to say.
    """
    return MARK, theme.style(meaning)


def frame(theme: Theme, elapsed: float) -> str:
    """Which frame of the beat to draw at ``elapsed`` seconds into a turn.

    **Still when motion is off**, which is `NO_COLOR`, `HERA_CODE_MOTION=off`, a non-TTY stdout or
    `TERM=dumb`. `docs/tui.md` inherits hera's `prefers-reduced-motion` rule without softening it:
    the terminal must be completely usable and completely legible with all motion off, so what a
    still frame shows is the *open* eye rather than the first one.
    """
    if not theme.motion:
        return MARK
    step = int((elapsed % BEAT_SECONDS) / (BEAT_SECONDS / len(BEAT)))
    return BEAT[min(step, len(BEAT) - 1)]
