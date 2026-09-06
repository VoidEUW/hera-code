"""Boot settings for the application, from ``HERA_CODE_*`` environment variables.

Each library reads its own (``HERA_PROVIDER_*``, ``HERA_TOOLS_*``, ``HERA_CHATS_*``,
``HERA_STORAGE_*``); this is only what the *application* decides. Keeping them apart means a
library can be lifted into another project with its configuration intact, which is the whole
premise of the workspace — and here it is not a premise but a demonstration, since nine of them
came from one.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from pydantic_settings import BaseSettings, SettingsConfigDict

from hera_code_home import sessions_db_path

OWNER_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
"""The DNS namespace, used to derive a stable id for the single user."""

SINGLE_USER_ID = uuid5(OWNER_NAMESPACE, "hera-code.local")
"""Who owns everything. Derived rather than random, so it is the same on every launch without
needing a row to remember it in.

Deliberately **not** hera's ``uuid5(OWNER_NAMESPACE, "hera.local")``. The two applications keep
separate databases, so nothing joins across them, and giving them the same owner id would
suggest a relationship the schema does not have.
"""

FAKE_PROVIDER = "fake"
"""``HERA_CODE_PROVIDER=fake`` swaps in ``hera_providers.FakeProvider``.

The whole turn loop then runs with no endpoint, which is what CI drives and what every test
below the release milestone uses. A string rather than a boolean because a second scripted
provider is a plausible thing to want and ``HERA_CODE_PROVIDER=fake`` reads better than
``HERA_CODE_USE_FAKE_PROVIDER=1``.
"""


class CodeSettings(BaseSettings):
    """What the application itself decides."""

    model_config = SettingsConfigDict(env_prefix="HERA_CODE_", extra="ignore")

    owner_id: UUID = SINGLE_USER_ID

    provider: str = ""
    """Force a provider implementation. Empty means the active endpoint from ``config.toml``;
    :data:`FAKE_PROVIDER` means the scripted one."""

    motion: str = ""
    """``off`` disables the terminal's one animation. Also implied by ``NO_COLOR``, a non-TTY
    stdout and ``TERM=dumb`` — see ``docs/tui.md`` § Motion. Read by the terminal in M3."""

    def database_url(self) -> str:
        """The SQLite file under ``~/.hera/code``.

        Computed here rather than defaulted in ``hera_storage``, which is domain-free and does
        not know what ``~/.hera`` is. ``HERA_STORAGE_URL`` still overrides it — that is the
        escape hatch for pointing somewhere else entirely.
        """
        return f"sqlite:///{sessions_db_path()}"

    @property
    def use_fake_provider(self) -> bool:
        return self.provider.strip().lower() == FAKE_PROVIDER
