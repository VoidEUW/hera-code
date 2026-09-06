"""Test helpers that are not fixtures.

Separate from `conftest.py` because mypy excludes every `conftest.py` by name — several resolve to
the same module and given a choice it picks one and cannot find the others. Anything a test
*imports* therefore has to live somewhere else, or it is unchecked and unimportable at once.

The same arrangement hera uses for `core_support`.
"""

from __future__ import annotations

from hera_providers import ChatRequest, Event, FakeProvider, FakeProviderExhausted


class Scripted(FakeProvider):
    """`FakeProvider` that a test can queue turns onto after it has been wired in.

    `FakeProvider` takes its script at construction and copies the list, which does not fit a
    fixture graph where the provider is wired into the orchestrator before the test knows what it
    wants it to say. Its callable form does fit, so this is that — queue in front, `requests`
    behind, and no reaching into a private attribute.

    **Running out is a failure, not an empty answer.** A test that forgot to script a turn should
    say so rather than quietly assert against silence.
    """

    def __init__(self) -> None:
        self._queued: list[list[Event] | Exception] = []
        super().__init__(script=self._take)

    def script(self, turn: list[Event] | Exception) -> Scripted:
        """Queue one turn. Chainable, so a test can set up several in a row."""
        self._queued.append(turn)
        return self

    def _take(self, request: ChatRequest) -> list[Event] | Exception:
        del request
        if not self._queued:
            return FakeProviderExhausted("nothing was scripted for this request")
        return self._queued.pop(0)

    @property
    def sent(self) -> str:
        """Every message of the most recent request, flattened. For asserting on the prompt."""
        return "\n".join(str(message.content) for message in self.requests[-1].messages)
