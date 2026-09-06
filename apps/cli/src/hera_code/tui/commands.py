"""`/commands` and `@file` completion.

Two completers on one input, chosen by what the word under the cursor starts with.

**`/skill-name` is not handled here.** `hera_skillsets.SkillRouter.select()` already strips a
leading `/command` and resolves it before the turn is built — so a slash that names a skill
travels through to the router untouched, and the gutter row it produces says `slash`, which is the
person's decision being recorded rather than the model's. What this module does is *offer* the
names; the router is what acts on them.

That split matters: skill selection is code (hera's ADR 5), and a completer that resolved a skill
itself would be a second place deciding what a turn gets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


@dataclass(frozen=True)
class Command:
    """One thing typing `/` offers."""

    name: str
    summary: str
    skill: bool = False
    """Whether this is a skill rather than a built-in. Shown differently, because *use this skill*
    and *quit* are not the same kind of act and a flat list of both is a list nobody scans."""


BUILT_INS: tuple[Command, ...] = (
    Command("help", "what the keys and commands do"),
    Command("skills", "what skills are available, and where they came from"),
    Command("todos", "the plan for this run"),
    Command("clear", "start a new session, keeping this one"),
    Command("quit", "leave"),
)
"""The commands hera-code answers itself.

Short on purpose. Everything a person does often should be a key rather than a command — `^T` for
the todo list, `^C` to stop — and a command menu that duplicates the keys teaches neither.
"""


class SlashCompleter(Completer):
    """Offers built-ins and skill names after a `/` at the start of the line.

    **Only at the start.** A `/` inside a sentence is a path separator or a date, and offering a
    menu there would fire constantly while somebody types `src/api.py`.
    """

    def __init__(self, skills: Callable[[], Sequence[str]] | None = None) -> None:
        self._skills = skills or (lambda: ())

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:
        del complete_event
        text = document.text_before_cursor
        if not text.startswith("/") or "\n" in text:
            return
        typed = text[1:]
        for command in self._commands():
            if command.name.startswith(typed):
                yield Completion(
                    command.name,
                    start_position=-len(typed),
                    display=f"/{command.name}",
                    display_meta="skill" if command.skill else command.summary,
                )

    def _commands(self) -> list[Command]:
        # Built-ins first: they are a fixed short list and a person looking for `/quit` should not
        # scroll past forty skills to reach it.
        return [
            *BUILT_INS,
            *(Command(name, "", skill=True) for name in sorted(self._skills())),
        ]


class PathCompleter(Completer):
    """Offers paths from the working tree after an `@`.

    The paths come from a callable rather than a directory scan here, so the completer uses the
    same `.gitignore`-aware walk everything else does — one answer to *what files are there*, and
    a completer that offered `node_modules/...` would be a second.
    """

    def __init__(self, paths: Callable[[], Sequence[str]], limit: int = 20) -> None:
        self._paths = paths
        self._limit = limit

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:
        del complete_event
        word = document.text_before_cursor.rsplit(" ", 1)[-1]
        if not word.startswith("@"):
            return
        typed = word[1:]
        offered = 0
        for path in self._paths():
            if offered >= self._limit:
                return
            if typed and typed not in path:
                continue
            offered += 1
            yield Completion(path, start_position=-len(typed), display=path)


class Composer(Completer):
    """Whichever completer the word under the cursor calls for.

    One completer on the input rather than a mode a person has to be in. Typing `@` mid-sentence
    to name a file is the ordinary case, and so is a line that starts `/` — neither should require
    switching anything.
    """

    def __init__(self, slash: SlashCompleter, path: PathCompleter) -> None:
        self._slash = slash
        self._path = path

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:
        if document.text_before_cursor.startswith("/"):
            yield from self._slash.get_completions(document, complete_event)
            return
        yield from self._path.get_completions(document, complete_event)


def is_command(text: str) -> str:
    """The built-in command a line invokes, or ``""``.

    **Built-ins only.** A `/slash` that is not one of them is a skill, and it goes to the router
    untouched — which is what makes typing `/tdd` reach `hera_skillsets` rather than an error
    about an unknown command.
    """
    line = text.strip()
    if not line.startswith("/"):
        return ""
    name = line[1:].split()[0] if len(line) > 1 else ""
    return name if any(command.name == name for command in BUILT_INS) else ""
