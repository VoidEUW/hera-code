"""Seeding: what a fresh install gets, and what an existing one keeps.

Two promises, and every test here is one of them.

**Nothing is ever overwritten and nothing is ever deleted.** `~/.hera` is shared with hera, so
`prepare` runs against directories another application may own and a person may have edited. A
seeding step that replaced a file would destroy somebody's mind region or their `mcp.json`.

**It is idempotent**, so it can run on every launch rather than only the first. Somebody who
deleted a profile should get it back, and the first turn is a worse place to discover there is
nobody to answer as.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from hera_code.boot import DatabaseAhead, check_revision, prepare
from hera_code.config import CodeConfig
from hera_code.profile import CODING_SLUG
from hera_code_home import code_config_path, code_home, project_dir, sessions_db_path
from hera_home import mcp_path, mind_dir, skills_dir
from hera_profiles import MindRepository, ProfileRepository
from hera_storage import Database


def test_a_fresh_install_gets_everything(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    mind = MindRepository(mind_dir())
    report = prepare(database, mind, owner_id=owner_id, config=config)

    assert mind.initialised
    assert skills_dir().is_dir()
    assert mcp_path().is_file()
    assert code_home().is_dir()
    assert code_config_path().is_file()
    assert sessions_db_path().is_file()
    assert report.anything


def test_the_database_directory_exists_before_the_database_does(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """SQLite will not create a file in a directory that is not there, and what it says instead
    is `unable to open database file` — which names neither the directory nor the fix.

    Ordering inside `prepare` is the whole guard, so this is the test that holds it.
    """
    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)
    assert sessions_db_path().parent.is_dir()


def test_running_it_twice_changes_nothing(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """Idempotent, and provably so: not one file is rewritten."""
    mind = MindRepository(mind_dir())
    prepare(database, mind, owner_id=owner_id, config=config)

    before = _fingerprint()
    report = prepare(database, mind, owner_id=owner_id, config=config)

    assert not report.anything
    assert _fingerprint() == before


def test_an_existing_mind_is_left_alone(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """The mind is shared with hera. Overwriting a region a person edited is unforgivable."""
    mind = MindRepository(mind_dir())
    mind.ensure()
    mind.write("character", "She is terse and never apologises.", origin="manual")

    prepare(database, mind, owner_id=owner_id, config=config)

    # Stripped, because `MindRepository.write` normalises a trailing newline on the way in. What
    # this test is about is that the words survive, not how the file ends.
    assert mind.read("character").strip() == "She is terse and never apologises."


def test_an_existing_mcp_json_is_left_alone(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """Somebody's configured servers survive a hera-code install."""
    mcp_path().parent.mkdir(parents=True, exist_ok=True)
    theirs = {"mcpServers": {"filesystem": {"command": "npx", "args": ["-y", "@mcp/fs"]}}}
    mcp_path().write_text(json.dumps(theirs))

    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)

    assert json.loads(mcp_path().read_text()) == theirs


def test_an_existing_config_is_left_alone(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    code_config_path().parent.mkdir(parents=True, exist_ok=True)
    code_config_path().write_text('# mine\nactive_provider = "mine"\n')

    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)

    assert "# mine" in code_config_path().read_text()


def test_the_mcp_file_it_writes_is_empty_and_valid(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """A server nobody asked for is one that fails on the first turn and has to be explained."""
    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)
    assert json.loads(mcp_path().read_text()) == {"mcpServers": {}}


def test_the_coding_profile_is_created_and_default(
    database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)

    with database.session() as session:
        profile = ProfileRepository(session).by_slug(owner_id, CODING_SLUG)
        assert profile is not None
        assert profile.is_default


def test_nothing_is_written_into_a_working_tree(
    tmp_path: Path, database: Database, owner_id: UUID, config: CodeConfig
) -> None:
    """`init` prepares `~/.hera`. `<root>/.hera` is created by the work, not by the install —
    and never by surprise."""
    prepare(database, MindRepository(mind_dir()), owner_id=owner_id, config=config)
    assert not project_dir(tmp_path).exists()


def test_a_database_from_the_future_is_refused_rather_than_repaired(database: Database) -> None:
    """Stamping it back would leave columns a later upgrade fails to add; downgrading would drop
    somebody's sessions because their shell was in the wrong directory. Both are a person's call.
    """
    sessions_db_path().parent.mkdir(parents=True, exist_ok=True)
    with database.engine.begin() as connection:
        from sqlalchemy import text

        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('9999')"))

    with pytest.raises(DatabaseAhead) as caught:
        check_revision(database)

    message = str(caught.value)
    assert "9999" in message
    assert "Nothing has been changed." in message
    assert "git switch" in message, "the message has to say what to do, not only what is wrong"


def _fingerprint() -> dict[str, tuple[int, int]]:
    """Every file under the home, with its size and modification time in nanoseconds.

    Size *and* mtime, because a rewrite with identical content still moves the mtime — which is
    what a non-idempotent seeding step would do.
    """
    from hera_home import home

    return {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(home().rglob("*"))
        if path.is_file()
    }
