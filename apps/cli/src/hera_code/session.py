"""A session is a chat, and running one turn is what this module does.

`hera_chats` owns the loop; this owns the *bookkeeping around* it — finding or creating the row,
building the context, persisting what came back. Deliberately small, because everything
interesting is one layer down (ADR 5).

**The order of the four steps is not arbitrary.** The user message is stored *before* the turn
runs and the assistant row is created *before* the turn runs, so a `^C` two seconds in leaves a
conversation with a question and a cancelled answer rather than a conversation with nothing in it.
`Turn.recorded` is complete at every moment, which is what makes that work.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlmodel import Session as DbSession

from hera_chats import (
    Chat,
    ChatEvent,
    ChatRepository,
    Message,
    MessageRepository,
    Project,
    Turn,
    TurnContext,
    build_history,
    events_of,
    title_from,
)
from hera_code import context as project_context
from hera_code.profile import active_profile
from hera_code.wiring import Services
from hera_code_home import user_instructions_path
from hera_code_workspace import discover, instructions


@dataclass
class Exchange:
    """One user message and the assistant row its answer is being written into."""

    chat: Chat
    user: Message
    assistant: Message
    turn: Turn

    @property
    def events(self) -> list[ChatEvent]:
        """Everything the turn has produced so far, coalesced and ready to persist.

        Correct at every moment rather than only at the end — a cancelled turn is persisted from
        here, with whatever had arrived.
        """
        return self.turn.recorded


def open_session(
    session: DbSession,
    services: Services,
    *,
    chat_id: UUID | None = None,
) -> Chat:
    """The session to speak into: a named one, the most recent, or a new one.

    A session is bound to nothing in v0.1.0 — binding it to a working tree so that `--continue`
    in one repository never resumes another's is v0.1.0 M5, along with the flags that need it.
    """
    chats = ChatRepository(session)
    owner = services.settings.owner_id
    if chat_id is not None:
        found = chats.get(chat_id)
        if found is None or found.owner_id != owner:
            raise LookupError(f"no session called {chat_id}")
        return found
    return chats.create(owner_id=owner)


def begin(
    session: DbSession,
    services: Services,
    chat: Chat,
    text: str,
    *,
    root: Path | None = None,
) -> Exchange:
    """Store what was typed, open the assistant row, and build the turn.

    Nothing has been sent to the model when this returns. Iterating
    :meth:`hera_chats.Turn.stream` is what does that, and the caller does it so the terminal can
    render as events arrive and `-p` can simply drain it.
    """
    messages = MessageRepository(session)
    profile = active_profile(session, services.settings.owner_id)

    user = messages.add_user_message(chat, text)
    if not chat.title:
        # Derived from the first message, the one place it is derived. A session list showing a
        # title that disagrees with the conversation is worse than one showing none.
        ChatRepository(session).touch(chat, title=title_from(text))
    assistant = messages.start_assistant_message(chat, profile_id=profile.id if profile else None)

    history = build_history(m for m in messages.for_chat(chat.id) if m.id != user.id)

    workspace = services.workspace if root is None else discover(root)
    # Read every turn rather than cached at launch: a person who edits CLAUDE.md mid-session
    # means the next turn to follow it, and that is the same promise the todo list makes.
    found = instructions(workspace.root, user_file=user_instructions_path())
    project = project_context.build(workspace=workspace, instructions=found.render())

    turn = services.orchestrator.begin(
        TurnContext(
            text=text,
            chat=chat,
            profile=profile,
            history=history,
            # Everything about the working tree goes into the project slot -- the seam that keeps
            # every vendored package unedited. See hera_code.context and ADR 5.
            project=_working_tree(services.settings.owner_id, workspace.root, project.render()),
        )
    )
    return Exchange(chat=chat, user=user, assistant=assistant, turn=turn)


async def run(session: DbSession, exchange: Exchange) -> AsyncIterator[ChatEvent]:
    """Drive the turn, persisting what happened whatever happens.

    Persisting in a ``finally`` rather than after the loop is the whole point: a cancelled turn, a
    provider that died and a turn that completed all leave a stored answer, because
    ``Turn.recorded`` was complete at the moment they stopped. A turn that only persisted on
    success would lose the half a person was reading.
    """
    messages = MessageRepository(session)
    try:
        async for event in exchange.turn.stream():
            yield event
    finally:
        messages.record(
            exchange.assistant,
            exchange.turn.recorded,
            prompt_fingerprint=exchange.turn.prompt_fingerprint,
        )


def _working_tree(owner_id: UUID, root: Path | None, instructions: str) -> Project:
    """The working tree as a `Project`, built in memory and **never added to a session**.

    `hera_chats.Turn` reads two things off `TurnContext.project`: `instructions`, which it binds
    into `SLOT_PROJECT`, and `pinned_skills`, which it merges into the router's pins. It is
    annotated as `hera_chats.Project`, a table.

    hera-code has **no projects as rows**. A working tree is the container and it is a directory,
    so a row per repository would be a table that exists to satisfy a type — one that then has to
    be kept in step with a directory that can be renamed, moved or deleted without telling us.

    An unsaved instance is the honest middle: it is the exact shape the turn wants, it type-checks,
    and nothing persists it. `instructions` is rebuilt every turn anyway, because the todo list is
    in it and the todo list changes — so a stored copy would be stale by definition.
    """
    name = root.name if root is not None else "working tree"
    return Project(owner_id=owner_id, slug="working-tree", name=name, instructions=instructions)


def resume(
    session: DbSession,
    services: Services,
    chat: Chat,
    assistant: Message,
    *,
    confirmed: Sequence[str] = (),
    denied: Sequence[str] = (),
    answers: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> Exchange:
    """Continue a turn a person has just settled.

    **The same assistant message, not a new one.** A suspended turn is the first half of an answer;
    resuming appends to it, so what a person read before the card and what they read after are one
    message rather than two that happen to be adjacent.

    The three ways to settle a call arrive on the same footing — allowed, refused, or replied to —
    and `hera_chats.Turn` decides which are dispatched. A refusal still produces a *result*: the
    model is told it was not allowed, which is what lets it try something else instead of hanging.
    """
    messages = MessageRepository(session)
    profile = active_profile(session, services.settings.owner_id)

    earlier = events_of(assistant)
    history = build_history(
        m for m in messages.for_chat(chat.id) if m.id != assistant.id and m.role != "assistant"
    )

    workspace = services.workspace if root is None else discover(root)
    found = instructions(workspace.root, user_file=user_instructions_path())
    project = project_context.build(workspace=workspace, instructions=found.render())

    turn = services.orchestrator.begin(
        TurnContext(
            text="",
            chat=chat,
            profile=profile,
            history=history,
            # The paused half. `Turn` re-streams none of it -- the person is already looking at
            # it -- and picks the settled calls back out before the model is asked anything.
            resume=earlier,
            confirmed=list(confirmed),
            denied=list(denied),
            answers=dict(answers or {}),
            project=_working_tree(services.settings.owner_id, workspace.root, project.render()),
        )
    )
    # The user message is the one that started the paused turn; nothing new was typed.
    return Exchange(chat=chat, user=assistant, assistant=assistant, turn=turn)


def latest_assistant(session: DbSession, chat: Chat) -> Message | None:
    """The message a card would be answered into."""
    return MessageRepository(session).latest_assistant(chat.id)
