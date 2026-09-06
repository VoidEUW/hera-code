"""The coding register — a profile, not a fork of the mind.

hera and hera-code share `~/.hera/mind` (ADR 5). Twelve regions, one git repository, one
character. What differs between answering in a chat window and answering in a terminal is not
*who she is*, and the line `docs/frontend.md` draws is the one held here:

    If a sentence would still be true in a chat window it is a mind region.
    If it would not, it is project text or a trait.

So the coding register lives in exactly two places, and neither of them is a mind file:

* **Behaviour traits** on a `coding` profile — `approach.depth: brief`, `identity.tone.emoji:
  false`. Those are declared knobs with declared values, and setting one is what a profile is for.
* **The project-slot preamble** in :mod:`hera_code.context` — how to work in a terminal, and that
  a diff is the deliverable. That is *what we are working on*, which is what `SLOT_PROJECT` means.

**Nothing here writes to a mind region**, and if something ever needs to, that is ADR 5 to
re-open rather than a `MindRepository.write` call to add.
"""

from __future__ import annotations

from uuid import UUID

from hera_profiles.traits import DEPTH, EMOJI, FORMALITY
from sqlmodel import Session

from hera_profiles import Profile, ProfileRepository

CODING_SLUG = "coding"
"""The profile hera-code answers as, and the one a session falls back to.

hera's `ensure_default_exists` seeds a profile called *Hera* under the slug `hera`. hera-code does
not use that method: it keeps its own database, so it would be seeding a second profile row that
answers the same as the first while the *default* one carried none of the coding traits.
"""

CODING_TRAITS: dict[str, object] = {
    # A coding agent that writes three paragraphs before a diff is one a person scrolls past
    # (`docs/tui.md` § Voice). `brief` is the trait that says so in the prompt.
    DEPTH: "brief",
    FORMALITY: "neutral",
    EMOJI: False,
}
"""What the `coding` profile sets, and deliberately little.

Three traits rather than a paragraph. Anything that wants a paragraph is either project text —
which belongs in the slot, where it can name the working tree — or a mind region, which belongs to
both applications. A profile that started carrying prose would be a second mind with no git
history behind it.
"""

CODING_DESCRIPTION = "Her, in a terminal, with a working tree in front of her."


def ensure_coding_profile(session: Session, owner_id: UUID) -> Profile:
    """The `coding` profile, created and made default on first launch.

    Idempotent, so it runs on every launch rather than only the first. Somebody who deleted the
    row should get it back, and discovering on the first turn that there is nobody to answer as is
    a worse way to find out.

    **Existing traits are not overwritten.** Somebody who set `approach.depth: thorough` because
    they wanted the reasoning meant it, and a launch that quietly reset it every time would make
    the setting look broken. The row is seeded once and is theirs afterwards — the same stance the
    config file takes.
    """
    repository = ProfileRepository(session)
    existing = repository.by_slug(owner_id, CODING_SLUG)
    if existing is not None:
        if not existing.is_default and repository.default_for(owner_id) is None:
            return repository.make_default(existing)
        return existing

    profile = repository.create(
        owner_id,
        "Coding",
        slug=CODING_SLUG,
        description=CODING_DESCRIPTION,
        traits=dict(CODING_TRAITS),
    )
    return repository.make_default(profile)


def active_profile(session: Session, owner_id: UUID) -> Profile | None:
    """Who is answering. The default, or whatever single profile exists, or nothing.

    ``None`` is a real answer and not an error: `PromptBuilder.build(None)` renders the mind with
    no profile applied, which is a working prompt. A turn should not fail because a profile row is
    missing.
    """
    repository = ProfileRepository(session)
    return repository.default_for(owner_id)
