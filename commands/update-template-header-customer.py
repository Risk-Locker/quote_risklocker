"""Idempotently update existing TemplateRevision configurations so the top header variable is customer_name."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import SessionLocal
from app.models.tables import OutputTemplateConfig, TemplateRevision, User
from app.services.template_revision_service import publish_template_revision


def update_template_headers(db, user, *, apply: bool = False) -> list[dict]:
    templates = list(db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None)).order_by(OutputTemplateConfig.created_at)).all())
    updated_records = []

    for tmpl in templates:
        fixed_fields = copy.deepcopy(tmpl.fixed_fields or {})
        canvas = fixed_fields.get("canvas") or {}
        elements = canvas.get("elements") or []
        modified = False

        for el in elements:
            # Check for top header insurer name variable (y < 100)
            if (
                (el.get("id") == "header_insurer_name" or el.get("variableId") == "insurance_company")
                and (el.get("y") or 0) < 100
            ):
                old_id = el.get("id")
                old_var = el.get("variableId")
                el["id"] = "header_customer_name"
                el["variableId"] = "customer_name"
                el["w"] = max(el.get("w", 230), 260)
                modified = True
                print(f"[{'APPLY' if apply else 'DRY-RUN'}] Updating Template '{tmpl.name}' (ID: {tmpl.id}): {old_id} ({old_var}) -> header_customer_name (customer_name)")

        if modified:
            fixed_fields["canvas"]["elements"] = elements
            if apply:
                tmpl.fixed_fields = fixed_fields
                flag_modified(tmpl, "fixed_fields")
                new_rev = publish_template_revision(db, user, tmpl.id, base_revision=tmpl.revision)
                print(f"  -> Published new Revision {new_rev.revision_number} for '{tmpl.name}'")
            updated_records.append({
                "template_id": tmpl.id,
                "template_name": tmpl.name,
            })

    if apply:
        db.commit()
        print(f"\nSuccessfully updated and published {len(updated_records)} templates.")
    else:
        db.rollback()
        print(f"\nDry-run completed for {len(updated_records)} templates (no changes written).")

    return updated_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Update template header insurer variable to customer_name.")
    parser.add_argument("--apply", action="store_true", help="Commit changes to database.")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "super_admin", User.status == "active").order_by(User.created_at))
        if not user:
            user = db.scalar(select(User).where(User.status == "active").order_by(User.created_at))
        update_template_headers(db, user, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
