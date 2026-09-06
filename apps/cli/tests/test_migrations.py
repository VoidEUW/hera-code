"""The schema, and the two ways it can silently go wrong.

A model is only in `SQLModel.metadata` once its module has been imported, so `alembic autogenerate`
sees exactly what happened to be imported when it ran. Left implicit, a package nobody imported is
a package whose tables silently do not exist — and the migration that gets generated next
cheerfully proposes dropping them.

`hera_code.models.ALL_TABLES` makes that explicit; these tests are what hold it to the metadata.
"""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID

from sqlalchemy import inspect as sa_inspect
from sqlmodel import SQLModel

from hera_code.config import CodeConfig
from hera_code.migrations import upgrade_to_head
from hera_code.models import ALL_TABLES, TABLE_NAMES
from hera_profiles import MindRepository
from hera_storage import Database


def test_every_listed_table_is_registered() -> None:
    """`ALL_TABLES` naming something that is not in the metadata is a typo with no other symptom."""
    missing = set(TABLE_NAMES) - set(SQLModel.metadata.tables)
    assert not missing, sorted(missing)


def test_every_table_a_shipped_package_declares_is_listed() -> None:
    """Forgetting a package here is a failing test rather than a migration that drops a table.

    A **static scan** rather than a comparison against `SQLModel.metadata`, and the reason is worth
    knowing: that metadata is process-global, so the vendored packages' own test suites register
    their fixtures into it — `hera_storage` alone contributes `test_widgets`, `test_gizmos` and
    three more. Comparing against it passes when this module runs alone and fails when the whole
    suite does, which is the worst kind of test.

    Reading the source instead asks the question that is actually meant: *does a package we ship
    declare a table nobody listed?*
    """
    declared = _declared_tablenames()
    assert declared, "the scan found no tables at all, which means it is broken"

    missing = declared - set(TABLE_NAMES)
    assert not missing, (
        f"declared in packages/ but not in hera_code.models.ALL_TABLES: {sorted(missing)}. "
        "Add it, or the next autogenerate will propose dropping it."
    )


def _declared_tablenames() -> set[str]:
    """Every `__tablename__` really assigned inside a class in a shipped package's source.

    Deliberately not an import: importing every module to inspect it is what pollutes the metadata
    in the first place, and this test exists because of that pollution.

    **Parsed rather than grepped**, and that is not fussiness — a regex over the text finds
    `__tablename__ = "cook_recipes"` in `hera_storage.base`'s docstring, which is an illustration
    of how to declare a table rather than a declaration of one. An `ast.Assign` inside a
    `ClassDef` is the thing that actually creates a table; a docstring is an `Expr` and is skipped
    for free.
    """
    root = Path(__file__).resolve().parents[3] / "packages"
    found: set[str] = set()
    for source in root.glob("*/src/**/*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                found.update(_tablename_of(statement))
    return found


def _tablename_of(statement: ast.stmt) -> set[str]:
    if not isinstance(statement, ast.Assign):
        return set()
    names = {t.id for t in statement.targets if isinstance(t, ast.Name)}
    if "__tablename__" not in names:
        return set()
    value = statement.value
    return (
        {value.value} if isinstance(value, ast.Constant) and isinstance(value.value, str) else set()
    )


def test_every_table_carries_a_package_prefix() -> None:
    """All models share one `MetaData`, so an unprefixed name from two packages would silently
    collide. The rule is in ARCHITECTURE.md; this is what enforces it."""
    unprefixed = [name for name in TABLE_NAMES if "_" not in name]
    assert not unprefixed, unprefixed


def test_the_migration_produces_the_whole_schema(database: Database) -> None:
    upgrade_to_head(database)

    created = set(sa_inspect(database.engine).get_table_names())

    assert set(TABLE_NAMES) <= created, sorted(set(TABLE_NAMES) - created)


def test_upgrading_twice_is_harmless(database: Database) -> None:
    """`prepare` runs on every launch, so this is the ordinary case rather than the corner."""
    upgrade_to_head(database)
    upgrade_to_head(database)
    assert set(TABLE_NAMES) <= set(sa_inspect(database.engine).get_table_names())


def test_the_schema_matches_the_models(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """Autogenerate against a migrated database should have nothing to say.

    This is the test that catches a model changed without a revision — the failure that otherwise
    shows up as a column missing at runtime, months later, on somebody else's machine.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from hera_code.boot import prepare
    from hera_home import mind_dir

    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)

    with database.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        difference = compare_metadata(context, SQLModel.metadata)

    # Filtered to our tables. `SQLModel.metadata` is process-global, so when the whole suite runs
    # it also holds the vendored packages' test fixtures, and autogenerate would dutifully propose
    # creating `test_widgets` here. Those are not ours and their absence is not a disagreement.
    ours = [entry for entry in difference if _table_of(entry) in TABLE_NAMES]

    assert not ours, f"the models and the migrations disagree: {ours}"


def _table_of(entry: object) -> str:
    """The table name an autogenerate diff entry is about.

    Entries are tuples whose shape depends on the kind: `('add_table', Table)`,
    `('add_column', schema, table_name, Column)`, and so on. Both shapes are unpacked here rather
    than only the one seen today, because a change that produced the other shape should still be
    filtered rather than silently kept.
    """
    if not isinstance(entry, tuple) or not entry:
        return ""
    for part in entry[1:]:
        if isinstance(part, str) and part:
            return part
        table = getattr(part, "name", None)
        if isinstance(table, str):
            return table
    return ""


def test_the_project_table_exists_although_nothing_writes_to_it() -> None:
    """hera-code has no projects — a working tree is a directory, not a row.

    The table comes from `hera_chats`, which is vendored and not edited (ADR 1), so it is in the
    schema whether or not anything uses it. Leaving it out of `ALL_TABLES` would make the next
    autogenerate propose dropping it, which is why it is deliberately listed.
    """
    assert "chat_projects" in TABLE_NAMES
    assert len(ALL_TABLES) == len(TABLE_NAMES), "two models share a __tablename__"
