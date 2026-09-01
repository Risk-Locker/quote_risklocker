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
    connect_with_retry,
    discover_migrations,
    migration_checksums,
    validate_schema_history,
)
from app.db import migrations as migration_module

REAL_036 = ROOT / "migrations" / "036_package_plans.sql"
PRODUCTION_036_CHECKSUM = "d8fdd09a77b43d093cd715e5547fc9d28bdb23b80f4c71daf22169b005186734"


def write_migration(root: Path, name: str, sql: str) -> None:
    (root / name).write_text(sql, encoding="utf-8")


def write_filler(root: Path, upto: int) -> None:
    for version in range(1, upto + 1):
        (root / f"{version:03d}_filler.sql").write_text(f"SELECT {version};\n", encoding="utf-8")


def to_crlf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


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


def test_lf_and_crlf_files_produce_the_same_checksum(tmp_path: Path):
    lf_dir = tmp_path / "lf"
    crlf_dir = tmp_path / "crlf"
    lf_dir.mkdir()
    crlf_dir.mkdir()
    write_migration(lf_dir, "001_first.sql", "SELECT 1;\n")
    (crlf_dir / "001_first.sql").write_bytes(b"SELECT 1;\r\n")

    lf = discover_migrations(lf_dir)[0]
    crlf = discover_migrations(crlf_dir)[0]

    assert lf.checksum == crlf.checksum
    assert lf.checksum == migration_checksums(b"SELECT 1;\n")[0]


def test_mixed_cr_crlf_and_lf_line_endings_normalize_identically(tmp_path: Path):
    canonical = b"SELECT 1;\nSELECT 2;\nSELECT 3;\n"
    mixed = b"SELECT 1;\r\nSELECT 2;\rSELECT 3;\n"

    assert migration_checksums(mixed)[0] == migration_checksums(canonical)[0]


def test_real_036_accepts_the_historical_production_checksum(tmp_path: Path):
    if not REAL_036.is_file():
        pytest.skip("migrations/036_package_plans.sql missing from the checkout")
    for suffix, content in (("lf", REAL_036.read_bytes()), ("crlf", to_crlf(REAL_036.read_bytes()))):
        directory = tmp_path / suffix
        directory.mkdir()
        write_filler(directory, 35)
        (directory / "036_package_plans.sql").write_bytes(content)

        migrations = discover_migrations(directory)
        applied = [AppliedMigration(version=36, name="036_package_plans.sql", checksum=PRODUCTION_036_CHECKSUM)]

        plan = build_plan(migrations, applied)
        assert all(item.version != 36 for item in plan)


def test_genuine_content_change_still_fails_against_historical_checksum(tmp_path: Path):
    if not REAL_036.is_file():
        pytest.skip("migrations/036_package_plans.sql missing from the checkout")
    changed = REAL_036.read_text(encoding="utf-8").replace("package_plan_id", "package_plan_id_mutated")
    assert changed != REAL_036.read_text(encoding="utf-8")
    write_filler(tmp_path, 35)
    (tmp_path / "036_package_plans.sql").write_bytes(to_crlf(changed.encode("utf-8")))

    migrations = discover_migrations(tmp_path)
    applied = [AppliedMigration(version=36, name="036_package_plans.sql", checksum=PRODUCTION_036_CHECKSUM)]

    with pytest.raises(MigrationError, match="checksum"):
        build_plan(migrations, applied)


def test_name_mismatch_fails_even_with_a_matching_checksum(tmp_path: Path):
    if not REAL_036.is_file():
        pytest.skip("migrations/036_package_plans.sql missing from the checkout")
    write_filler(tmp_path, 35)
    (tmp_path / "036_package_plans.sql").write_bytes(REAL_036.read_bytes())
    migrations = discover_migrations(tmp_path)

    renamed = [AppliedMigration(version=36, name="036_something_else.sql", checksum=PRODUCTION_036_CHECKSUM)]
    with pytest.raises(MigrationError, match="checksum/name"):
        build_plan(migrations, renamed)

    tampered = [AppliedMigration(version=36, name="036_package_plans.sql", checksum="0" * 64)]
    with pytest.raises(MigrationError, match="checksum"):
        build_plan(migrations, tampered)


def test_unknown_newer_migration_037_still_fails(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    migrations = discover_migrations(tmp_path)

    with pytest.raises(MigrationError, match="newer than this release"):
        build_plan(migrations, [AppliedMigration(version=37, name="037_future.sql", checksum="a" * 64)])


def test_fresh_planning_returns_every_migration(tmp_path: Path):
    write_migration(tmp_path, "001_first.sql", "SELECT 1;")
    write_migration(tmp_path, "002_second.sql", "SELECT 2;")
    migrations = discover_migrations(tmp_path)

    assert build_plan(migrations, []) == migrations


def test_already_applied_legacy_rows_are_not_rerun(tmp_path: Path):
    write_filler(tmp_path, 34)
    if REAL_036.is_file():
        (tmp_path / "035_prev.sql").write_text("SELECT 35;\n")
        (tmp_path / "036_package_plans.sql").write_bytes(to_crlf(REAL_036.read_bytes()))
    else:
        write_migration(tmp_path, "035_prev.sql", "SELECT 35;")
        write_migration(tmp_path, "036_package_plans.sql", "SELECT 36;")
    migrations = discover_migrations(tmp_path)
    checksums = {item.version: item.checksum for item in migrations}

    applied = [
        AppliedMigration(version=35, name="035_prev.sql", checksum=checksums[35]),
        AppliedMigration(version=36, name="036_package_plans.sql", checksum=PRODUCTION_036_CHECKSUM),
    ]

    assert [item.version for item in build_plan(migrations, applied)] == list(range(1, 35))


def test_crlf_migrations_still_require_contiguous_versions(tmp_path: Path):
    (tmp_path / "001_first.sql").write_bytes(b"SELECT 1;\r\n")
    (tmp_path / "003_third.sql").write_bytes(b"SELECT 3;\r\n")

    with pytest.raises(MigrationError, match="contiguous"):
        discover_migrations(tmp_path)


def test_real_037_discovery_and_planning():
    migrations = discover_migrations(ROOT / "migrations")
    assert len(migrations) >= 37
    m37 = next(item for item in migrations if item.version == 37)
    assert m37.name == "037_draft_package_pin.sql"
    assert len(m37.checksum) == 64


def test_connect_with_retry_recovers_after_transient_failures(monkeypatch):
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError

    engine = MagicMock()
    mock_conn = MagicMock()
    attempts = [0]

    def mock_connect():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OperationalError("FATAL: (EMAXCONNSESSION) max clients reached", params=None, orig=Exception())
        return mock_conn

    engine.connect = mock_connect
    monkeypatch.setattr("time.sleep", lambda _: None)

    conn = connect_with_retry(engine, max_attempts=5, initial_delay=0.01, max_delay=0.05)
    assert conn is mock_conn
    assert attempts[0] == 3


def test_connect_with_retry_exhausts_and_raises(monkeypatch):
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError

    engine = MagicMock()

    def mock_connect():
        raise OperationalError("FATAL: (EMAXCONNSESSION) max clients reached", params=None, orig=Exception())

    engine.connect = mock_connect
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(OperationalError, match="EMAXCONNSESSION"):
        connect_with_retry(engine, max_attempts=3, initial_delay=0.01, max_delay=0.05)


