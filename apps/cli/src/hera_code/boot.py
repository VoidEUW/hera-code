"""What has to be true before the first turn.

Two jobs: refuse a database whose schema is *ahead* of this build, then make the things a fresh
install needs exist.

**The refusal is about going backwards** — checking out an older branch, or downgrading hera-code,
against a `~/.hera/code` a newer build has already migrated. Alembic notices, but only as
``Can't locate revision identified by '0004'`` under forty lines of its own frames, at a point
where the reader has no reason to connect it to the branch they just switched to. This says it in
a sentence.

**The seeding is split in two, and the split is the whole design of this module.** `~/.hera` is
shared with hera and `~/.hera/code` is not (ADR 5, ADR 7), so a fresh install of either fills in
whatever the other has not:

* Somebody who has run hera finds the mind, the skills and `mcp.json` already there, and
  hera-code adds only its own directory.
* Somebody who has never run hera gets all of it created here, and installing hera later finds it
  already in place.

**Nothing is ever overwritten and nothing is ever deleted.** Every step below asks whether a thing
exists before creating it, and none of them replaces one that does.

There is no pre-v0.1 refusal here. hera has one because it has a version before v0.1; hera-code
does not, and inventing a legacy check for a directory shape that has never existed would be
machinery pretending to have history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError

from hera_code.config import CodeConfig, load, save
from hera_code.migrations import alembic_config, upgrade_to_head
from hera_code.profile import CODING_SLUG, ensure_coding_profile
from hera_code_home import code_config_path, code_home
from hera_home import mcp_path, skills_dir
from hera_profiles import MindRepository
from hera_storage import Database

EMPTY_MCP: dict[str, dict[str, object]] = {"mcpServers": {}}
"""What `mcp.json` says when hera-code writes it.

Empty rather than seeded with a suggestion. A server nobody asked for is one that fails to start
on the first turn and has to be explained; an empty object is a file with an obvious shape to add
to, and `docs/tui.md` already promises that servers come from a JSON file *you* wrote.
"""


class DatabaseAhead(RuntimeError):
    """The database has been migrated by a build newer than this one.

    The remedy is not to move anything aside: nothing is wrong with the directory. The code is
    behind, and either the code or the database has to move — which is a person's decision.
    """


@dataclass
class Prepared:
    """What `init` did, so it can say so and so `check` can say nothing happened.

    Paths rather than a count, because *created ~/.hera/mind* is a useful sentence and *created 4
    things* is not.
    """

    created: list[Path] = field(default_factory=list)
    migrated: bool = False

    @property
    def anything(self) -> bool:
        return bool(self.created) or self.migrated


def check_revision(database: Database) -> None:
    """Refuse a database stamped with a revision this build does not have.

    **Refusing rather than repairing is the point.** Stamping the database back would leave
    columns behind that a later upgrade then fails to add; downgrading it would drop somebody's
    sessions because their shell was in the wrong directory. Both are decisions for a person, so
    this names the revision, names the file, and gives the command.

    A database with no ``alembic_version`` row at all is a fresh one and is fine.
    """
    script = ScriptDirectory.from_config(alembic_config(database))
    with database.engine.connect() as connection:
        stamped = MigrationContext.configure(connection).get_current_heads()

    unknown = [revision for revision in stamped if _missing(script, revision)]
    if not unknown:
        return

    head = script.get_current_head() or "nothing"
    # The engine's own URL rather than the computed path: HERA_STORAGE_URL can point somewhere
    # else entirely, and an error naming a file it did not look at is worse than one naming none.
    where = database.engine.url.database or str(database.engine.url)
    raise DatabaseAhead(
        f"{where} is at migration {', '.join(unknown)}, which this build of hera-code does not "
        f"have — it knows up to {head}. The database was migrated by a newer version, so either "
        f"the code is behind or the wrong branch is checked out.\n"
        f"  Go forward:  git switch <the branch that has {unknown[0]}>\n"
        f"  Or go back:  on that branch, uv run alembic downgrade {head}\n"
        f"Nothing has been changed."
    )


def _missing(script: ScriptDirectory, revision: str) -> bool:
    try:
        return script.get_revision(revision) is None
    except CommandError:
        # What alembic raises for a revision it cannot resolve, which is precisely the case this
        # function exists to report. Anything else is a broken migrations directory and deserves
        # to propagate.
        return True


def prepare(
    database: Database,
    mind: MindRepository,
    *,
    owner_id: UUID,
    config: CodeConfig | None = None,
) -> Prepared:
    """Make a fresh install usable, and leave an existing one alone.

    Idempotent, so it runs on every launch rather than only on the first. Somebody who deletes a
    profile or a mind file should get it back, and discovering on the first turn that there is
    nobody to answer as is a worse way to find out.
    """
    report = Prepared()

    # The directories come first, and specifically before anything touches the database: SQLite
    # will not create `~/.hera/code/sessions.sqlite3` in a directory that does not exist, and what
    # it says instead is `unable to open database file` -- which names neither the directory nor
    # the fix. Ordering is the whole guard; there is nothing to catch.
    _ensure_dir(code_home(), report)
    _ensure_dir(skills_dir(), report)

    check_revision(database)
    before = _revision_of(database)
    upgrade_to_head(database)
    report.migrated = _revision_of(database) != before

    if not mind.initialised:
        mind.ensure()
        report.created.append(mind.path)

    if not mcp_path().exists():
        mcp_path().parent.mkdir(parents=True, exist_ok=True)
        mcp_path().write_text(json.dumps(EMPTY_MCP, indent=2) + "\n", encoding="utf-8")
        report.created.append(mcp_path())

    if not code_config_path().exists():
        # `load()` seeds from hera's config and then the environment without writing; this is the
        # one place that turns a seeded value into a file. After it, this file wins.
        save(config if config is not None else load())
        report.created.append(code_config_path())

    with database.session() as session:
        ensure_coding_profile(session, owner_id)

    return report


def _ensure_dir(path: Path, report: Prepared) -> None:
    if path.is_dir():
        return
    path.mkdir(parents=True, exist_ok=True)
    report.created.append(path)


def _revision_of(database: Database) -> tuple[str, ...]:
    with database.engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_heads()


__all__ = [
    "CODING_SLUG",
    "EMPTY_MCP",
    "DatabaseAhead",
    "Prepared",
    "check_revision",
    "prepare",
]
