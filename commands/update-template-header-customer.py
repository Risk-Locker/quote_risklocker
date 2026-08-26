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
            y = el.get("y") or 0
            el_id = el.get("id") or ""
            var_id = el.get("variableId") or ""
            text = el.get("text") or ""

            # 1. Top header (y < 100): ensure insurer name is shown
            if y < 100 and (el_id in {"header_customer_name", "header_insurer_name"} or var_id in {"customer_name", "insurance_company"}):
                if var_id != "insurance_company" or el_id != "header_insurer_name":
                    el["id"] = "header_insurer_name"
                    el["variableId"] = "insurance_company"
                    el["w"] = 230
                    modified = True
                    print(f"[{'APPLY' if apply else 'DRY-RUN'}] Template '{tmpl.name}': Top Header -> header_insurer_name (insurance_company)")

            # 2. Coverage Table Row 1 (y around 160-175): ensure customer name is shown
            if 150 <= y <= 175:
                if el_id in {"lbl_insurer", "lbl_customer"} or "保险公司" in text or "客户" in text or "insurer" in text.lower():
                    if text != "Customer / 客户姓名" or el_id != "lbl_customer":
                        el["id"] = "lbl_customer"
                        el["text"] = "Customer / 客户姓名"
                        modified = True
                        print(f"[{'APPLY' if apply else 'DRY-RUN'}] Template '{tmpl.name}': Table Row 1 Label -> Customer")
                elif el_id in {"val_insurer", "val_customer"} or var_id in {"insurance_company", "customer_name"}:
                    if var_id != "customer_name" or el_id != "val_customer":
                        el["id"] = "val_customer"
                        el["variableId"] = "customer_name"
                        modified = True
                        print(f"[{'APPLY' if apply else 'DRY-RUN'}] Template '{tmpl.name}': Table Row 1 Value -> val_customer (customer_name)")

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
