"""Batch recalculate road tax and entity classification (Individual vs Company) across all database sessions.

Usage (from repo root):
    python commands/recalculate-road-tax-and-client-type.py --dry-run
    python commands/recalculate-road-tax-and-client-type.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.extraction.entity_classifier import classify_client_entity  # noqa: E402
from app.models.tables import ClientRecord, DraftBenefitSelection, QuotationDraft  # noqa: E402
from app.services.road_tax_service import calculate_road_tax  # noqa: E402


def _get_val(fields: dict[str, Any], key: str) -> Any:
    raw = fields.get(key)
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value")
    return raw


def _set_val(fields: dict[str, Any], key: str, value: Any) -> None:
    raw = fields.get(key)
    if isinstance(raw, dict) and "value" in raw:
        raw["value"] = value
    else:
        fields[key] = value


def _to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0.00")
    s = re.sub(r"[^\d.]", "", str(val))
    if not s:
        return Decimal("0.00")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0.00")


def run_recalculation(apply: bool = False) -> None:
    mode_str = "APPLY" if apply else "DRY RUN"
    print(f"=== Recalculating Road Tax & Client Entity Classification (Mode: {mode_str}) ===\n")

    with SessionLocal() as db:
        drafts = db.query(QuotationDraft).order_by(QuotationDraft.created_at.desc()).all()
        print(f"Found {len(drafts)} quotation drafts to inspect.\n")

        changed_count = 0
        unchanged_count = 0
        client_record_changes = 0

        for draft in drafts:
            fields = dict(draft.fields or {})
            insured_name = _get_val(fields, "insured_name") or _get_val(fields, "customer_name") or ""
            ic_or_brn = (
                _get_val(fields, "ic_or_brn")
                or _get_val(fields, "ic_number")
                or _get_val(fields, "business_registration_number")
                or ""
            )
            vtype_raw = _get_val(fields, "vehicle_type") or "Car"
            old_client_type = _get_val(fields, "client_type")
            old_roadtax_str = _get_val(fields, "roadtax") or _get_val(fields, "road_tax_amount") or "0.00"
            old_roadtax = _to_decimal(old_roadtax_str)

            cc_raw = _get_val(fields, "engine_cc")
            clean_cc = 0.0
            if cc_raw:
                try:
                    clean_cc = float(re.sub(r"[^\d.]", "", str(cc_raw)))
                except Exception:
                    clean_cc = 0.0

            car_model = _get_val(fields, "car_model") or ""
            new_client_type, new_vtype = classify_client_entity(
                customer_name=str(insured_name),
                ic_or_brn=str(ic_or_brn),
                current_vehicle_type=str(vtype_raw),
                car_model=str(car_model),
            )

            new_roadtax_num = 0.0
            # Guard against invalid/corrupt CC extractions (e.g. 32179 from chassis numbers)
            if 50 <= clean_cc <= 7000:
                new_roadtax_num = calculate_road_tax(
                    clean_cc,
                    new_vtype,
                    owner_type=new_client_type,
                )
            new_roadtax = Decimal(f"{new_roadtax_num:.2f}")

            # Check if any change occurred
            vtype_changed = str(vtype_raw) != str(new_vtype)
            client_type_changed = (
                old_client_type is None
                or str(old_client_type).strip().capitalize() != str(new_client_type).strip().capitalize()
            )
            roadtax_changed = abs(old_roadtax - new_roadtax) > Decimal("0.001")

            if vtype_changed or client_type_changed or roadtax_changed:
                changed_count += 1
                print(
                    f"Draft ID: {draft.id} | Ref: {_get_val(fields, 'quotation_reference') or 'N/A'}\n"
                    f"  Customer: {insured_name!r} | IC/BRN: {ic_or_brn!r} | CC: {clean_cc}\n"
                    f"  Client Type:  {old_client_type or 'None'} -> {new_client_type}\n"
                    f"  Vehicle Type: {vtype_raw} -> {new_vtype}\n"
                    f"  Road Tax:     RM {old_roadtax:.2f} -> RM {new_roadtax:.2f}"
                )

                _set_val(fields, "client_type", new_client_type)
                _set_val(fields, "vehicle_type", new_vtype)
                _set_val(fields, "roadtax", f"{new_roadtax:.2f}")
                _set_val(fields, "road_tax_amount", f"{new_roadtax:.2f}")

                # Recalculate total
                p_num = _to_decimal(_get_val(fields, "premium"))
                sf_num = _to_decimal(_get_val(fields, "service_fee") or _get_val(fields, "runner_fee"))

                selections = db.query(DraftBenefitSelection).filter(
                    DraftBenefitSelection.draft_id == draft.id,
                    DraftBenefitSelection.state.in_(["selected", "confirmed", "applied"]),
                ).all()
                extras_total = Decimal("0.00")
                for sel in selections:
                    if sel.price and isinstance(sel.price, dict):
                        p = sel.price.get("amount") if "amount" in sel.price else sel.price.get("value")
                        extras_total += _to_decimal(p)

                if p_num > Decimal("0.00"):
                    new_total = p_num + new_roadtax + sf_num + extras_total
                    old_total = _to_decimal(_get_val(fields, "total_amount"))
                    _set_val(fields, "total_amount", f"{new_total:.2f}")
                    if abs(old_total - new_total) > Decimal("0.001"):
                        print(f"  Total Amount: RM {old_total:.2f} -> RM {new_total:.2f}")

                draft.fields = dict(fields)
                flag_modified(draft, "fields")

                # Sync associated ClientRecord if exists
                matched_crs = db.query(ClientRecord).filter(ClientRecord.draft_id == draft.id).all()
                for cr in matched_crs:
                    cr.roadtax = f"{new_roadtax:.2f}"
                    cr.total_premium = _get_val(fields, "total_amount")
                    cr.raw_values = dict(fields)
                    client_record_changes += 1

                print()
            else:
                unchanged_count += 1

        print(
            f"Summary: {changed_count} drafts changed, {unchanged_count} unchanged, {client_record_changes} client records updated."
        )

        if apply:
            db.commit()
            print("\nSUCCESS: All changes committed to the database.")
        else:
            db.rollback()
            print("\nDRY RUN complete. No changes were committed. Use --apply to execute.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recalculate road tax and entity types in drafts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Inspect without committing.")
    group.add_argument("--apply", action="store_true", help="Execute and commit to DB.")
    args = parser.parse_args()

    run_recalculation(apply=args.apply)


if __name__ == "__main__":
    main()
