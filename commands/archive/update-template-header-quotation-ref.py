"""Idempotently update existing TemplateRevision configurations with Quotation Ref and Vehicle No header fields."""

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
from app.models.tables import OutputTemplateConfig, User
from app.services.template_revision_service import publish_template_revision

MUTED_COLOR = "#64748B"


def update_template_headers(db, user, *, apply: bool = False) -> list[dict]:
    templates = list(db.scalars(select(OutputTemplateConfig).where(OutputTemplateConfig.deleted_at.is_(None)).order_by(OutputTemplateConfig.created_at)).all())
    updated_records = []

    for tmpl in templates:
        fixed_fields = copy.deepcopy(tmpl.fixed_fields or {})
        canvas = fixed_fields.get("canvas") or {}
        elements = canvas.get("elements") or []
        modified = False

        has_vehicle_label = False
        has_vehicle_val = False

        for el in elements:
            y = el.get("y") or 0
            el_id = el.get("id") or ""
            var_id = el.get("variableId") or ""

            # Check existing elements
            if el_id == "vehicle_no_label":
                has_vehicle_label = True
            if el_id == "vehicle_no_val":
                has_vehicle_val = True

            # 1. Quotation Ref Label (top line: y=36)
            if el_id in {"ref_label", "quotation_ref_label"} and y < 100:
                if el.get("y") != 36 or el.get("x") != 460 or el.get("w") != 150 or el.get("text") != "Quotation Ref: ":
                    el["text"] = "Quotation Ref: "
                    el["x"] = 460
                    el["y"] = 36
                    el["w"] = 150
                    el["h"] = 16
                    el["size"] = 10.5
                    el["weight"] = "500"
                    el["color"] = MUTED_COLOR
                    el["align"] = "right"
                    modified = True

            # 2. Quotation Ref Value (top line: y=36, maps to quotation_reference)
            if el_id in {"ref_val", "quotation_ref_val"} and y < 100:
                if var_id != "quotation_reference" or el.get("y") != 36 or el.get("x") != 614:
                    el["variableId"] = "quotation_reference"
                    el["x"] = 614
                    el["y"] = 36
                    el["w"] = 140
                    el["h"] = 16
                    el["size"] = 10.5
                    el["weight"] = "700"
                    el["color"] = MUTED_COLOR
                    el["align"] = "left"
                    modified = True

        # If vehicle_no_label is missing in header, add it at y=56
        if not has_vehicle_label:
            elements.append({
                "id": "vehicle_no_label",
                "type": "text",
                "x": 460,
                "y": 56,
                "w": 150,
                "h": 16,
                "z": 5,
                "text": "Vehicle No: ",
                "size": 10.5,
                "weight": "500",
                "color": MUTED_COLOR,
                "align": "right",
            })
            modified = True

        # If vehicle_no_val is missing in header, add it at y=56
        if not has_vehicle_val:
            elements.append({
                "id": "vehicle_no_val",
                "type": "variable",
                "x": 614,
                "y": 56,
                "w": 140,
                "h": 16,
                "z": 5,
                "variableId": "vehicle_no",
                "size": 10.5,
                "weight": "700",
                "color": MUTED_COLOR,
                "align": "left",
            })
            modified = True

        if modified:
            fixed_fields["canvas"]["elements"] = elements
            if apply:
                tmpl.fixed_fields = fixed_fields
                flag_modified(tmpl, "fixed_fields")
                new_rev = publish_template_revision(db, user, tmpl.id, base_revision=tmpl.revision)
                print(f"[{'APPLY' if apply else 'DRY-RUN'}] Published Revision {new_rev.revision_number} for '{tmpl.name}'")
            else:
                print(f"[{'APPLY' if apply else 'DRY-RUN'}] Template '{tmpl.name}': Added Quotation Ref & Vehicle No headers")
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
    parser = argparse.ArgumentParser(description="Update template header with separate Quotation Ref and Vehicle No.")
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
