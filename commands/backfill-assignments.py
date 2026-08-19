"""Plan or apply the offering_kind -> assignment role backfill (refactor Tasks 3/10).

Maps legacy catalog offerings to the Benefit Assignment model:
    base              -> role = 'included'
    optional          -> role = 'addon_option'
    package_component -> role = 'bundle_component'
    upgrade           -> stays legacy (role NULL), reported only

Apply writes ONLY rows belonging to DRAFT revisions: published revisions are
immutable by trigger (migrations/024). Published rows are reported as skipped.
For draft offerings of product-level catalogs (no tier, no package) the
assignment target is resolved automatically (applies_to_type = 'product').

Usage (from repo root, PYTHONPATH=backend):
    python commands/backfill-assignments.py --dry-run
    python commands/backfill-assignments.py            # applies draft-only changes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import engine  # noqa: E402


REPORT_HEADER = "{state:<12} {kind:<18} {count:>6}  {action}"


def _report(db) -> None:
    rows = db.execute(
        text(
            """
            SELECT r.state, o.offering_kind, COUNT(*) AS count
            FROM catalog_offerings o
            JOIN benefit_catalog_revisions r ON r.id = o.catalog_revision_id
            GROUP BY r.state, o.offering_kind
            ORDER BY r.state, o.offering_kind
            """
        )
    ).all()
    planned = {"base": "included", "optional": "addon_option", "package_component": "bundle_component"}
    print(REPORT_HEADER.format(state="state", kind="offering_kind", count="count", action="action"))
    print("-" * 60)
    for state, kind, count in rows:
        if kind in planned:
            action = f"-> {planned[kind]} (draft only)" if state == "draft" else "skipped: published revision is immutable"
        else:
            action = "legacy: role stays NULL"
        print(REPORT_HEADER.format(state=state or "-", kind=kind or "-", count=int(count or 0), action=action))
    product_level = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM catalog_offerings o
            JOIN benefit_catalog_revisions r ON r.id = o.catalog_revision_id
            JOIN benefit_catalogs c ON c.id = r.catalog_id
            WHERE r.state = 'draft' AND o.role IS NULL
              AND o.offering_kind IN ('base', 'optional', 'package_component')
              AND c.package_id IS NULL AND c.tier_id IS NULL
            """
        )
    ).scalar()
    print(f"\nDraft product-level offerings that will also get applies_to_type='product': {int(product_level or 0)}")


def _apply(db) -> int:
    result = db.execute(
        text(
            """
            WITH draft_revs AS (
                SELECT r.id AS revision_id, c.tier_id, c.package_id
                FROM benefit_catalog_revisions r
                JOIN benefit_catalogs c ON c.id = r.catalog_id
                WHERE r.state = 'draft'
            )
            UPDATE catalog_offerings o
            SET role = CASE o.offering_kind
                           WHEN 'base' THEN 'included'
                           WHEN 'optional' THEN 'addon_option'
                           WHEN 'package_component' THEN 'bundle_component'
                           ELSE o.role
                       END,
                applies_to_type = CASE
                    WHEN o.applies_to_type IS NULL AND d.package_id IS NULL AND d.tier_id IS NULL THEN 'product'
                    ELSE o.applies_to_type
                END
            FROM draft_revs d
            WHERE o.catalog_revision_id = d.revision_id
              AND o.role IS NULL
              AND o.offering_kind IN ('base', 'optional', 'package_component')
            """
        )
    )
    return int(result.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Map catalog offerings to assignment roles (draft revisions only).")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing.")
    args = parser.parse_args()

    with engine.connect() as connection:
        if args.dry_run:
            _report(connection)
            return
        updated = _apply(connection)
        connection.commit()
        print(f"Updated {updated} draft-revision offering(s). Run with --dry-run to inspect the current state.")


if __name__ == "__main__":
    main()
