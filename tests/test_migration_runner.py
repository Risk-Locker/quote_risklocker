"""Migration discovery, checksum, and readiness contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.migrations import (
    AppliedMigration,
    MigrationError,
    build_plan,
    discover_migrations,
    validate_schema_history,
)
from app.db import migrations as migration_module


def write_migration(root: Path, name: str, sql: str) -> None:
    (root / name).write_text(sql, encoding="utf-8")


def test_migrations_are_strictly_ordered_and_content_hashed(tmp_path: Path):
    write_migration(tmp_path, "002_second.sql", "SELECT 2;\n")
    write_migration(tmp_path, "001_first.sql", "SELECT 1;\n")

    migrations = discover_migrations(tmp_path)

    assert [item.version for item in migrations] == [1, 2]
    assert [item.name for item in migrations] == ["001_first.sql", "002_second.sql"]
    assert all(len(item.checksum) == 64 for item in migrations)


@pytest.mark.parametrize("name", ["no-prefix.sql", "01_short.sql", "001-no-underscore.sql"])
def test_migration_discovery_rejects_malformed_names(tmp_path: Path, name: str):
    write_migration(tmp_path, name, "SELECT 1;")

    with pytest.raises(MigrationError, match="migration filename"):
        discover_migrations(tmp_path)


def test_migration_discovery_rejects_duplicate_or_gapped_versions(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    write_migration(tmp_path, "001_duplicate.sql", "SELECT 2;")
    with pytest.raises(MigrationError, match="duplicate"):
        discover_migrations(tmp_path)

    (tmp_path / "001_duplicate.sql").unlink()
    write_migration(tmp_path, "003_gap.sql", "SELECT 3;")
    with pytest.raises(MigrationError, match="contiguous"):
        discover_migrations(tmp_path)


def test_plan_skips_matching_history_and_rejects_checksum_drift(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    write_migration(tmp_path, "002_second.sql", "SELECT 2;")
    migrations = discover_migrations(tmp_path)
    applied = [AppliedMigration(version=1, name=migrations[0].name, checksum=migrations[0].checksum)]

    assert build_plan(migrations, applied) == [migrations[1]]

    drifted = [AppliedMigration(version=1, name=migrations[0].name, checksum="0" * 64)]
    with pytest.raises(MigrationError, match="checksum"):
        build_plan(migrations, drifted)


def test_plan_rejects_database_history_unknown_to_this_release(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    migrations = discover_migrations(tmp_path)

    with pytest.raises(MigrationError, match="newer than this release"):
        build_plan(
            migrations,
            [AppliedMigration(version=2, name="002_future.sql", checksum="a" * 64)],
        )


def test_schema_readiness_requires_every_release_migration_and_matching_checksums(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    write_migration(tmp_path, "002_second.sql", "SELECT 2;")
    migrations = discover_migrations(tmp_path)

    with pytest.raises(MigrationError, match="behind"):
        validate_schema_history(migrations, [AppliedMigration(1, migrations[0].name, migrations[0].checksum)])

    with pytest.raises(MigrationError, match="checksum"):
        validate_schema_history(
            migrations,
            [
                AppliedMigration(1, migrations[0].name, migrations[0].checksum),
                AppliedMigration(2, migrations[1].name, "f" * 64),
            ],
        )

    validate_schema_history(
        migrations,
        [AppliedMigration(item.version, item.name, item.checksum) for item in migrations],
    )


def test_default_migration_root_points_to_repository_migrations():
    root = migration_module.default_migration_root()

    assert root == ROOT / "migrations"
    assert (root / "001_create_users_table.sql").is_file()
