"""`check` looks and reports. It creates nothing, changes nothing, and repairs nothing.

**Looking and changing are different verbs**, and a diagnostic that repairs things is one you
cannot use to diagnose. The first test below is the one that matters; the rest are about the
sentences being useful.
"""

from __future__ import annotations

from uuid import UUID

from hera_code.check import BROKEN, MISSING, OK, Finding, Report, inspect
from hera_code.config import CodeConfig
from hera_code.settings import CodeSettings
from hera_code_home import code_config_path, sessions_db_path
from hera_home import home
from hera_profiles import MindRepository
from hera_storage import Database


def test_it_changes_nothing(
    database: Database, owner_id: UUID, config: CodeConfig, settings: CodeSettings
) -> None:
    """**The load-bearing test.** A diagnostic with side effects is one nobody can trust."""
    from hera_code.boot import prepare
    from hera_home import mind_dir

    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)
    before = _fingerprint()

    inspect(settings)

    assert _fingerprint() == before


def test_it_does_not_create_a_missing_home(settings: CodeSettings) -> None:
    """Run against nothing, it reports nothing — it does not helpfully seed."""
    inspect(settings)
    assert not home().exists()


def test_a_fresh_install_reports_usable(
    database: Database, owner_id: UUID, config: CodeConfig, settings: CodeSettings
) -> None:
    from hera_code.boot import prepare
    from hera_home import mind_dir

    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)

    report = inspect(settings)

    assert report.usable, report.render()
    assert all(finding.state == OK for finding in report.findings)


def test_an_empty_home_says_what_to_run(settings: CodeSettings) -> None:
    report = inspect(settings)

    assert not report.usable
    assert "hera-code init" in report.render()


def test_a_broken_config_names_the_file(settings: CodeSettings) -> None:
    """A person who hand-edited it into a broken state needs the parser's own complaint and the
    path, not `invalid configuration`."""
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text("[[providers]\nbroken")

    finding = _finding(inspect(settings), "config.toml")

    assert finding.state == BROKEN
    assert str(code_config_path()) in finding.line()


def test_an_endpoint_with_no_model_is_named(settings: CodeSettings) -> None:
    """*no model is set on 'local'* beats *invalid configuration* — `docs/tui.md` § Voice."""
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text(
        'active_provider = "local"\n\n[[providers]]\nname = "local"\nmodel = ""\n'
    )

    finding = _finding(inspect(settings), "config.toml")

    assert finding.state == BROKEN
    assert "'local'" in finding.detail
    assert finding.remedy


def test_a_missing_database_is_missing_rather_than_broken(settings: CodeSettings) -> None:
    """Two different sentences. *Not created yet* is answered by `init`; *broken* is not."""
    assert not sessions_db_path().exists()
    finding = _finding(inspect(settings), "sessions.sqlite3")
    assert finding.state == MISSING


def test_it_does_not_contact_the_endpoint(settings: CodeSettings, config: CodeConfig) -> None:
    """The config points at `http://localhost:1/v1`, where nothing is listening.

    If `check` dialled it, this test would take `connect_timeout_s` to fail — and a person on a
    train reaching for a diagnostic is exactly who should not wait for a socket.
    """
    from hera_code.config import save

    save(config)
    finding = _finding(inspect(settings), "endpoint")
    assert finding.state == OK


def _finding(report: Report, what: str) -> Finding:
    for finding in report.findings:
        if what in finding.what:
            return finding
    raise AssertionError(f"no finding about {what!r} in:\n{report.render()}")


def _fingerprint() -> dict[str, tuple[int, int]]:
    return {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(home().rglob("*"))
        if path.is_file()
    }
