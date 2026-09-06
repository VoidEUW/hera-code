"""The coding register lives in a profile, never in a mind region.

hera and hera-code share `~/.hera/mind` (ADR 5), so a mind edit here would change how *she*
answers in a chat window too. The line `docs/frontend.md` draws — a sentence that would still be
true in a chat window is a mind region — is the thing these tests hold.
"""

from __future__ import annotations

from uuid import UUID

from hera_profiles.traits import BEHAVIOUR_TRAITS, DEPTH
from sqlmodel import Session

from hera_code.profile import (
    CODING_SLUG,
    CODING_TRAITS,
    active_profile,
    ensure_coding_profile,
)
from hera_home import mind_dir
from hera_profiles import MindRepository, ProfileRepository


def test_it_creates_the_coding_profile_and_makes_it_default(
    session: Session, owner_id: UUID
) -> None:
    profile = ensure_coding_profile(session, owner_id)

    assert profile.slug == CODING_SLUG
    assert profile.is_default
    assert profile.traits[DEPTH] == "brief"


def test_running_it_twice_returns_the_same_row(session: Session, owner_id: UUID) -> None:
    """Idempotent, so it can run on every launch rather than only the first."""
    first = ensure_coding_profile(session, owner_id)
    second = ensure_coding_profile(session, owner_id)

    assert first.id == second.id
    assert len(ProfileRepository(session).for_owner(owner_id)) == 1


def test_a_trait_a_person_changed_is_not_reset(session: Session, owner_id: UUID) -> None:
    """**Somebody who set `thorough` because they wanted the reasoning meant it.**

    A launch that quietly reset it every time would make the setting look broken, which is worse
    than not having it.
    """
    profile = ensure_coding_profile(session, owner_id)
    ProfileRepository(session).set_traits(profile, {**profile.traits, DEPTH: "thorough"})

    again = ensure_coding_profile(session, owner_id)

    assert again.traits[DEPTH] == "thorough"


def test_every_seeded_trait_is_one_the_registry_admits() -> None:
    """A trait the registry rejects is dropped silently by `PromptBuilder` and reported only by
    `rejected_traits` — so a typo here would be a setting that does nothing and says nothing."""
    for key, value in CODING_TRAITS.items():
        spec = next((s for s in BEHAVIOUR_TRAITS.specs if s.key == key), None)
        assert spec is not None, f"{key} is not a declared behaviour trait"
        if spec.choices:
            assert value in spec.choices, f"{key}={value!r} is not one of {spec.choices}"


def test_the_profile_carries_no_prose(session: Session, owner_id: UUID) -> None:
    """**A profile that started carrying prose would be a second mind with no git history.**

    Anything that wants a paragraph is either project text — which belongs in `SLOT_PROJECT`,
    where it can name the working tree — or a mind region, which belongs to both applications.
    """
    profile = ensure_coding_profile(session, owner_id)

    assert profile.overrides == {}
    assert profile.disabled_regions == []


def test_seeding_writes_nothing_into_the_mind(session: Session, owner_id: UUID) -> None:
    """The mind is shared. If this ever fails, ADR 5 is what to re-open."""
    mind = MindRepository(mind_dir())
    mind.ensure()
    before = mind.read_all()

    ensure_coding_profile(session, owner_id)

    assert mind.read_all() == before


def test_the_active_profile_is_the_default_one(session: Session, owner_id: UUID) -> None:
    ensure_coding_profile(session, owner_id)
    found = active_profile(session, owner_id)

    assert found is not None
    assert found.slug == CODING_SLUG


def test_no_profile_at_all_is_a_real_answer(session: Session, owner_id: UUID) -> None:
    """`PromptBuilder.build(None)` renders the mind with no profile applied, which is a working
    prompt. A turn should not fail because a row is missing."""
    assert active_profile(session, owner_id) is None
