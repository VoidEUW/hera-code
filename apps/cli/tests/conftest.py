"""Fixtures for the application suite.

The whole application against `FakeProvider` and no MCP servers, so the config, the boot
sequence, the prompt slot, the turn loop and the persistence are all exercised — and none of it
needs a model, a network or a subprocess.

**`HERA_HOME` is repointed for every test, automatically.** Nothing here may write into a real
`~/.hera`: this suite creates a mind repository, seeds a config file and migrates a database, and
doing any of that to somebody's actual install would be unforgivable. The fixture is `autouse`
rather than something a test opts into, because the one that forgets is the one that does it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from code_support import Scripted

from hera_chats import ChatsSettings, TurnOrchestrator
from hera_code.config import CodeConfig, ProviderEntry

# Registers every table into the shared MetaData before the schema is created.
from hera_code.models import ALL_TABLES  # noqa: F401
from hera_code.settings import CodeSettings
from hera_code.wiring import DEFAULT_POLICY, Services
from hera_code_workspace import Workspace
from hera_home import mind_dir, skills_dir
from hera_profiles import MindRepository, PromptBuilder
from hera_skillsets import SkillLibrary, SkillRouter
from hera_storage import Database, StorageSettings
from hera_tools import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Every test gets its own `~/.hera`, and no test can reach the real one."""
    home = tmp_path / "home"
    monkeypatch.setenv("HERA_HOME", str(home))
    # The provider settings are read from the environment when nothing else supplies them, and a
    # developer machine may well have these set. A test that passed only because of somebody's
    # shell is a test that fails in CI.
    for name in ("HERA_PROVIDER_BASE_URL", "HERA_PROVIDER_MODEL", "HERA_PROVIDER_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    # **No test may reach a network, and unsetting the variables above is not enough.** The
    # default `base_url` is `http://localhost:1234/v1`, which is where LM Studio listens — so on
    # a developer machine a test that builds its own provider quietly talks to a real model, and
    # in CI the same test passes because nothing is listening. A test that passes for the wrong
    # reason on one machine and the right reason on another is worse than one that fails.
    #
    # Forcing the scripted provider makes that impossible rather than unlikely. A test that wants
    # a live endpoint marks itself `live` and is never run in CI.
    monkeypatch.setenv("HERA_CODE_PROVIDER", "fake")
    return home


@pytest.fixture
def settings() -> CodeSettings:
    return CodeSettings()


@pytest.fixture
def owner_id(settings: CodeSettings) -> UUID:
    return settings.owner_id


@pytest.fixture
def config() -> CodeConfig:
    """A registered endpoint that is never contacted, so a turn has a model name to send."""
    return CodeConfig(
        providers=[
            ProviderEntry(name="local", base_url="http://localhost:1/v1", model="test-model")
        ],
        active_provider="local",
    )


@pytest.fixture
def database(settings: CodeSettings) -> Iterator[Database]:
    """A real SQLite file under the isolated home, migrated by whoever needs it.

    A file rather than `:memory:` because `boot.prepare` runs alembic against it, and alembic on an
    in-memory database is a different code path from the one that ships.
    """
    sessions = Path(settings.database_url().removeprefix("sqlite:///"))
    sessions.parent.mkdir(parents=True, exist_ok=True)
    db = Database(StorageSettings(url=settings.database_url()))
    yield db
    db.dispose()


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A working tree of its own, so nothing a test does reaches the repository it runs in.

    A real directory rather than `Path.cwd()`: a tool test that wrote a file would otherwise write
    it into hera-code's own checkout, and a `grep` would search this repository's source.
    """
    root = tmp_path / "tree"
    root.mkdir()
    return Workspace(root=root)


@pytest.fixture
def provider() -> Scripted:
    """Scripted by the test. With nothing queued it fails the request, which is what a test that
    forgot to script a turn deserves."""
    return Scripted()


@pytest.fixture
def services(
    settings: CodeSettings,
    config: CodeConfig,
    database: Database,
    provider: Scripted,
    workspace: Workspace,
) -> Services:
    """The application, assembled by hand rather than through `build_services`.

    Built here so a test can queue turns onto the provider afterwards.

    The registry has **no servers and a real policy**, which is exactly what M1 is: nothing is
    mounted until the MCP server lands in M2, but `hera_permissions` is already wired, so a call
    the model invents still goes through the policy and still suspends the turn. `registry=None`
    would skip that path entirely and leave the suspension untested until M2.
    """
    mind = MindRepository(mind_dir())
    builder = PromptBuilder(mind)
    library = SkillLibrary(skills_dir())
    router = SkillRouter(library)
    registry = ToolRegistry([], policy=DEFAULT_POLICY)
    return Services(
        settings=settings,
        config=config,
        workspace=workspace,
        database=database,
        mind=mind,
        builder=builder,
        library=library,
        router=router,
        registry=registry,
        provider=provider,
        orchestrator=TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=ChatsSettings(model="test-model"),
        ),
    )


@pytest.fixture
def prepared(services: Services, owner_id: UUID) -> Services:
    """`services`, with the data directories seeded and the schema migrated."""
    from hera_code.boot import prepare

    prepare(services.database, services.mind, owner_id=owner_id, config=services.config)
    return services


@pytest.fixture
def default_policy() -> object:
    return DEFAULT_POLICY
