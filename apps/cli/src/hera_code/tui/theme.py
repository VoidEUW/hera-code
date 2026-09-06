"""Colour, and what each one is allowed to say.

`docs/tui.md` § Colour is the authority. Four meanings, and **using the wrong one is a bug in the
same way a wrong `if` is** — if a colour appears somewhere and you cannot say which of the four
sentences it is saying, it does not belong there.

Three things about this module are decisions rather than implementation:

**No background is ever painted.** The terminal's background belongs to the person. They chose it,
every other tool in their session respects it, and an application that paints over it is the one
that looks broken next to the rest. That is the single place the conversion refuses hera's design,
which spends four paragraphs getting its ground right.

**Light or dark is detected, not assumed** — and the config key exists because detection cannot be
relied on. Getting it wrong means brass on a light terminal, which is unreadable, and a person
should not have to argue with it.

**`NO_COLOR` is honoured absolutely**, and the meaning colour carried moves into the words: a
failed row reads *failed* rather than being red. That is what makes the interface legible with
colour off rather than merely usable.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

Appearance = Literal["system", "light", "dark"]


class Meaning(StrEnum):
    """What a colour is allowed to say. There are four, and there are only four.

    A `StrEnum` rather than four constants, so a renderer names the *meaning* and never the
    colour — which is what makes the rule checkable rather than a convention.
    """

    AUTHORITY = "authority"
    """The mark, skills, permission cards, emphasis. hera's brass."""

    ATTENTION = "attention"
    """Thinking, a tool running, live state. hera's laurel."""

    ITS_OWN = "its own"
    """The agent's name, and the send action. Nothing else. hera's pomegranate."""

    FAILURE = "failure"
    """A refusal or a failure. Deliberately not harmonised with the others."""

    MUTED = "muted"
    """Not an accent. Labels, timestamps, metadata, collapsed activity — the chrome that should
    get out of the way. Here because a renderer needs to name it and `dim` is not a meaning."""


DARK: dict[Meaning, str] = {
    Meaning.AUTHORITY: "#D9AE52",
    Meaning.ATTENTION: "#7FB069",
    Meaning.ITS_OWN: "#DE4E64",
    Meaning.FAILURE: "#E0685E",
    Meaning.MUTED: "dim",
}

LIGHT: dict[Meaning, str] = {
    Meaning.AUTHORITY: "#8A6A1C",
    Meaning.ATTENTION: "#3F6B32",
    Meaning.ITS_OWN: "#A82A45",
    Meaning.FAILURE: "#B03A2E",
    Meaning.MUTED: "dim",
}

MEASURE = 68
"""Where prose wraps, whatever the terminal is.

**Kept from hera's `docs/frontend.md` and it is the most important thing this module inherits.**
A reading column that runs the width of a monitor is the fastest way to make a text interface
tiring, and every wide terminal is a monitor's width.

Code, tables and diffs are **not prose** and use the full width. Capping those would be the
version of this rule that looks broken.
"""


@dataclass(frozen=True)
class Theme:
    """Resolved colour for one terminal, on one launch."""

    dark: bool = True
    colour: bool = True
    motion: bool = True

    def style(self, meaning: Meaning) -> str:
        """The rich style for one meaning, or nothing at all when colour is off.

        `""` rather than a default colour: with `NO_COLOR` set, nothing should emit a style at
        all. A "colourless" style that still wrote a reset sequence would put escape codes in a
        pipe, which is the failure ADR 3 says this design is most exposed to.
        """
        if not self.colour:
            return ""
        return (DARK if self.dark else LIGHT)[meaning]

    def measure(self, width: int) -> int:
        """How wide prose may be. Never more than :data:`MEASURE`, never wider than the terminal."""
        return min(width, MEASURE) if width > 0 else MEASURE


def detect(
    appearance: Appearance = "system",
    *,
    environ: dict[str, str] | None = None,
    isatty: bool | None = None,
) -> Theme:
    """Work out what this terminal can do.

    `environ` and `isatty` are injected so the whole thing is testable without a terminal — which
    matters more here than usual, because every branch below is about an environment CI does not
    have.
    """
    env = environ if environ is not None else dict(os.environ)
    tty = isatty if isatty is not None else sys.stdout.isatty()

    # NO_COLOR's own specification: any value, including empty, means off.
    colour = "NO_COLOR" not in env and tty and env.get("TERM") != "dumb"

    motion = colour and env.get("HERA_CODE_MOTION", "").lower() != "off"

    return Theme(dark=_is_dark(appearance, env), colour=colour, motion=motion)


def _is_dark(appearance: Appearance, env: dict[str, str]) -> bool:
    """Dark unless something says otherwise.

    The config wins outright — that is why the key exists. `system` falls back to `COLORFGBG`,
    which is the only signal available without querying the terminal and waiting for a reply that
    may never come. An OSC 11 query would be more accurate and can hang on a terminal that does
    not answer, which is a bad trade for a colour.

    Dark is the default because it is the commoner terminal and because being wrong that way is
    survivable: the light palette on a dark background is dim but readable, and the dark palette
    on a light one is not.
    """
    if appearance == "dark":
        return True
    if appearance == "light":
        return False

    # `COLORFGBG` is `foreground;background`, where the background is an ANSI colour number.
    # 0-6 and 8 are the dark ones.
    parts = env.get("COLORFGBG", "").split(";")
    if len(parts) >= 2 and parts[-1].strip().isdigit():
        return int(parts[-1]) in {0, 1, 2, 3, 4, 5, 6, 8}
    return True
