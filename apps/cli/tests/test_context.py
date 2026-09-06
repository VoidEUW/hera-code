"""`SLOT_PROJECT`: the seam that keeps every vendored package unedited.

`hera_profiles` already defines a slot meaning *what we are working on*, and the working tree, the
instruction files, the todo list, the shadow index and the graph's freshness are all exactly that.
Composing them here rather than adding a slot is why ADR 1's no-edit rule has cost nothing so far —
so these tests are about that seam holding, not about string formatting.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from hera_code.context import (
    DEFAULT_CEILING,
    PREAMBLE,
    ProjectContext,
    build,
    sections_of,
)


def test_the_preamble_is_always_there() -> None:
    context = build()
    assert "how-you-work" in sections_of(context)
    assert PREAMBLE in context.render()


def test_an_empty_section_is_left_out_rather_than_rendered_empty() -> None:
    """A model told `<todos></todos>` concludes there is an empty list. A model told nothing
    concludes there is no list, which is the true thing."""
    context = build(todos="")
    assert "todos" not in list(sections_of(context))
    assert "<todos>" not in context.render()


def test_the_working_tree_is_named(tmp_path: Path) -> None:
    assert str(tmp_path) in build(root=tmp_path).render()


def test_the_sections_are_in_the_order_a_model_should_read_them(tmp_path: Path) -> None:
    """Not alphabetical, and not arbitrary. The preamble frames everything after it; a person's
    own instructions outrank ours; the todo list is last because it is what changes every turn and
    what a model should be looking at when it starts work."""
    context = build(
        root=tmp_path,
        instructions="Run the tests with `just test`.",
        graph="1 file, 2 symbols",
        notes="- limiter: the retry logic is load-bearing",
        todos="- [ ] a1 do the thing",
    )
    assert list(sections_of(context)) == [
        "how-you-work",
        "where-we-are",
        "instructions",
        "what-the-index-knows",
        "notes-you-have-kept",
        "todos",
    ]


def test_what_did_not_fit_is_reported_rather_than_truncated() -> None:
    """A slot that quietly truncated would fail as a model that ignored an instruction, which is
    indistinguishable from one that read it and disagreed."""
    context = build(instructions="x" * 5_000, todos="y" * 5_000, ceiling=1_000)

    assert context.dropped
    assert "x" * 5_000 not in context.render()


def test_the_preamble_survives_a_ceiling_that_would_drop_it() -> None:
    """A ceiling small enough to exclude it is a misconfiguration, and the failure it would
    produce — an agent with no instructions at all — is worse than being one section over."""
    context = build(instructions="x" * 100, ceiling=1)

    assert "how-you-work" in sections_of(context)
    assert context.dropped == ["instructions"]


def test_a_repository_that_committed_a_novel_does_not_eat_the_window() -> None:
    context = build(instructions="x" * 500_000)
    assert len(context.render()) < DEFAULT_CEILING * 2


@pytest.mark.parametrize(
    ("compose", "tag"),
    [
        (lambda text: build(instructions=text), "instructions"),
        (lambda text: build(todos=text), "todos"),
        (lambda text: build(notes=text), "notes-you-have-kept"),
        (lambda text: build(graph=text), "what-the-index-knows"),
    ],
)
def test_each_section_is_labelled(compose: Callable[[str], ProjectContext], tag: str) -> None:
    """A labelled block is what lets a model tell *what you told me to do* from *what is
    currently on the list*.

    Nothing ever reads these back. `hera_prompts` takes the result as an opaque pre-rendered
    string through a named slot, which is the only way foreign content is allowed in — so this is
    structure for the model to read, never a format anything parses.
    """
    context = compose("something")
    assert f"<{tag}>" in context.render()
    assert f"</{tag}>" in context.render()
