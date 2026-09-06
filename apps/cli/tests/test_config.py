"""``~/.hera/code/config.toml``: where an endpoint comes from, and what wins.

The promise this file makes is a sequence — hera's endpoints, then the environment, then the file
forever — and each step of it is a test below. The one that matters most is *the file wins*: a
setting you can change and that quietly does not apply is worse than one that overrides a
variable, and nothing but a test keeps that true.
"""

from __future__ import annotations

import stat
import tomllib
from pathlib import Path

import pytest

from hera_code.config import (
    CodeConfig,
    ConfigError,
    ProviderEntry,
    load,
    save,
    validate_provider_name,
)
from hera_code_home import code_config_path
from hera_home import config_path as hera_config_path


def test_a_fresh_install_is_seeded_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a person finds is the right shape to correct, not an empty form."""
    monkeypatch.setenv("HERA_PROVIDER_BASE_URL", "http://192.168.1.5:8000/v1")
    monkeypatch.setenv("HERA_PROVIDER_MODEL", "some-model")

    config = load()
    entry = config.active()

    assert entry is not None
    assert entry.base_url == "http://192.168.1.5:8000/v1"
    assert entry.model == "some-model"


def test_seeding_does_not_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """`load` produces a value; `save` writes. A read-only run must not create a file."""
    load()
    assert not code_config_path().exists()


def test_heras_endpoints_are_borrowed_before_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An endpoint registered for hera is one hera-code can use.

    Asking somebody to type the same URL twice would be a poor reason to keep two files.
    """
    monkeypatch.setenv("HERA_PROVIDER_BASE_URL", "http://from-the-environment/v1")
    _write_hera_config(
        """
        active_provider = "workstation"

        [[providers]]
        name = "workstation"
        base_url = "http://192.168.1.9:1234/v1"
        active_model = "qwen3.6-35b"
        """
    )

    entry = load().active()

    assert entry is not None
    assert entry.name == "workstation"
    assert entry.base_url == "http://192.168.1.9:1234/v1"
    assert entry.model == "qwen3.6-35b"


def test_heras_active_endpoint_becomes_ours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one known to work should be the one hera-code starts on."""
    _write_hera_config(
        """
        active_provider = "second"

        [[providers]]
        name = "first"
        base_url = "http://first/v1"
        active_model = "a"

        [[providers]]
        name = "second"
        base_url = "http://second/v1"
        active_model = "b"
        """
    )

    config = load()
    entry = config.active()

    assert entry is not None
    assert entry.name == "second"
    assert {e.name for e in config.providers} == {"first", "second"}


def test_heras_older_bare_model_field_is_understood() -> None:
    """A person may have either shape on disk; both are read."""
    _write_hera_config(
        """
        [[providers]]
        name = "old"
        base_url = "http://old/v1"
        model = "qwen"
        """
    )

    entry = load().active()

    assert entry is not None
    assert entry.model == "qwen"


def test_an_unreadable_hera_config_means_nothing_to_borrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hera's file belongs to another application and may change shape.

    Anything unreadable there means *nothing to borrow*, never an error — failing to start because
    a sibling application's optional file has a new field would be absurd.
    """
    monkeypatch.setenv("HERA_PROVIDER_MODEL", "from-the-environment")
    _write_hera_config("this is not [ valid toml")

    entry = load().active()

    assert entry is not None
    assert entry.model == "from-the-environment"


def test_the_file_wins_after_it_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """**The load-bearing promise of this module.**

    Once written, neither hera's file nor the environment is consulted again. A setting you can
    change and that quietly does not apply is worse than one that overrides a variable.
    """
    save(
        CodeConfig(
            providers=[ProviderEntry(name="mine", base_url="http://mine/v1", model="chosen")],
            active_provider="mine",
        )
    )
    monkeypatch.setenv("HERA_PROVIDER_MODEL", "ignored")
    _write_hera_config(
        """
        [[providers]]
        name = "heras"
        base_url = "http://heras/v1"
        active_model = "also-ignored"
        """
    )

    entry = load().active()

    assert entry is not None
    assert entry.model == "chosen"


def test_a_config_round_trips(config: CodeConfig) -> None:
    save(config)
    assert load() == config


def test_an_api_key_with_a_quote_in_it_survives() -> None:
    """The case hand-rolled TOML serialisation breaks on, and why `tomli-w` is a dependency."""
    awkward = 'sk-"quoted"-\\backslash\\-key'
    save(
        CodeConfig(
            providers=[ProviderEntry(name="x", model="m", api_key=awkward)],
            active_provider="x",
        )
    )
    entry = load().active()
    assert entry is not None
    assert entry.api_key == awkward


def test_the_file_is_not_world_readable() -> None:
    """It holds an API key."""
    save(CodeConfig(providers=[ProviderEntry(name="x", model="m", api_key="secret")]))
    mode = stat.S_IMODE(code_config_path().stat().st_mode)
    assert mode == 0o600, f"config.toml is {mode:o}, and it holds an API key"


def test_defaults_are_not_written_for_the_tuning_fields() -> None:
    """The file means *what I decided*, not *what the defaults were the day I installed it*.

    A default this project later improves would otherwise be silently dead for everybody who has
    already run hera-code — which is the opposite of what *the file wins* protects.
    """
    save(CodeConfig(providers=[ProviderEntry(name="x", model="m")]))
    written = tomllib.loads(code_config_path().read_text())
    assert "timeout_s" not in written["providers"][0]
    assert "connect_timeout_s" not in written["providers"][0]


def test_a_tuning_value_that_was_set_is_written() -> None:
    save(CodeConfig(providers=[ProviderEntry(name="x", model="m", timeout_s=30.0)]))
    written = tomllib.loads(code_config_path().read_text())
    assert written["providers"][0]["timeout_s"] == 30.0


def test_unparseable_toml_is_reported_with_the_path() -> None:
    """A person who hand-edited it into a broken state needs the parser's own complaint."""
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text("[[providers]\nbroken")
    with pytest.raises(ConfigError, match="could not be read"):
        load()


def test_an_invalid_entry_is_reported() -> None:
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text('[[providers]]\nname = "Not A Slug!"\n')
    with pytest.raises(ConfigError, match="not a valid hera-code configuration"):
        load()


def test_an_active_provider_that_was_deleted_falls_back_to_the_first() -> None:
    """A working install should not be left with no model because of a hand edit."""
    config = CodeConfig(
        providers=[ProviderEntry(name="only", model="m")], active_provider="deleted"
    )
    entry = config.active()
    assert entry is not None
    assert entry.name == "only"


def test_a_file_with_every_endpoint_deleted_keeps_the_appearance() -> None:
    """Somebody who removed the endpoints should not also lose the setting above them."""
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text('[terminal]\nappearance = "dark"\n')
    config = load()
    assert config.terminal.appearance == "dark"
    assert config.providers, "the endpoints should have been re-seeded"


@pytest.mark.parametrize("bad", ["", "  ", "Has Spaces", "with/slash", "emoji✨", "dot.ted"])
def test_a_provider_name_is_a_slug(bad: str) -> None:
    with pytest.raises(ValueError, match="lowercase letters"):
        validate_provider_name(bad)


@pytest.mark.parametrize(
    ("given", "expected"),
    [("Local", "local"), ("  local  ", "local"), ("LM-Studio_2", "lm-studio_2")],
)
def test_a_name_is_normalised_rather_than_refused(given: str, expected: str) -> None:
    """Case and surrounding space are corrected, not complained about.

    Refusing `Local` would teach nothing — there is one obvious thing the person meant. What is
    refused is a character that cannot be normalised into a slug, because guessing there would
    silently rename somebody's endpoint.
    """
    assert validate_provider_name(given) == expected


def _write_hera_config(body: str) -> Path:
    """hera's own `~/.hera/config.toml`, which hera-code reads exactly once."""
    path = hera_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path
