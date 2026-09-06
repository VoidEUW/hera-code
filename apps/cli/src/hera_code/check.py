"""`hera-code check` — look, and report. Create nothing, change nothing, repair nothing.

**Looking and changing are different verbs**, and a diagnostic that repairs things is one you
cannot use to diagnose. `check` never migrates, never seeds and never writes; when something is
wrong it says what to run, which is almost always `hera-code init`.

Every line follows `docs/tui.md` § Voice: say what is true, and when it is not, say what to do.
*"no model is set on 'local' — add one to ~/.hera/code/config.toml"* beats *"invalid
configuration"*.

It does **not** contact the endpoint. That is a `live` concern and would make `check` hang for
`connect_timeout_s` on a laptop with no network, which is exactly when a person reaches for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from hera_code.config import ConfigError
from hera_code.config import load as load_config
from hera_code.migrations import alembic_config
from hera_code.settings import CodeSettings
from hera_code_home import code_config_path, code_home, sessions_db_path
from hera_home import home, mcp_path, mind_dir, skills_dir
from hera_profiles import MindRepository
from hera_storage import Database, StorageSettings

OK = "ok"
MISSING = "missing"
BROKEN = "broken"


@dataclass
class Finding:
    """One thing looked at."""

    what: str
    state: str
    detail: str = ""
    remedy: str = ""

    @property
    def usable(self) -> bool:
        return self.state == OK

    def line(self) -> str:
        mark = {OK: "ok  ", MISSING: "--  ", BROKEN: "!!  "}[self.state]
        text = f"{mark}{self.what}"
        if self.detail:
            text = f"{text} — {self.detail}"
        if self.remedy:
            text = f"{text}\n      {self.remedy}"
        return text


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return all(finding.usable for finding in self.findings)

    def render(self) -> str:
        return "\n".join(finding.line() for finding in self.findings)


def inspect(settings: CodeSettings | None = None) -> Report:
    """Everything `check` looks at, in the order it is worth reading.

    Shared before own, because a shared directory that is missing is a thing `init` creates and a
    person who runs hera should recognise. Then the config, then the schema.
    """
    settings = settings or CodeSettings()
    report = Report()

    report.findings.append(_directory("~/.hera", home()))
    report.findings.append(_mind())
    report.findings.append(_directory("~/.hera/skills", skills_dir(), counted="skill"))
    report.findings.append(_file("~/.hera/mcp.json", mcp_path()))
    report.findings.append(_directory("~/.hera/code", code_home()))
    report.findings.append(_config())
    report.findings.append(_schema(settings))
    return report


def _directory(label: str, path: Path, *, counted: str = "") -> Finding:
    if not path.is_dir():
        return Finding(label, MISSING, "not created yet", "run: hera-code init")
    if not counted:
        return Finding(label, OK, str(path))
    found = sum(1 for child in path.iterdir() if child.is_dir())
    plural = "" if found == 1 else "s"
    return Finding(label, OK, f"{found} {counted}{plural}")


def _file(label: str, path: Path) -> Finding:
    if not path.is_file():
        return Finding(label, MISSING, "not created yet", "run: hera-code init")
    return Finding(label, OK, str(path))


def _mind() -> Finding:
    mind = MindRepository(mind_dir())
    if not mind.initialised:
        return Finding("~/.hera/mind", MISSING, "not created yet", "run: hera-code init")
    regions = len(mind.read_all())
    return Finding("~/.hera/mind", OK, f"{regions} regions, shared with hera")


def _config() -> Finding:
    """The endpoint, without asking it anything.

    A config with no model set is `broken` rather than `missing`: the file is there and a person
    edited it, so the useful sentence names the endpoint and the field.
    """
    try:
        config = load_config()
    except ConfigError as exc:
        return Finding(
            "~/.hera/code/config.toml",
            BROKEN,
            str(exc),
            f"fix it by hand: {code_config_path()}",
        )

    entry = config.active()
    if entry is None:
        return Finding(
            "~/.hera/code/config.toml",
            BROKEN,
            "no endpoint is registered",
            f"add one to {code_config_path()}",
        )
    if not entry.model:
        return Finding(
            "~/.hera/code/config.toml",
            BROKEN,
            f"no model is set on {entry.name!r}",
            f'add `model = "..."` under [[providers]] in {code_config_path()}',
        )
    seeded = "" if code_config_path().is_file() else " (seeded; not written yet)"
    return Finding(
        "endpoint",
        OK,
        f"{entry.name} — {entry.model} at {entry.base_url}{seeded}",
    )


def _schema(settings: CodeSettings) -> Finding:
    """Whether the database is at head, without moving it there."""
    if not sessions_db_path().is_file():
        return Finding("sessions.sqlite3", MISSING, "not created yet", "run: hera-code init")

    database = Database(StorageSettings(url=settings.database_url()))
    try:
        script = ScriptDirectory.from_config(alembic_config(database))
        head = script.get_current_head()
        with database.engine.connect() as connection:
            stamped = MigrationContext.configure(connection).get_current_heads()
    except Exception as exc:
        return Finding("sessions.sqlite3", BROKEN, str(exc))
    finally:
        database.dispose()

    if not stamped:
        return Finding("sessions.sqlite3", MISSING, "no schema yet", "run: hera-code init")
    if head not in stamped:
        return Finding(
            "sessions.sqlite3",
            BROKEN,
            f"at {', '.join(stamped)}, this build knows {head}",
            "run: hera-code init  (or check out the branch that has it)",
        )
    return Finding("sessions.sqlite3", OK, f"schema at {head}")
