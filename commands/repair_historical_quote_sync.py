"""Enterprise Historical Quote & Comparison Parity Audit/Repair Tool (`v32`).

Scans all non-trash quotations (`Session` + `QuotationDraft` + `ExtractionRecord` +
`TenureComparisonEntry`) and heals:
  1. Legacy `tot_num - extras_cost` subtraction splits where `detected_value` /
     `ExtractionRecord` retains the true Underwriter Motor Payable while `fields["premium"]`
     or `fields["motor_premium"]` drifted lower (never overriding genuine manual edits
     recorded in `scalar_decisions["premium"]["decision"] == "edit"`).
  2. Split-brain aliases (`fields["premium"]`, `motor_premium`, `total_payable`,
     `premium_due`) and net `total_amount` via pure `Decimal`.
  3. Missing `draft.company_id` / `ce.company_id` links resolved from
     `UploadedFile.insurance_company_id` or `Session.detected_company`.
  4. Comparison matrix materialization & ranking parity across every active tenure.

Usage:
  .\\.venv\\Scripts\\python.exe commands/repair_historical_quote_sync.py --dry-run
  .\\.venv\\Scripts\\python.exe commands/repair_historical_quote_sync.py --apply
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select
from sqlalchemy.orm import load_only, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import SessionLocal
from app.domain.benefit_pricing import parse_money_decimal
from app.domain.motor.discount_calculator import calculate_motor_discount, to_decimal_clean
from app.domain.quote_sync_engine import (
    resolve_canonical_motor_premium_decimal,
    resolve_session_company_id,
    sync_draft_motor_premium_aliases,
)
from app.models.tables import (
    ExtractionRecord,
    InsuranceCompany,
    InsuranceTenure,
    QuotationDraft,
    Session as SessionModel,
    TenureComparisonEntry,
    UploadedFile,
)
from app.services.marketing_comparison.materialize import (
    is_field_overridden,
    materialize_comparison_entries,
)
from app.services.marketing_comparison_service import rank_comparison_entries

_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_HUNDRED = Decimal("100")
_RATE_QUANT = Decimal("0.0001")


def _q2(val: Any) -> Decimal:
    return to_decimal_clean(val, _ZERO).quantize(_CENT, rounding=ROUND_HALF_UP)


def _match_company_id(detected_name: str | None, companies: list[InsuranceCompany]) -> str | None:
    clean = str(detected_name or "").strip().lower()
    if not clean:
        return None
    for c in companies:
        if (c.name or "").strip().lower() == clean or (c.slug or "").strip().lower() == clean:
            return str(c.id)
    for c in companies:
        cname = (c.name or "").strip().lower()
        if cname and (cname in clean or clean in cname):
            return str(c.id)
    return None


def _is_manual_premium_edit(draft: QuotationDraft) -> bool:
    decs = draft.scalar_decisions if isinstance(draft.scalar_decisions, dict) else {}
    prem_dec = decs.get("premium") if isinstance(decs.get("premium"), dict) else {}
    if prem_dec.get("decision") == "edit":
        return True
    p_node = (draft.fields or {}).get("premium") if isinstance(draft.fields, dict) else None
    return isinstance(p_node, dict) and p_node.get("status") == "manual_override"


def _detect_split_brain_uw_premium(draft: QuotationDraft, rec: ExtractionRecord | None) -> tuple[Decimal | None, str | None]:
    """Return `(authoritative_uw_dec, reason)` when draft pricing was split or subtracted."""
    fields = draft.fields if isinstance(draft.fields, dict) else {}
    cur_prem = _q2(fields.get("premium"))
    cur_mp = _q2(fields.get("motor_premium"))
    cur_tp = _q2(fields.get("total_payable"))
    extras = _q2(fields.get("total_optional_cover_amount"))

    prem_node = fields.get("premium")
    prem_det = _q2(prem_node.get("detected_value")) if isinstance(prem_node, dict) else _ZERO
    tot_node = fields.get("total_amount")
    tot_det = _q2(tot_node.get("detected_value")) if isinstance(tot_node, dict) else _ZERO

    rec_prem = _ZERO
    rec_tot = _ZERO
    if rec and isinstance(rec.candidates, dict):
        for key, out_attr in (("premium", "p"), ("total_amount", "t")):
            cand_list = rec.candidates.get(key)
            if isinstance(cand_list, list) and cand_list:
                best = cand_list[0]
                v = _q2(best.get("value") if isinstance(best, dict) else best)
                if out_attr == "p":
                    rec_prem = v
                else:
                    rec_tot = v

    if _is_manual_premium_edit(draft):
        # Preserve explicit manual edit, but align split aliases if motor_premium/total_payable drifted
        target = cur_prem if cur_prem > _ZERO else resolve_canonical_motor_premium_decimal(fields)
        if target > _ZERO and (cur_mp != target or cur_tp != target):
            return target, "align_manual_premium_aliases"
        return None, None

    # Detect legacy `tot_num - extras_cost` corruption in Rescan
    candidates_truth = [v for v in (rec_prem, prem_det, rec_tot, tot_det) if v > _ZERO]
    for truth in candidates_truth:
        if extras > _ZERO and cur_prem > _ZERO and truth > cur_prem:
            if abs((truth - extras) - cur_prem) <= Decimal("0.10"):
                return truth, f"heal_rescan_subtraction({cur_prem}->{truth},extras={extras})"

    # Align diverged motor_premium vs premium aliases
    if cur_mp > _ZERO and cur_prem > _ZERO and cur_mp != cur_prem:
        higher = max(cur_mp, cur_prem)
        return higher, f"align_split_aliases(prem={cur_prem},mp={cur_mp}->{higher})"

    canonical = resolve_canonical_motor_premium_decimal(fields)
    if canonical > _ZERO and (cur_prem != canonical or cur_mp != canonical or cur_tp != canonical):
        return canonical, f"sync_canonical_aliases({canonical})"
    return None, None


def run_audit_and_repair(*, apply_changes: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": "apply" if apply_changes else "dry_run",
        "sessions_scanned": 0,
        "drafts_repaired": [],
        "company_links_repaired": [],
        "tenures_re_materialized": [],
        "vqe8_or_target_session": None,
        "backup_path": None,
    }
    target_sid = "e7ee321c-9a85-4cb0-864a-0787636a2570"

    with SessionLocal() as db:
        companies = list(db.scalars(select(InsuranceCompany)).all())
        sessions = list(
            db.scalars(
                select(SessionModel)
                .options(
                    selectinload(SessionModel.draft),
                    selectinload(SessionModel.uploaded_file)
                    .load_only(UploadedFile.id, UploadedFile.insurance_company_id, UploadedFile.original_filename)
                    .selectinload(UploadedFile.extraction_record)
                    .load_only(ExtractionRecord.id, ExtractionRecord.uploaded_file_id, ExtractionRecord.candidates),
                    selectinload(SessionModel.tenure),
                )
                .where(SessionModel.status != "trash")
            ).all()
        )
        entries_by_session: dict[str, list[TenureComparisonEntry]] = {}
        entries_by_tenure: dict[str, list[TenureComparisonEntry]] = {}
        for ce in db.scalars(select(TenureComparisonEntry)).all():
            if ce.session_id:
                entries_by_session.setdefault(str(ce.session_id), []).append(ce)
            if ce.tenure_id:
                entries_by_tenure.setdefault(str(ce.tenure_id), []).append(ce)

        report["sessions_scanned"] = len(sessions)
        backup_records: list[dict[str, Any]] = []
        affected_tenures: set[str] = set()
        rematerialize_tenures: set[str] = set()
        sessions_by_tenure: dict[str, list[SessionModel]] = {}

        for sess in sessions:
            draft = sess.draft
            if not draft:
                continue
            if sess.tenure_id:
                sessions_by_tenure.setdefault(str(sess.tenure_id), []).append(sess)
            uf = sess.uploaded_file
            rec = getattr(uf, "extraction_record", None) if uf else None
            fields = dict(draft.fields or {}) if isinstance(draft.fields, dict) else {}

            if sess.id == target_sid or (getattr(sess.tenure, "vehicle_no", "") or "").upper() == "VQE8":
                ce_list = entries_by_session.get(sess.id, [])
                info = {
                    "session_id": sess.id,
                    "tenure_id": sess.tenure_id,
                    "vehicle_no": getattr(sess.tenure, "vehicle_no", None),
                    "detected_company": sess.detected_company,
                    "draft_premium": _q2(fields.get("premium")),
                    "draft_motor_premium": _q2(fields.get("motor_premium")),
                    "draft_total_payable": _q2(fields.get("total_payable")),
                    "draft_total_amount": _q2(fields.get("total_amount")),
                    "entry_motor_premium": [_q2(c.motor_premium) for c in ce_list],
                    "entry_towing": [c.towing_limit for c in ce_list],
                }
                if sess.id == target_sid or report["vqe8_or_target_session"] is None:
                    report["vqe8_or_target_session"] = {
                        k: (str(v) if isinstance(v, Decimal) else [str(x) for x in v] if isinstance(v, list) and v and isinstance(v[0], Decimal) else v)
                        for k, v in info.items()
                    }

            # 1. Backfill missing draft.company_id / uploaded_file.insurance_company_id
            comp_id = resolve_session_company_id(sess)
            if not comp_id:
                comp_id = _match_company_id(sess.detected_company, companies)
            if comp_id and not draft.company_id:
                report["company_links_repaired"].append({"session_id": sess.id, "draft_id": draft.id, "company_id": comp_id})
                if apply_changes:
                    backup_records.append({"kind": "draft_company", "draft_id": draft.id, "old_company_id": draft.company_id})
                    draft.company_id = comp_id
                    if uf and not uf.insurance_company_id:
                        uf.insurance_company_id = comp_id
                if sess.tenure_id:
                    affected_tenures.add(str(sess.tenure_id))

            # 2. Heal split-brain / subtraction drafts
            uw_dec, reason = _detect_split_brain_uw_premium(draft, rec)
            if uw_dec is not None and reason:
                report["drafts_repaired"].append(
                    {
                        "session_id": sess.id,
                        "draft_id": draft.id,
                        "old_premium": str(_q2(fields.get("premium"))),
                        "old_motor_premium": str(_q2(fields.get("motor_premium"))),
                        "new_uw_motor_premium": str(uw_dec),
                        "reason": reason,
                    }
                )
                if apply_changes:
                    backup_records.append({"kind": "draft_fields", "draft_id": draft.id, "old_fields": dict(draft.fields or {})})
                    old_prem_val = _q2(fields.get("premium"))
                    sync_draft_motor_premium_aliases(fields, uw_dec)
                    cur_tot_amt = _q2(fields.get("total_amount"))
                    if uw_dec != old_prem_val or cur_tot_amt <= _ZERO:
                        tenure = sess.tenure
                        pct_dec = _q2(getattr(tenure, "motor_discount_pct", _ZERO)) if tenure else _q2(fields.get("motor_discount_pct"))
                        flat_dec = _q2(getattr(tenure, "quotation_discount", _ZERO)) if tenure else _q2(fields.get("quotation_discount"))
                        inc_rt = (tenure.include_road_tax is not False) if tenure else (str(_extract_val_text(fields.get("include_road_tax"))).lower() == "true")
                        inc_rf = (tenure.include_runner_fee is not False) if tenure else (str(_extract_val_text(fields.get("include_runner_fee"))).lower() == "true")
                        rt_dec = _q2(tenure.road_tax if tenure else (fields.get("roadtax") or fields.get("road_tax_amount"))) if inc_rt else _ZERO
                        rf_dec = _q2(tenure.runner_fee if tenure else (fields.get("service_fee") or fields.get("runner_fee"))) if inc_rf else _ZERO
                        disc_bd = calculate_motor_discount(uw_dec, pct_dec, flat_dec)
                        fields["motor_discount_pct"] = {"value": f"{disc_bd.motor_discount_pct:.2f}", "status": "ready"}
                        fields["motor_discount_amount"] = {"value": f"{disc_bd.pct_discount_amount:.2f}", "status": "ready"}
                        fields["quotation_discount"] = {"value": f"{disc_bd.flat_discount_amount:.2f}", "status": "ready"}
                        fields["effective_discount"] = {"value": f"{disc_bd.effective_discount:.2f}", "status": "ready"}
                        fields["net_motor_premium"] = {"value": f"{disc_bd.net_motor_premium:.2f}", "status": "ready"}
                        fields["total_amount"] = {"value": f"{disc_bd.net_total_payable(rt_dec, rf_dec):.2f}", "detected_value": f"{uw_dec:.2f}", "status": "ready"}
                    draft.fields = fields
                    flag_modified(draft, "fields")
                if sess.tenure_id:
                    affected_tenures.add(str(sess.tenure_id))
                    rematerialize_tenures.add(str(sess.tenure_id))

            # 3. Detect Entry <-> Workspace drift for non-overridden TenureComparisonEntries
            for ce in entries_by_session.get(sess.id, []):
                target_mp = uw_dec if uw_dec is not None else resolve_canonical_motor_premium_decimal(fields)
                if not is_field_overridden(ce, "motor_premium") and target_mp > _ZERO and abs(_q2(ce.motor_premium) - target_mp) > _CENT:
                    if sess.tenure_id:
                        affected_tenures.add(str(sess.tenure_id))
                        rematerialize_tenures.add(str(sess.tenure_id))
                if comp_id and ce.company_id != comp_id:
                    if sess.tenure_id:
                        affected_tenures.add(str(sess.tenure_id))

        # Check tenures needing materialization / sync
        all_tenures = list(db.scalars(select(InsuranceTenure).where(InsuranceTenure.is_discarded.is_(False))).all())
        tenures_by_id = {str(t.id): t for t in all_tenures}
        for t in all_tenures:
            if str(t.id) in affected_tenures:
                report["tenures_re_materialized"].append({"tenure_id": t.id, "vehicle_no": t.vehicle_no})

        if apply_changes and (backup_records or affected_tenures):
            for tid in sorted(affected_tenures):
                for sess in sessions_by_tenure.get(tid, []):
                    target_mp = resolve_canonical_motor_premium_decimal(sess.draft.fields)
                    s_cid = resolve_session_company_id(sess) or _match_company_id(sess.detected_company, companies)
                    for ce in entries_by_session.get(sess.id, []):
                        need_cid = bool(s_cid and ce.company_id != s_cid)
                        need_mp = not is_field_overridden(ce, "motor_premium") and target_mp > _ZERO and abs(_q2(ce.motor_premium) - target_mp) > _CENT
                        if need_cid or need_mp:
                            backup_records.append(
                                {
                                    "kind": "comparison_entry",
                                    "entry_id": ce.id,
                                    "old_company_id": ce.company_id,
                                    "old_motor_premium": str(ce.motor_premium),
                                    "old_total_payable": str(ce.total_payable),
                                }
                            )
                        if need_cid:
                            ce.company_id = s_cid
                        if need_mp:
                            ce.motor_premium = target_mp
                            rt_e = _q2(ce.road_tax) if (ce.include_road_tax is not False) else _ZERO
                            rf_e = _q2(ce.runner_fee) if (ce.include_runner_fee is not False) else _ZERO
                            ce.total_payable = (target_mp + rt_e + rf_e).quantize(_CENT, rounding=ROUND_HALF_UP)
                            si_e = _q2(ce.sum_insured)
                            if si_e > _ZERO:
                                ce.rate_percentage = ((target_mp / si_e) * _HUNDRED).quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)
                t_obj = tenures_by_id.get(tid)
                t_entries = entries_by_tenure.get(tid, [])
                if t_obj and t_entries:
                    rank_comparison_entries(
                        t_entries,
                        explicit_winning_company_id=t_obj.winning_company_id,
                        explicit_winning_ref=t_obj.winning_quotation_ref,
                        auto_recommend_rank1=False,
                    )

            qctmp = ROOT / ".qc-tmp"
            qctmp.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_file = qctmp / f"pre_v32_quote_sync_backup_{ts}.json"
            backup_file.write_text(json.dumps(backup_records, indent=2, default=str), encoding="utf-8")
            report["backup_path"] = str(backup_file)
            db.commit()

            for tid in sorted(rematerialize_tenures):
                materialize_comparison_entries(db, tid)

    return report


def _extract_val_text(raw: Any) -> Any:
    return raw.get("value") if isinstance(raw, dict) else raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit & repair historical quote/comparison sync drift.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Inspect without writing to the database.")
    mode.add_argument("--apply", action="store_true", help="Backup modified rows to .qc-tmp and apply repairs.")
    args = parser.parse_args()

    result = run_audit_and_repair(apply_changes=bool(args.apply))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
