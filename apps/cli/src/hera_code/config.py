"""``~/.hera/code/config.toml`` — hera-code's own settings.

A file rather than a table, for the reason `ARCHITECTURE.md` already lists it as one: there must
be nothing in `~/.hera` you cannot open in an editor. A misconfigured endpoint is something you
can fix with `vim` when the terminal will not start because of it.

**Where an endpoint comes from, and in what order.** The file is *seeded* the first time it is
written, from two sources in this order:

1. **hera's own ``~/.hera/config.toml``**, if it exists and has endpoints in it. An endpoint
   registered for hera is one hera-code can use, and asking somebody to type the same URL twice
   because the two applications keep separate files would be a poor reason to keep them separate.
2. **``HERA_PROVIDER_*``**, otherwise. A fresh install then finds the intended deployment already
   filled in rather than an empty form.

**After that this file wins**, and hera's is never read again. A setting you change here and that
quietly does not apply is worse than one that overrides a variable — and a live merge would mean
changing hera's active endpoint silently changed hera-code's.

That is the seam ADR 5 describes: the endpoints are shared, the *choice* is not. Which one is
active is a different decision in a terminal than in a chat window.

**Several endpoints, one active.** There is no target model (ADR 2), so this is a list rather
than a set of fields, and `kind` selects the adapter rather than describing a vendor.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator

from hera_code_home import code_config_path
from hera_home import config_path as hera_config_path
from hera_providers import ProviderSettings

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")

ProviderKind = Literal["qwen", "openai-compatible"]
"""Which stream adapter an endpoint gets, and nothing else.

Deliberately **not** a vendor list. hera's equivalent names eleven vendors because it draws a
small icon beside each; there is no icon in a terminal, and the only thing this field can change
is how the response is parsed. `qwen` lifts a reasoning channel out of `reasoning_content` or
`<think>` tags; `openai-compatible` is the bare provider for an endpoint that has neither.

`qwen` is the default because a local Qwen is the deployment hera-code is developed against —
not because it is a target model. Nothing above `hera_providers` may assume one (ADR 2).

**Today both kinds select the same adapter**, and that is worth saying plainly rather than hiding
behind a branch that does nothing: `QwenAdapter` lifts a reasoning channel out *when there is one*
and is inert when there is not, so an endpoint with neither gets byte-identical output from it.
The field is recorded because the moment a second adapter is needed it is what selects one, and a
config format that has to grow a field later is one every existing install must be migrated
through.
"""

Appearance = Literal["system", "light", "dark"]


def validate_provider_name(name: str) -> str:
    """Lowercase, digits, ``-`` and ``_``. Raises ``ValueError`` otherwise."""
    cleaned = name.strip().lower()
    if not cleaned or set(cleaned) - SLUG_CHARS:
        raise ValueError("a provider name uses lowercase letters, digits, - and _")
    return cleaned


class ProviderEntry(BaseModel):
    """One endpoint hera-code can be pointed at."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: ProviderKind = "qwen"
    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    """Empty for a local server, which is the intended deployment. This is why the file is
    written with mode 600."""

    model: str = ""
    """What travels in the request body's ``model`` field. Has to match what the endpoint calls
    it. Empty is a configuration that cannot run, and :func:`load` does not reject it — `check`
    reports it, because a person half-way through editing the file should get a sentence rather
    than a parse error."""

    embedding_model: str = ""
    """Empty means embeddings are off and skill retrieval falls back to keyword overlap, which
    is ADR 5's supported path rather than a degraded one."""

    timeout_s: float = 600.0
    """How long this endpoint may be **silent** — not how long a turn may take. On a streamed
    answer it is measured between one piece of the response and the next, so what it bounds is
    loading the weights and prefilling the prompt."""

    connect_timeout_s: float = 5.0
    """Short on purpose: *nothing is listening* should be answered immediately rather than after
    ten minutes of the read timeout above. This is the one that catches a wrong port."""

    @field_validator("name")
    @classmethod
    def _usable_name(cls, name: str) -> str:
        return validate_provider_name(name)

    def settings(self) -> ProviderSettings:
        """As ``hera_providers`` wants it."""
        return ProviderSettings(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            embedding_model=self.embedding_model,
            timeout_s=self.timeout_s,
            connect_timeout_s=self.connect_timeout_s,
        )


class TerminalConfig(BaseModel):
    """What the terminal does, for the things it cannot reliably detect."""

    model_config = ConfigDict(frozen=True)

    appearance: Appearance = "system"
    """`system` detects — `COLORFGBG`, then an OSC 11 query. The override exists because
    detection cannot be relied on and getting it wrong means brass on a light terminal, which is
    unreadable. A person should not have to argue with it (``docs/tui.md`` § Colour)."""


class CodeConfig(BaseModel):
    """Everything in ``~/.hera/code/config.toml``."""

    model_config = ConfigDict(frozen=True)

    providers: list[ProviderEntry] = Field(default_factory=list)
    active_provider: str = ""
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)

    def active(self) -> ProviderEntry | None:
        """The endpoint in use, or the first one, or nothing.

        Falling back to the first rather than to nothing: an ``active_provider`` naming an entry
        somebody deleted by hand should not leave a working install with no model.
        """
        for entry in self.providers:
            if entry.name == self.active_provider:
                return entry
        return self.providers[0] if self.providers else None


class ConfigError(RuntimeError):
    """``config.toml`` exists and cannot be used.

    Not caught anywhere that would swallow it: a person who has hand-edited the file into a state
    that will not parse needs the parser's own complaint, not a default quietly taking its place.
    """


def load(path: Path | None = None) -> CodeConfig:
    """Read the file, seeding it from hera and then the environment when there is nothing yet.

    Seeding produces a value; it does not write. :func:`save` is what writes, and `init` is what
    calls it — so `check` and `-p` can read a seeded config without a read-only run creating a
    file as a side effect.
    """
    path = path if path is not None else code_config_path()
    if not path.is_file():
        return _seeded()

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path} could not be read: {exc}") from exc

    try:
        config = CodeConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"{path} is not a valid hera-code configuration: {exc}") from exc

    if not config.providers:
        # Seeded, but the rest of the file is kept: somebody who deleted every endpoint by hand
        # should not also lose the appearance they set.
        seeded = _seeded()
        return seeded.model_copy(update={"terminal": config.terminal})
    return config


def save(config: CodeConfig, path: Path | None = None) -> None:
    """Write the file, creating the directory if it is not there yet.

    Written whole and replaced atomically. A half-written ``config.toml`` is a hera-code that will
    not start, and the moment it happens is the moment somebody was changing the endpoint because
    the old one had stopped working.

    **Mode 600**, because this file holds an API key. Set on the temporary file before the content
    is written rather than on the target afterwards, so the key is never briefly world-readable.
    """
    path = path if path is not None else code_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = tomli_w.dumps(_writable(config))
    temporary = path.with_suffix(f"{path.suffix}.writing")
    temporary.touch(mode=0o600, exist_ok=True)
    temporary.chmod(0o600)
    temporary.write_text(_HEADER + body, encoding="utf-8")
    temporary.replace(path)


TUNING_FIELDS = ("timeout_s", "connect_timeout_s")
"""Fields written **only when they differ from the default**.

The rest of an entry is written whether or not it was changed, because the rest of an entry is
what you came to the file to read: an endpoint with no ``base_url`` in it is a worse file even
when the URL is the default one.

These two are different, and the difference cost hera a real afternoon. The file is seeded once
and wins afterwards, so it records the defaults of whichever version happened to write it first —
which means a default this project later improves is silently dead for everybody who has already
run it. That is the opposite of what *the file wins* is supposed to protect. Omitting them unless
they were set makes the file mean *what I decided* rather than *what the defaults were the day I
installed it*.
"""


def _writable(config: CodeConfig) -> dict[str, Any]:
    """The document as it goes to disk. See :data:`TUNING_FIELDS`."""
    document = config.model_dump(mode="python")
    blank = ProviderEntry(name="seed")
    for entry, dumped in zip(config.providers, document["providers"], strict=True):
        for field in TUNING_FIELDS:
            if getattr(entry, field) == getattr(blank, field):
                dumped.pop(field, None)
    return document


def _seeded() -> CodeConfig:
    """What a file that does not exist yet would say.

    hera's endpoints first, the environment second. Wrapped so that a bad value in either reads
    as a configuration problem rather than a traceback — an environment variable is still
    somebody's hand-edited input, and ``HERA_PROVIDER_MODEL=""`` is a plausible accident.
    """
    try:
        borrowed = _from_hera()
        if borrowed:
            return CodeConfig(providers=borrowed, active_provider=borrowed[0].name)
        return CodeConfig(providers=[_from_environment()], active_provider="local")
    except ValueError as exc:
        raise ConfigError(f"the environment describes an unusable provider: {exc}") from exc


def _from_environment() -> ProviderEntry:
    settings = ProviderSettings()
    return ProviderEntry(
        name="local",
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        embedding_model=settings.embedding_model,
        timeout_s=settings.timeout_s,
        connect_timeout_s=settings.connect_timeout_s,
    )


def _from_hera(path: Path | None = None) -> list[ProviderEntry]:
    """hera's registered endpoints, translated into ours. Empty when there is nothing to borrow.

    **Read once, at seed time, and never again.** After that this application's file wins, so
    changing hera's active endpoint cannot silently change hera-code's.

    Deliberately forgiving. hera's file belongs to a different application that is free to change
    its shape, and anything unreadable here means *nothing to borrow* rather than an error —
    hera-code seeding from the environment instead is a perfectly good outcome, and failing to
    start because a sibling application's optional file has a new field would be absurd.

    It reads hera's ``models``/``active_model`` pair as well as the older bare ``model``, because
    a person may have either on disk.
    """
    path = path if path is not None else hera_config_path()
    if not path.is_file():
        return []
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []

    entries: list[ProviderEntry] = []
    providers = raw.get("providers")
    if not isinstance(providers, list):
        return []
    for item in providers:
        if not isinstance(item, dict):
            continue
        entry = _borrow(item)
        if entry is not None:
            entries.append(entry)

    # hera's active endpoint should be hera-code's starting choice, since it is the one known to
    # work. Ordering rather than a separate field, because `active()` falls back to the first.
    wanted = raw.get("active_provider")
    if isinstance(wanted, str) and wanted:
        entries.sort(key=lambda entry: entry.name != wanted)
    return entries


def _borrow(item: dict[str, Any]) -> ProviderEntry | None:
    """One of hera's provider tables as one of ours, or ``None`` if it is not usable."""
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return None
    model = item.get("active_model") or item.get("model") or ""
    if not model:
        models = item.get("models")
        if isinstance(models, list) and models and isinstance(models[0], dict):
            model = models[0].get("id") or ""
    try:
        return ProviderEntry(
            name=name,
            base_url=str(item.get("base_url") or "http://localhost:1234/v1"),
            api_key=str(item.get("api_key") or ""),
            model=str(model),
            embedding_model=str(item.get("embedding_model") or ""),
        )
    except ValueError:
        # A name hera allows and we do not, or a field of the wrong type. Skipped rather than
        # fatal -- see the docstring above.
        return None


_HEADER = """# hera-code's settings. Safe to edit by hand.
#
# Seeded once from hera's ~/.hera/config.toml if it existed, and from HERA_PROVIDER_* otherwise.
# This file wins afterwards: hera's is never read again.
#
#   kind = "qwen"               lifts a reasoning channel out of reasoning_content or <think>
#   kind = "openai-compatible"  for an endpoint that has neither

"""
