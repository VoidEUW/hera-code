"""Where every package is joined up.

The one place in the system that knows all of them. Each library takes what it needs as an
injected dependency and names no concrete class, which is what lets the whole application be
exercised against ``FakeProvider`` — so this module is also the seam the tests replace.

Two wirings are worth pointing at, because they are the ones the layering rules exist for.

``hera_chats`` may not learn what hera-code's tools are, so the **name** of the tool that suspends
a turn travels through ``ChatsSettings.asking_tools``, and the key a tool reads its session id
from travels through ``ChatsSettings.chat_meta_key``. Both are constants exported by
``hera_code_mcp``, which imports nothing of ours. The application is what makes the two agree.

``hera_skillsets`` may not import ``hera_providers``, so retrieval would reach embeddings through
a port — and in v0.1 it does not, deliberately. ``SkillRouter.select()`` is synchronous because
everything else it does is a file read, and ``hera_chats`` runs it in a worker thread. ADR 5 names
keyword overlap as the supported fallback, so the cost of leaving this is *worse ranking*, not a
missing feature.

**Nothing here is a patch to a vendored package.** Every redirect below — the database URL, the
mind path, the MCP config path, the built-in server, the asking tool — is a setting or an
argument that already existed. If something ever cannot be done this way, that is
[ADR 1](../../../docs/adr/0001-a-uv-workspace-with-heras-packages-vendored.md) to re-open.
"""

from __future__ import annotations

from dataclasses import dataclass

from hera_chats import ChatsSettings, TurnOrchestrator
from hera_code.config import CodeConfig
from hera_code.config import load as load_config
from hera_code.files import WorkingTree
from hera_code.settings import CodeSettings
from hera_code.shell import WorkingShell
from hera_code_mcp import ASK_TOOL, BUILTIN_SERVER_NAME, build_server
from hera_code_workspace import Workspace, discover
from hera_home import mind_dir, skills_dir
from hera_permissions import Decision, PermissionSet, Policy, Rule
from hera_profiles import MindRepository, PromptBuilder
from hera_providers import (
    FakeProvider,
    OpenAICompatibleProvider,
    Provider,
    ProviderSettings,
    QwenAdapter,
)
from hera_skillsets import SkillLibrary, SkillRouter
from hera_storage import Database, StorageSettings
from hera_tools import ToolRegistry, ToolsSettings

DEFAULT_POLICY = Policy(
    base=PermissionSet(
        rules=[
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__read",
                decision=Decision.ALLOW,
                reason="reads a file inside the working tree and changes nothing",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__glob",
                decision=Decision.ALLOW,
                reason="lists files inside the working tree and changes nothing",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__grep",
                decision=Decision.ALLOW,
                reason="searches inside the working tree and changes nothing",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__graph_*",
                decision=Decision.ALLOW,
                reason="reads the code index and changes nothing",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__todo_*",
                decision=Decision.ALLOW,
                reason="edits the todo list, which is yours to read and change back",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__note_*",
                decision=Decision.ALLOW,
                reason="writes a note under .hera, never into your source",
            ),
            # Spelled out rather than left to the fallback. The fallback would decide the same
            # thing, and would decide it with no `reason` -- which is the field the permission
            # card's third line renders and the one `--yes` prints. ADR 11 makes that field
            # load-bearing twice, so the three calls a person sees most often each have one.
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__write",
                decision=Decision.ASK,
                reason="replaces a file in your source",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__edit",
                decision=Decision.ASK,
                reason="changes a file in your source",
            ),
            Rule(
                pattern=f"{BUILTIN_SERVER_NAME}__bash",
                decision=Decision.ASK,
                reason="runs a command in your working tree",
            ),
        ]
    ),
    fallback=Decision.ASK,
)
"""What an install with no permission rules of its own gets, and why it asks so much.

**Reads are allowed; anything that changes a file is not.** hera allows all of her own tools
without a card because they are bounded — the worst one writes into her own scratchpad. Nothing
about that reasoning survives a tool with a shell in it, or one that rewrites a file in a
repository somebody is mid-refactor on. So `write`, `edit` and `bash` fall through to `ask`, and so
does every foreign server, which is the right default for a tool nobody has an opinion about yet.

**A coding agent therefore asks more than a chat agent does, and that is the decision rather than
an accident.** Somebody who finds it noisy has *Always allow*, which writes a rule. Somebody who
finds it too quiet has no recourse at all — they find out from a diff. Between a default that
annoys and a default that surprises, the annoying one is recoverable.

`todo_*` and `note_*` are allowed despite writing, because what they write is `<root>/.hera` —
a directory whose whole promise is that it is the agent's and that a person can read and revert it
(ADR 7). A card before every `todo_set` would fire several times a turn and teach a person to
click through cards without reading them, which is the failure that matters.

The rules are seeded, not hard-coded: this is the *default*, and `hera_permissions` is what a
person's own rules are loaded into on top of it.
"""


@dataclass
class Services:
    """Everything a turn reaches for, built once at launch.

    A dataclass rather than a container framework: there are eight of these, they are all
    singletons, and the wiring is a hundred lines that should be readable top to bottom.
    """

    settings: CodeSettings
    config: CodeConfig
    workspace: Workspace
    database: Database
    mind: MindRepository
    builder: PromptBuilder
    library: SkillLibrary
    router: SkillRouter
    registry: ToolRegistry | None
    provider: Provider
    orchestrator: TurnOrchestrator

    owns_provider: bool = False
    """Whether closing this container should close the provider.

    Defaults to **False**, so ownership is something the creator claims rather than something a
    hand-built container inherits. :func:`build_services` sets it when it constructed the provider
    itself; a test passing its own ``FakeProvider`` keeps it, and nothing closes what it did not
    open.
    """

    @property
    def model(self) -> str:
        """The model name requests are sent with."""
        return self.orchestrator.settings.model

    def always_allow(self, tool: str, reason: str = "") -> None:
        """Write one rule, because a person said *always*.

        **Not persisted yet** — the rule lives for this session. Writing it to disk needs a file
        for a person's own rules to live in, and inventing one here would be inventing a format
        that `check` cannot report on and nothing can edit. That is v0.2.0, and the terminal says
        *always allowing* rather than *always allowed* until then, because the two are different
        promises.
        """
        if self.registry is None:
            return
        rule = Rule(
            pattern=tool,
            decision=Decision.ALLOW,
            reason=reason or "you allowed this",
        )
        widened = Policy(
            base=PermissionSet(rules=[*self.registry.policy.base.rules, rule]),
            fallback=self.registry.policy.fallback,
        )
        self.registry = self.registry.with_policy(widened)
        self.orchestrator.registry = self.registry

    def allow_what_would_be_asked(self) -> None:
        """Apply `--yes` — see :func:`said_yes_in_advance` for the line it must not cross.

        `with_policy` shares the servers rather than reconnecting them, so this costs nothing
        even when a subprocess server is already running.
        """
        if self.registry is None:
            return
        self.registry = self.registry.with_policy(said_yes_in_advance(self.registry.policy))
        self.orchestrator.registry = self.registry

    async def aclose(self) -> None:
        """Release everything holding a connection or a subprocess open."""
        if self.registry is not None:
            await self.registry.aclose()
        if self.owns_provider:
            await self.provider.aclose()
        self.database.dispose()


def build_services(
    settings: CodeSettings | None = None,
    *,
    config: CodeConfig | None = None,
    provider: Provider | None = None,
    database: Database | None = None,
    registry: ToolRegistry | None = None,
    policy: Policy | None = None,
    workspace: Workspace | None = None,
) -> Services:
    """Assemble the application.

    Every argument is an override and every override exists for the tests: a scripted provider, an
    in-memory database, a registry with no servers. A real launch passes none of them.
    """
    settings = settings or CodeSettings()
    config = config if config is not None else load_config()
    database = database or Database(StorageSettings(url=settings.database_url()))

    entry = config.active()
    provider_settings = entry.settings() if entry is not None else ProviderSettings()
    injected = provider is not None
    if provider is None:
        provider = _provider_for(settings, config)

    # The mind and the skills are the shared ~/.hera, and both defaults are left alone -- that is
    # what "shared with hera" means in code (ADR 5).
    mind = MindRepository(mind_dir())
    builder = PromptBuilder(mind)
    library = SkillLibrary(skills_dir())
    # No embedder yet. Keyword overlap is ADR 5's supported fallback, so retrieval works; it
    # just ranks worse than it eventually will.
    router = SkillRouter(library)

    workspace = workspace if workspace is not None else discover()
    if registry is None:
        registry = ToolRegistry.open(
            policy=policy if policy is not None else DEFAULT_POLICY,
            settings=ToolsSettings(),
            # hera_code_mcp imports nothing of ours, so the working tree arrives as two ports.
            # It is mounted under its own name -- `code` -- which travels on the server object
            # rather than being written here as well.
            builtin=build_server(
                files=WorkingTree(workspace),
                shell=WorkingShell(workspace),
            ),
        )

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
        owns_provider=not injected,
        orchestrator=TurnOrchestrator(
            provider=provider,
            builder=builder,
            router=router,
            registry=registry,
            settings=ChatsSettings(
                model=provider_settings.model,
                # The one place the asking tool is named to the turn layer. `hera_chats` does not
                # know what a hera-code tool is and must not learn; it takes the qualified name
                # and suspends on it. Qualified here because `hera_tools` namespaces by server
                # name, and that name travels on the server object rather than being written
                # twice.
                asking_tools=(f"{BUILTIN_SERVER_NAME}__{ASK_TOOL}",),
            ),
        ),
    )


def _provider_for(settings: CodeSettings, config: CodeConfig) -> Provider:
    """The endpoint, or the scripted stand-in.

    ``HERA_CODE_PROVIDER=fake`` runs the whole loop with no endpoint. It answers nothing useful —
    ``FakeProvider`` with no scripted turns raises ``FakeProviderExhausted`` on the first request —
    which is correct: a test scripts it, and a person who set the variable by accident should find
    out immediately rather than get plausible nonsense.
    """
    if settings.use_fake_provider:
        return FakeProvider()

    entry = config.active()
    provider_settings = entry.settings() if entry is not None else ProviderSettings()
    # One adapter for both kinds today, and that is worth saying rather than hiding behind a
    # branch that does nothing. `QwenAdapter` lifts a reasoning channel out of `reasoning_content`
    # or `<think>` tags *when they are there*, and is inert when they are not -- so an endpoint
    # with neither gets byte-identical output from it. `kind` is recorded because the moment a
    # second adapter is needed it is the field that selects one, and a config format that has to
    # grow a field later is one every existing install has to be migrated through.
    return OpenAICompatibleProvider(provider_settings, adapter_factory=QwenAdapter)


def said_yes_in_advance(policy: Policy) -> Policy:
    """The same policy with every **ask** turned into an allow, and every **deny** left alone.

    What `--yes` does, and ADR 11 is explicit about the line it must not cross: a person saying
    *yes in advance* is answering the cards they would have been shown. It is not switching off
    the containment guard, which is an invariant rather than a preference — a flag that could
    reach `deny` would make it one.

    The `reason` travels with each flipped rule, because it is what the caller prints when it
    says which calls it allowed. A CI log should show *what was permitted*, not only what ran.
    """
    return Policy(
        base=PermissionSet(
            rules=[
                Rule(pattern=rule.pattern, decision=Decision.ALLOW, reason=rule.reason)
                if rule.decision is Decision.ASK
                else rule
                for rule in policy.base.rules
            ]
        ),
        fallback=(Decision.ALLOW if policy.fallback is Decision.ASK else policy.fallback),
    )
