"""Marketing Comparison Service

Provides side-by-side multi-underwriter comparison, rate computation,
Excel 1:1 parity financial modeling, manual quote sourcing, WhatsApp teaser formatting,
and winner handoff to the Risk-Locker Quotation Builder.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.tables import (
    AccountStatus,
    Batch,
    BenefitConcept,
    CompanyBenefitCondition,
    CustomerAccount,
    DraftBenefitSelection,
    ExtractionBenefitLine,
    ExtractionRecord,
    InsuranceCompany,
    InsuranceTenure,
    Job,
    QuotationDraft,
    RecordStatus,
    Session as SessionModel,
    StorageStatus,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.customer_account_service import resolve_or_create_customer

logger = logging.getLogger(__name__)

# Malaysian Private Car NCD Rate Scale (ordered 1st year to 6th+ year max)
NCD_RATE_SCALE = [0.0, 25.0, 30.0, 38.33, 45.0, 55.0]


def calculate_ncd_pair(ncd_value: float | None) -> tuple[float | None, float | None]:
    """Calculate (current_ncd, next_ncd) according to Malaysian Private Car NCD Rate Scale.
    
    The scale is:
    0% (1st Yr) -> 25% (2nd Yr) -> 30% (3rd Yr) -> 38.33% (4th Yr) -> 45% (5th Yr) -> 55% (6th+ Yr).
    
    The PDF quotation displays the upcoming policy's NCD (next_ncd).
    The previous tenure's NCD (current_ncd) is one step below in the scale.
    """
    if ncd_value is None:
        return None, None
    try:
        val = float(ncd_value)
    except (ValueError, TypeError):
        return None, None

    if val < 0.0:
        return None, None

    # Find closest tier in NCD_RATE_SCALE
    best_idx = 0
    min_diff = float("inf")
    for idx, tier in enumerate(NCD_RATE_SCALE):
        diff = abs(tier - val)
        if diff < min_diff:
            min_diff = diff
            best_idx = idx

    next_ncd = NCD_RATE_SCALE[best_idx]
    prev_idx = max(0, best_idx - 1)
    current_ncd = NCD_RATE_SCALE[prev_idx]
    return current_ncd, next_ncd


def _extract_ncd_from_draft(f: dict[str, Any]) -> float | None:
    """Extract numeric NCD percentage from draft fields."""
    cand = f.get("ncd_percent") or f.get("ncd_percentage") or f.get("ncd") or f.get("ncb") or f.get("ncb_percentage")
    if cand is None or cand == "":
        return None
    if isinstance(cand, (int, float)):
        val = float(cand)
        if 0.0 <= val <= 55.0:
            return val
        return None
    s = str(cand).strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            val = float(m.group(1))
            if 0.0 <= val <= 55.0:
                return val
        except (ValueError, TypeError):
            pass
    return None


def _extract_val(val: Any) -> Any:
    """Recursively unwrap ExtractionField dictionary objects."""
    if isinstance(val, dict):
        return _extract_val(val.get("value"))
    return val


def _to_float(val: Any) -> float:
    raw = _extract_val(val)
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float, Decimal)):
        return float(raw)
    try:
        # Strip currency symbols, commas, and whitespace
        s = str(raw).replace("RM", "").replace("rm", "").replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _safe_str(val: Any) -> str:
    raw = _extract_val(val)
    if raw is None:
        return ""
    return str(raw).strip()


def detect_runner_fee_from_id(ic_or_passport: str | None) -> float:
    """Auto-detect runner fee based on Malaysian IC vs International Passport.

    Rules:
    - Customer ID starts with letters (e.g. K1584766Z, A12345678) -> International Passport -> RM 20.00.
    - Customer ID starts with digits (YYMMDD...) -> Malaysian National ID (MyKad) -> RM 10.00.
    - Missing / undetectable -> Default = RM 10.00.
    """
    if not ic_or_passport:
        return 10.0
    cleaned = ic_or_passport.strip().upper()
    if not cleaned:
        return 10.0
    if cleaned[0].isalpha():
        return 20.0
    return 10.0


def _extract_vehicle_sum_insured(f: dict[str, Any]) -> float:
    """Disambiguate vehicle sum insured from accessory endorsement limits (e.g. windscreen RM 4,000)."""
    c_cov = _to_float(f.get("coverage_amount"))
    c_sum = _to_float(f.get("sum_insured"))
    c_mkt = _to_float(f.get("market_value"))
    c_agr = _to_float(f.get("agreed_value"))

    # Malaysian motor vehicles typically have sum insured >= RM 10,000.
    # Exclude add-on sub-limits (like windscreen RM 4,000) when vehicle-level coverage is available.
    major_candidates = [c for c in [c_cov, c_mkt, c_agr, c_sum] if c >= 10000.0]
    if major_candidates:
        if c_cov >= 10000.0:
            return c_cov
        return max(major_candidates)

    all_candidates = [c for c in [c_sum, c_cov, c_mkt, c_agr] if c > 0.0]
    return max(all_candidates) if all_candidates else 0.0


def _extract_vehicle_motor_premium(f: dict[str, Any]) -> float:
    """Extract motor insurance premium payable to underwriter (including SST and stamp duty)."""
    total_amt = _to_float(f.get("total_amount") or f.get("total_payable"))
    if total_amt > 0.0:
        return total_amt
    gross = _to_float(f.get("gross_premium"))
    if gross > 0.0:
        return gross
    return _to_float(f.get("basic_premium") or f.get("premium") or f.get("insurance_premium"))


def _extract_valuation_type(f: dict[str, Any]) -> tuple[str, bool]:
    """Determine agreed value vs market value."""
    val_type_str = _safe_str(f.get("valuation_type")).lower()
    agr_val = _extract_val(f.get("agreed_value"))
    is_agreed = (
        "agreed" in val_type_str
        or agr_val in [True, "Yes", "yes", "true", "True", "1"]
    )
    if is_agreed:
        return "agreed_value", True
    return "market_value", False


def _extract_excess(f: dict[str, Any]) -> float:
    return _to_float(f.get("excess_amount")) or _to_float(f.get("compulsory_excess")) or _to_float(f.get("excess"))


def _resolve_comparison_benefits(
    db: Session,
    session: SessionModel,
    company_id: str | None,
    f: dict[str, Any],
    windscreen_target: float | None = None,
) -> dict[str, Any]:
    """Single source of truth for extracting Special Perils, Windscreen, LLP, and Towing.
    
    Reads from:
    1. DraftBenefitSelection records
    2. ExtractionBenefitLine records
    3. CompanyBenefitCondition dynamic rules
    4. QuotationDraft scalar fields
    """
    tokens: list[str] = []
    
    # 1. Draft Benefit Selections
    draft_id = session.draft_id
    selections: list[DraftBenefitSelection] = []
    if draft_id:
        selections = list(
            db.scalars(
                select(DraftBenefitSelection).where(DraftBenefitSelection.draft_id == draft_id)
            ).all()
        )
    
    concept_ids = {s.concept_id for s in selections if s.concept_id}
    concepts: dict[str, BenefitConcept] = {}
    if concept_ids:
        c_list = list(db.scalars(select(BenefitConcept).where(BenefitConcept.id.in_(concept_ids))).all())
        concepts = {c.id: c for c in c_list}
        
    for s in selections:
        if s.label_override:
            tokens.append(s.label_override)
        if s.selection_key:
            tokens.append(s.selection_key)
        c = concepts.get(s.concept_id) if s.concept_id else None
        if c:
            if c.label:
                tokens.append(c.label)
            if c.concept_key:
                tokens.append(c.concept_key)
                
    # 2. Extraction Benefit Lines
    if session.uploaded_file_id:
        ext_lines = list(
            db.scalars(
                select(ExtractionBenefitLine)
                .join(ExtractionRecord, ExtractionBenefitLine.extraction_record_id == ExtractionRecord.id)
                .where(ExtractionRecord.uploaded_file_id == session.uploaded_file_id)
            ).all()
        )
        for el in ext_lines:
            if el.raw_label:
                tokens.append(el.raw_label)
            if el.normalized_label:
                tokens.append(el.normalized_label)
                
    # 3. Add raw fields text
    for k in ("special_perils", "optional_covers", "benefits_selected", "extra_benefits", "llp_llop", "towing", "towing_limit", "windscreen_coverage", "windscreen_sum_insured"):
        val = f.get(k)
        if val:
            if isinstance(val, list):
                tokens.extend(str(item) for item in val)
            else:
                tokens.append(str(val))

    combined_text = " ".join(tokens).lower()

    # --- SPECIAL PERILS ---
    # Only genuine perils: flood, typhoon, storm, landslide, peril khas, special perils
    has_special_perils = any(
        kw in combined_text
        for kw in (
            "special perils",
            "special peril",
            "peril khas",
            "perils khas",
            "banjir",
            "flood",
            "storm",
            "ribut",
            "typhoon",
            "landslide",
            "tanah runtuh",
            "convulsion of nature",
            "natural disaster",
            "act of god",
        )
    )
    special_perils_val = "Included" if has_special_perils else None

    # --- WINDSCREEN ---
    windscreen_amount: float | None = None
    cand_ws = _to_float(f.get("windscreen_coverage") or f.get("windscreen_sum_insured"))
    if cand_ws > 0.0:
        windscreen_amount = cand_ws
    else:
        for s in selections:
            s_text = f"{s.label_override or ''} {s.selection_key or ''}".lower()
            if "windscreen" in s_text or "cermin" in s_text:
                if isinstance(s.typed_value_override, dict):
                    t_amt = _to_float(s.typed_value_override.get("amount") or s.typed_value_override.get("coverage") or s.typed_value_override.get("limit"))
                    if t_amt > 0.0:
                        windscreen_amount = t_amt
                        break
                m = re.search(r"(?:rm|myr)?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[1-9][0-9]{2,6}(?:\.[0-9]+)?)", s.label_override or "", re.IGNORECASE)
                if m:
                    amt = _to_float(m.group(1).replace(",", ""))
                    if amt > 0.0:
                        windscreen_amount = amt
                        break
        if windscreen_amount is None:
            for tok in tokens:
                if "windscreen" in tok.lower() or "cermin" in tok.lower():
                    m = re.search(r"(?:rm|myr)?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[1-9][0-9]{2,6}(?:\.[0-9]+)?)", tok, re.IGNORECASE)
                    if m:
                        amt = _to_float(m.group(1).replace(",", ""))
                        if amt > 0.0:
                            windscreen_amount = amt
                            break
            if windscreen_amount is None and ("windscreen" in combined_text or "cermin" in combined_text):
                if windscreen_target and windscreen_target > 0.0:
                    windscreen_amount = float(windscreen_target)

    # --- LLP / LLOP ---
    has_llp = any(
        kw in combined_text
        for kw in (
            "legal liability to passenger",
            "legal liability of passenger",
            "liability to passenger",
            "liability of passenger",
            "llp",
            "llop",
        )
    )
    llp_val = "Included" if has_llp else None

    # --- TOWING ---
    towing_limit_val: str | None = None
    target_comp_id = company_id or getattr(session, "company_id", None)
    if target_comp_id:
        conditions = list(
            db.scalars(
                select(CompanyBenefitCondition).where(
                    CompanyBenefitCondition.company_id == target_comp_id,
                    CompanyBenefitCondition.is_active == True,
                )
            ).all()
        )
        for cond in conditions:
            filter_text = (cond.trigger_plan_filter or "").strip().lower()
            if filter_text and filter_text in combined_text:
                if cond.replacement_description:
                    towing_limit_val = cond.replacement_description.strip()
                    break

    if not towing_limit_val:
        if any(kw in combined_text for kw in ("motor pa plus 4", "driver plus plan 4", "driver plus 4", "unlimited towing", "24-hr unlimited", "24 hour unlimited")):
            towing_limit_val = "Unlimited"

    if not towing_limit_val:
        raw_towing = _safe_str(f.get("towing_limit") or f.get("towing"))
        towing_limit_val = raw_towing if raw_towing else "Unlimited"

    return {
        "special_perils": special_perils_val,
        "windscreen_sum_insured": windscreen_amount,
        "llp_llop": llp_val,
        "towing_limit": towing_limit_val,
    }


def get_marketing_comparison(db: Session, tenure_id: str) -> dict[str, Any]:
    """Retrieve or auto-hydrate the full marketing comparison matrix for an insurance tenure.
    
    Returns:
        Structured comparison payload containing:
        - tenure metadata & fixed costs (road tax + runner fee)
        - side-by-side underwriter comparison columns
        - previous policy year reference card (Year - 1)
        - recommended sum insured / valuation matrix
        - NCD status
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    # 1. Inspect existing comparison entries
    entries = list(
        db.scalars(
            select(TenureComparisonEntry)
            .where(TenureComparisonEntry.tenure_id == tenure_id)
            .order_by(TenureComparisonEntry.sort_order.asc(), TenureComparisonEntry.created_at.asc())
        ).all()
    )

    needs_commit = False

    # 2. Query all linked sessions under this tenure (with preloaded drafts)
    sessions = list(
        db.scalars(
            select(SessionModel)
            .options(selectinload(SessionModel.draft))
            .where(
                SessionModel.tenure_id == tenure_id,
                SessionModel.status != "trash",
            )
            .order_by(SessionModel.created_at.asc())
        ).all()
    )
    session_map = {s.id: s for s in sessions}

    # Gather candidate customer IC / passport for runner fee detection
    cand_ic = ""
    for s in sessions:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not cand_ic:
                cand_ic = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))

    # Detect road tax and runner fee only if tenure fixed costs are uninitialized (0.0)
    road_tax_val = float(tenure.road_tax)
    runner_fee_val = float(tenure.runner_fee)

    if road_tax_val == 0.0 or runner_fee_val == 0.0:
        for s in sessions:
            if s.draft and s.draft.fields:
                f = s.draft.fields
                cand_rt = _to_float(f.get("road_tax") or f.get("roadtax"))
                if road_tax_val == 0.0 and cand_rt > 0.0:
                    road_tax_val = cand_rt
                cand_rf = _to_float(f.get("runner_fee") or f.get("runner"))
                if runner_fee_val == 0.0 and cand_rf > 0.0:
                    runner_fee_val = cand_rf

        # Auto-detect runner fee from Malaysian MyKad vs International Passport if still 0.0
        if runner_fee_val == 0.0:
            runner_fee_val = detect_runner_fee_from_id(cand_ic)

        if road_tax_val != float(tenure.road_tax) or runner_fee_val != float(tenure.runner_fee):
            tenure.road_tax = road_tax_val
            tenure.runner_fee = runner_fee_val
            needs_commit = True

    # 3. If no entries exist yet, auto-hydrate from sessions under this tenure
    if not entries:
        for idx, s in enumerate(sessions):
            comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{idx+1}")
            f = s.draft.fields if s.draft and s.draft.fields else {}

            sum_ins = _extract_vehicle_sum_insured(f)
            motor_prem = _extract_vehicle_motor_premium(f)
            val_type, agreed = _extract_valuation_type(f)
            betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
            excess_val = _extract_excess(f)
            rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
            tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

            b_res = _resolve_comparison_benefits(
                db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
            )

            entry = TenureComparisonEntry(
                tenure_id=tenure_id,
                session_id=s.id,
                company_name=comp_name,
                company_id=getattr(s, "company_id", None),
                sum_insured=sum_ins,
                valuation_type=val_type,
                motor_premium=motor_prem,
                road_tax=float(tenure.road_tax),
                runner_fee=float(tenure.runner_fee),
                total_payable=tot_pay,
                towing_limit=b_res["towing_limit"] or "Unlimited",
                agreed_value=agreed,
                waiver_betterment=betterment,
                excess=excess_val,
                rate_percentage=rate_val,
                windscreen_sum_insured=b_res["windscreen_sum_insured"],
                special_perils=b_res["special_perils"],
                llp_llop=b_res["llp_llop"],
                sort_order=idx,
                is_recommended=bool(
                    (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                    or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                ),
            )
            db.add(entry)
            entries.append(entry)

        needs_commit = True
    else:
        # Synchronize any sessions under this tenure that don't have a comparison entry yet
        existing_sess_ids = {e.session_id for e in entries if e.session_id}
        unlinked_sessions = [s for s in sessions if s.id not in existing_sess_ids]
        if unlinked_sessions:
            for idx, s in enumerate(unlinked_sessions):
                comp_name = s.detected_company or (s.uploaded_file.original_filename if s.uploaded_file else f"Quote #{len(entries)+idx+1}")
                f = s.draft.fields if s.draft and s.draft.fields else {}

                sum_ins = _extract_vehicle_sum_insured(f)
                motor_prem = _extract_vehicle_motor_premium(f)
                val_type, agreed = _extract_valuation_type(f)
                betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
                excess_val = _extract_excess(f)
                rate_val = round((motor_prem / sum_ins) * 100, 4) if sum_ins > 0 else None
                tot_pay = motor_prem + float(tenure.road_tax) + float(tenure.runner_fee)

                b_res = _resolve_comparison_benefits(
                    db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
                )

                new_entry = TenureComparisonEntry(
                    tenure_id=tenure_id,
                    session_id=s.id,
                    company_name=comp_name,
                    company_id=getattr(s, "company_id", None),
                    sum_insured=sum_ins,
                    valuation_type=val_type,
                    motor_premium=motor_prem,
                    road_tax=float(tenure.road_tax),
                    runner_fee=float(tenure.runner_fee),
                    total_payable=tot_pay,
                    towing_limit=b_res["towing_limit"] or "Unlimited",
                    agreed_value=agreed,
                    waiver_betterment=betterment,
                    excess=excess_val,
                    rate_percentage=rate_val,
                    windscreen_sum_insured=b_res["windscreen_sum_insured"],
                    special_perils=b_res["special_perils"],
                    llp_llop=b_res["llp_llop"],
                    sort_order=len(entries) + idx,
                    is_recommended=bool(
                        (tenure.winning_quotation_ref and s.quotation_ref == tenure.winning_quotation_ref)
                        or (tenure.winning_company_id and getattr(s, "company_id", None) == tenure.winning_company_id)
                    ),
                )
                db.add(new_entry)
                entries.append(new_entry)
            needs_commit = True

        # Auto-healing: If existing entries hold zeroed sum_insured or motor_premium
        for e in entries:
            # Sync runner fee from tenure if entry is 0.0
            if float(e.runner_fee) == 0.0 and float(tenure.runner_fee) > 0.0:
                e.runner_fee = float(tenure.runner_fee)
                e.total_payable = float(e.motor_premium) + float(e.road_tax) + float(e.runner_fee)
                needs_commit = True

            if e.session_id:
                s = session_map.get(e.session_id)
                if s and s.draft and s.draft.fields:
                    f = s.draft.fields
                    h_sum = _extract_vehicle_sum_insured(f)
                    h_prem = _extract_vehicle_motor_premium(f)
                    val_type, is_agr = _extract_valuation_type(f)

                    # Check if entry needs financial or benefit auto-healing
                    needs_healing = (
                        e.sum_insured == 0.0
                        or e.motor_premium == 0.0
                        or (e.special_perils and any(bad in e.special_perils.lower() for bad in ("windscreen", "passenger", "llp", "driver")))
                    )

                    if needs_healing:
                        b_res = _resolve_comparison_benefits(
                            db, s, getattr(s, "company_id", None), f, float(tenure.windscreen_target) if tenure.windscreen_target else None
                        )
                        if h_sum > 0.0:
                            e.sum_insured = h_sum
                        if h_prem > 0.0:
                            e.motor_premium = h_prem
                        e.valuation_type = val_type
                        e.agreed_value = is_agr
                        e.excess = _extract_excess(f)
                        e.towing_limit = b_res["towing_limit"] or "Unlimited"
                        e.waiver_betterment = _extract_val(f.get("waiver_of_betterment")) in [True, "Yes", "yes", "true", "True", "1"]
                        e.windscreen_sum_insured = b_res["windscreen_sum_insured"]
                        e.special_perils = b_res["special_perils"]
                        e.llp_llop = b_res["llp_llop"]

                        e.road_tax = float(tenure.road_tax)
                        e.runner_fee = float(tenure.runner_fee)
                        e.total_payable = float(e.motor_premium) + e.road_tax + e.runner_fee
                        if e.sum_insured > 0.0:
                            e.rate_percentage = round((float(e.motor_premium) / float(e.sum_insured)) * 100, 4)
                        needs_commit = True

    if needs_commit:
        db.commit()


    # 3. Retrieve Previous Policy (Year - 1 / 365 Days Prior)
    prev_tenure = db.scalar(
        select(InsuranceTenure)
        .where(
            InsuranceTenure.tracked_vehicle_id == tenure.tracked_vehicle_id,
            InsuranceTenure.id != tenure.id,
            InsuranceTenure.coverage_start_date < tenure.coverage_start_date,
        )
        .order_by(InsuranceTenure.coverage_start_date.desc())
        .limit(1)
    )

    prev_policy_data = None
    if prev_tenure:
        prev_entries = list(
            db.scalars(
                select(TenureComparisonEntry)
                .where(TenureComparisonEntry.tenure_id == prev_tenure.id)
                .order_by(TenureComparisonEntry.is_recommended.desc(), TenureComparisonEntry.total_payable.asc())
            ).all()
        )
        best_prev = prev_entries[0] if prev_entries else None
        prev_policy_data = {
            "year": prev_tenure.coverage_start_date.year,
            "period": f"{prev_tenure.coverage_start_date.strftime('%d/%m/%Y')} - {prev_tenure.coverage_end_date.strftime('%d/%m/%Y')}",
            "insurer": (prev_tenure.winning_company.name if prev_tenure.winning_company else None) or (best_prev.company_name if best_prev else "Previous Insurer"),
            "sum_insured": float(best_prev.sum_insured) if best_prev else 0.0,
            "insurance_premium": float(prev_tenure.won_premium) if prev_tenure.won_premium is not None else (float(best_prev.motor_premium) if best_prev else 0.0),
            "perils": "LLP, LLOP, PA",
            "model": tenure.tracked_vehicle.car_model if tenure.tracked_vehicle else "Standard Model",
            "yom": getattr(tenure.tracked_vehicle, "manufacture_year", None) or 2023,
            "sub_agent": "RM_01_EugeneLee",
        }

    # 4. Formulate Recommended Sum Insured matrix
    # 4. Formulate Recommended Sum Insured matrix (genuine underwriter figures only)
    rec_sum_insured = tenure.recommended_sum_insured_json or {}
    if (not rec_sum_insured or all(v == 0.0 for v in rec_sum_insured.values())) and entries:
        rec_sum_insured = {}
        for e in entries:
            clean_c = e.company_name.split()[0]
            if float(e.sum_insured) > 0.0:
                rec_sum_insured[clean_c] = float(e.sum_insured)

    # Aggregate customer & vehicle metadata from linked sessions and master records
    linked_sessions = list(reversed(sessions))

    cust_ic = ""
    cust_phone = ""
    cust_email = ""
    cust_address = ""
    veh_engine_no = ""
    veh_chassis_no = ""
    veh_yom = None
    veh_seating = ""
    veh_engine_cc = ""
    veh_model = ""

    if tenure.customer:
        cust_ic = tenure.customer.id_number or ""
        cust_phone = tenure.customer.phone or ""
        cust_email = tenure.customer.email or ""
        cust_address = tenure.customer.address or ""

    if tenure.tracked_vehicle:
        veh_engine_no = tenure.tracked_vehicle.engine_no or ""
        veh_chassis_no = tenure.tracked_vehicle.chassis_no or ""
        veh_engine_cc = tenure.tracked_vehicle.engine_cc or ""
        veh_model = tenure.tracked_vehicle.car_model or ""
        veh_yom = getattr(tenure.tracked_vehicle, "manufacture_year", None)

    for s in linked_sessions:
        if s.draft and isinstance(s.draft.fields, dict):
            f = s.draft.fields
            if not cust_ic:
                cust_ic = _safe_str(f.get("ic_no") or f.get("nric") or f.get("ic_or_brn") or f.get("passport_no"))
            if not cust_phone:
                cust_phone = _safe_str(f.get("phone_number") or f.get("contact_no") or f.get("mobile"))
            if not cust_email:
                cust_email = _safe_str(f.get("email"))
            if not cust_address:
                cust_address = _safe_str(f.get("address") or f.get("location"))
            if not veh_engine_no:
                veh_engine_no = _safe_str(f.get("engine_number") or f.get("engine_no"))
            if not veh_chassis_no:
                veh_chassis_no = _safe_str(f.get("chassis_number") or f.get("chassis_no") or f.get("vin"))
            if not veh_engine_cc:
                veh_engine_cc = _safe_str(f.get("engine_cc") or f.get("capacity"))
            if not veh_model:
                veh_model = _safe_str(f.get("car_model") or f.get("vehicle_model"))
            if not veh_yom:
                raw_yom = f.get("manufacture_year") or f.get("year_of_manufacture") or f.get("yom")
                if raw_yom:
                    try:
                        veh_yom = int(_safe_str(raw_yom))
                    except (ValueError, TypeError):
                        pass
    # 4. Resolve NCD and In-Flight Jobs
    cand_ncd: float | None = None
    if tenure.ncd_percentage is not None:
        cand_ncd = float(tenure.ncd_percentage)
    else:
        for s in sessions:
            if s.draft and isinstance(s.draft.fields, dict):
                ext_ncd = _extract_ncd_from_draft(s.draft.fields)
                if ext_ncd is not None:
                    cand_ncd = ext_ncd
                    tenure.ncd_percentage = cand_ncd
                    needs_commit = True
                    break

    current_ncd, next_ncd = calculate_ncd_pair(cand_ncd)

    # Count pending/processing jobs
    pending_jobs_count = 0
    session_ids = [s.id for s in sessions]
    if session_ids:
        pending_jobs_count = db.scalar(
            select(func.count(Job.id)).where(
                Job.session_id.in_(session_ids),
                Job.state.in_(["queued", "claimed", "processing", "extracting", "saving_review"]),
            )
        ) or 0
    elif tenure.id:
        pending_jobs_count = db.scalar(
            select(func.count(Job.id)).where(
                Job.state.in_(["queued", "claimed", "processing", "extracting", "saving_review"]),
                Job.payload["tenure_id"].as_string() == tenure.id,
            )
        ) or 0

    if needs_commit:
        db.commit()

    # 5. Format Entry Payloads
    entry_dicts = []
    for e in entries:
        entry_dicts.append({
            "id": e.id,
            "tenure_id": e.tenure_id,
            "session_id": e.session_id,
            "company_name": e.company_name,
            "company_id": e.company_id,
            "sum_insured": float(e.sum_insured),
            "valuation_type": e.valuation_type,
            "motor_premium": float(e.motor_premium),
            "road_tax": float(e.road_tax),
            "runner_fee": float(e.runner_fee),
            "total_payable": float(e.total_payable),
            "towing_limit": e.towing_limit,
            "agreed_value": e.agreed_value,
            "waiver_betterment": e.waiver_betterment,
            "excess": float(e.excess),
            "rate_percentage": float(e.rate_percentage) if e.rate_percentage is not None else None,
            "windscreen_sum_insured": float(e.windscreen_sum_insured) if e.windscreen_sum_insured else None,
            "special_perils": e.special_perils,
            "llp_llop": e.llp_llop,
            "personal_accident": e.personal_accident,
            "is_recommended": e.is_recommended,
            "is_manual": e.is_manual,
            "sort_order": e.sort_order,
            "notes": e.notes,
        })

    return {
        "tenure": {
            "id": tenure.id,
            "vehicle_no": tenure.vehicle_no,
            "customer_name": tenure.customer_name,
            "ic_no": cust_ic,
            "phone": cust_phone,
            "email": cust_email,
            "address": cust_address,
            "engine_cc": veh_engine_cc or "1496 CC",
            "engine_no": veh_engine_no,
            "chassis_no": veh_chassis_no,
            "manufacture_year": veh_yom or 2023,
            "seating_capacity": veh_seating or "5",
            "coverage_start_date": tenure.coverage_start_date.isoformat(),
            "coverage_end_date": tenure.coverage_end_date.isoformat(),
            "coverage_period_formatted": f"{tenure.coverage_start_date.strftime('%d/%m/%Y')} - {tenure.coverage_end_date.strftime('%d/%m/%Y')}",
            "expiry_month": tenure.expiry_month,
            "status": tenure.status,
            "road_tax": float(tenure.road_tax),
            "runner_fee": float(tenure.runner_fee),
            "runner_fee_type": "passport" if ((cust_ic or cand_ic).strip() and (cust_ic or cand_ic).strip()[0].isalpha()) else "mykad",
            "fixed_costs_total": float(tenure.road_tax + tenure.runner_fee),
            "windscreen_target": float(tenure.windscreen_target) if tenure.windscreen_target else None,
            "ncd_percentage": float(tenure.ncd_percentage) if tenure.ncd_percentage is not None else None,
            "vehicle_model": veh_model or "Motor Vehicle",
            "vehicle_type": "Comprehensive (综合险)",
        },
        "entries": entry_dicts,
        "previous_policy": prev_policy_data,
        "recommended_sum_insured": rec_sum_insured,
        "ncd": {
            "current": current_ncd,
            "next": next_ncd,
        },
        "pending_jobs_count": pending_jobs_count,
    }


def update_tenure_fixed_costs(
    db: Session,
    tenure_id: str,
    *,
    road_tax: float,
    runner_fee: float,
    windscreen_target: float | None = None,
    ncd_percentage: float | None = None,
    coverage_start_date: str | None = None,
    coverage_end_date: str | None = None,
    customer_name: str | None = None,
    ic_no: str | None = None,
    engine_cc: str | None = None,
    engine_no: str | None = None,
    chassis_no: str | None = None,
    vehicle_model: str | None = None,
) -> dict[str, Any]:
    """Update fixed tenure expenses (Road Tax & Runner Fee), coverage dates, vehicle specs, and recalculate total payables for all columns."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    tenure.road_tax = road_tax
    if runner_fee > 0.0:
        tenure.runner_fee = runner_fee
    elif ic_no and ic_no.strip():
        tenure.runner_fee = detect_runner_fee_from_id(ic_no.strip())
    else:
        tenure.runner_fee = runner_fee
    if windscreen_target is not None:
        tenure.windscreen_target = windscreen_target
    if ncd_percentage is not None:
        tenure.ncd_percentage = ncd_percentage

    if customer_name and customer_name.strip():
        tenure.customer_name = customer_name.strip()

    # Link/resolve CustomerAccount and persist government ID & propagate across tenures
    if (ic_no and ic_no.strip()) or (customer_name and customer_name.strip()):
        cust = tenure.customer or (db.get(CustomerAccount, tenure.customer_id) if tenure.customer_id else None)
        if not cust:
            cust, _ = resolve_or_create_customer(
                db,
                raw_name=customer_name or tenure.customer_name,
                raw_id=ic_no,
            )
        if cust:
            tenure.customer_id = cust.id
            if customer_name and customer_name.strip():
                cust.canonical_name = customer_name.strip()
            if ic_no and ic_no.strip():
                from app.services.identity_normalization_service import normalize_government_id
                norm_id, norm_type = normalize_government_id(ic_no.strip())
                cust.id_number = norm_id or ic_no.strip()
                if norm_type:
                    cust.id_type = norm_type
            from sqlalchemy import update, or_
            db.execute(
                update(InsuranceTenure)
                .where(InsuranceTenure.customer_id == cust.id)
                .values(customer_name=cust.canonical_name)
            )

            # Also propagate customer name and IC to all quotation drafts under this customer/tenure
            sessions_to_sync = list(
                db.scalars(
                    select(SessionModel).where(
                        or_(
                            SessionModel.customer_id == cust.id,
                            SessionModel.tenure_id == tenure.id,
                        )
                    )
                ).all()
            )
            for s in sessions_to_sync:
                if s.customer_id != cust.id:
                    s.customer_id = cust.id
                if s.draft and isinstance(s.draft.fields, dict):
                    f = dict(s.draft.fields)
                    if customer_name and customer_name.strip():
                        for name_k in ["customer_name", "policyholder_name", "client_name"]:
                            if name_k in f:
                                if isinstance(f[name_k], dict):
                                    f[name_k] = {**f[name_k], "value": cust.canonical_name}
                                else:
                                    f[name_k] = cust.canonical_name
                    if ic_no and ic_no.strip():
                        for ic_k in ["customer_ic_no", "ic_no", "nric_no", "id_number"]:
                            if ic_k in f:
                                if isinstance(f[ic_k], dict):
                                    f[ic_k] = {**f[ic_k], "value": cust.id_number}
                                else:
                                    f[ic_k] = cust.id_number
                    s.draft.fields = f

    if tenure.tracked_vehicle:
        if engine_cc and engine_cc.strip():
            tenure.tracked_vehicle.engine_cc = engine_cc.strip()
        if vehicle_model and vehicle_model.strip():
            tenure.tracked_vehicle.car_model = vehicle_model.strip()
        if engine_no and engine_no.strip():
            tenure.tracked_vehicle.engine_no = engine_no.strip()
        if chassis_no and chassis_no.strip():
            tenure.tracked_vehicle.chassis_no = chassis_no.strip()

    # Date manipulation & synchronization
    dt_start = None
    dt_end = None
    if coverage_start_date:
        try:
            clean_s = coverage_start_date.split("T")[0].strip()
            if clean_s:
                dt_start = datetime.strptime(clean_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_start_date = dt_start
        except Exception as e:
            logger.warning("Could not parse coverage_start_date '%s': %s", coverage_start_date, e)

    if coverage_end_date:
        try:
            clean_e = coverage_end_date.split("T")[0].strip()
            if clean_e:
                dt_end = datetime.strptime(clean_e, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                tenure.coverage_end_date = dt_end
                tenure.expiry_month = dt_end.strftime("%Y-%m")
        except Exception as e:
            logger.warning("Could not parse coverage_end_date '%s': %s", coverage_end_date, e)

    # Propagate updated coverage dates and metadata to linked sessions
    linked_sessions = list(
        db.scalars(
            select(SessionModel).where(SessionModel.tenure_id == tenure_id)
        ).all()
    )
    for s in linked_sessions:
        if dt_start:
            s.coverage_start_date = dt_start
        if dt_end:
            s.coverage_end_date = dt_end
        if s.draft and isinstance(s.draft.fields, dict):
            f = dict(s.draft.fields)
            if dt_start:
                f["coverage_start_date"] = dt_start.isoformat()
            if dt_end:
                f["coverage_end_date"] = dt_end.isoformat()
            if customer_name:
                f["customer_name"] = customer_name.strip()
            if ic_no:
                f["ic_no"] = ic_no.strip()
            if engine_cc:
                f["engine_cc"] = engine_cc.strip()
            if engine_no:
                f["engine_number"] = engine_no.strip()
            if chassis_no:
                f["chassis_number"] = chassis_no.strip()
            if vehicle_model:
                f["car_model"] = vehicle_model.strip()
            s.draft.fields = f

    # Update all comparison entries under this tenure
    entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    for e in entries:
        e.road_tax = road_tax
        e.runner_fee = float(tenure.runner_fee)
        e.total_payable = float(e.motor_premium) + road_tax + float(tenure.runner_fee)

    db.commit()
    return get_marketing_comparison(db, tenure_id)



def save_comparison_entry(
    db: Session,
    tenure_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Save or update a single underwriter column in the comparison matrix."""
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry_id = payload.get("id")
    entry = db.get(TenureComparisonEntry, entry_id) if entry_id else None

    if not entry:
        entry = TenureComparisonEntry(
            tenure_id=tenure_id,
            company_name=_safe_str(payload.get("company_name") or "New Insurer"),
            is_manual=bool(payload.get("is_manual", True)),
        )
        db.add(entry)

    # Update fields
    if "company_name" in payload:
        entry.company_name = _safe_str(payload["company_name"])
    if "sum_insured" in payload:
        entry.sum_insured = _to_float(payload["sum_insured"])
    if "valuation_type" in payload:
        entry.valuation_type = _safe_str(payload["valuation_type"])
        entry.agreed_value = entry.valuation_type == "agreed_value"
    if "motor_premium" in payload:
        entry.motor_premium = _to_float(payload["motor_premium"])
    if "towing_limit" in payload:
        entry.towing_limit = _safe_str(payload["towing_limit"])
    if "agreed_value" in payload:
        entry.agreed_value = bool(payload["agreed_value"])
        if entry.agreed_value:
            entry.valuation_type = "agreed_value"
    if "waiver_betterment" in payload:
        entry.waiver_betterment = bool(payload["waiver_betterment"])
    if "excess" in payload:
        entry.excess = _to_float(payload["excess"])
    if "windscreen_sum_insured" in payload:
        entry.windscreen_sum_insured = _to_float(payload["windscreen_sum_insured"]) or None
    if "special_perils" in payload:
        entry.special_perils = _safe_str(payload["special_perils"]) or None
    if "llp_llop" in payload:
        entry.llp_llop = _safe_str(payload["llp_llop"]) or None
    if "notes" in payload:
        entry.notes = _safe_str(payload["notes"]) or None
    if "is_recommended" in payload:
        entry.is_recommended = bool(payload["is_recommended"])

    # Recompute fixed costs and total payable
    entry.road_tax = float(tenure.road_tax)
    entry.runner_fee = float(tenure.runner_fee)
    entry.total_payable = float(entry.motor_premium) + entry.road_tax + entry.runner_fee

    if float(entry.sum_insured) > 0:
        entry.rate_percentage = round((float(entry.motor_premium) / float(entry.sum_insured)) * 100, 4)

    db.commit()
    return get_marketing_comparison(db, tenure_id)


def delete_comparison_entry(db: Session, tenure_id: str, entry_id: str) -> dict[str, Any]:
    """Delete a comparison column."""
    entry = db.get(TenureComparisonEntry, entry_id)
    if entry and entry.tenure_id == tenure_id:
        if entry.session_id:
            s = db.get(SessionModel, entry.session_id)
            if s:
                s.status = "trash"
        db.delete(entry)
        db.commit()
    return get_marketing_comparison(db, tenure_id)


def select_winner_and_generate_draft(
    db: Session,
    tenure_id: str,
    entry_id: str,
    user_id: str,
    *,
    force_state: bool | None = None,
) -> dict[str, Any]:
    """Toggle or set winning underwriter recommendation state, update tenure status,
    and prepare the Quotation Builder draft.
    Allows multiple winners (e.g. 2 or 3 quotes) and clicking to deselect/unpick.
    """
    tenure = db.get(InsuranceTenure, tenure_id)
    if not tenure:
        raise ValueError(f"Tenure {tenure_id} not found")

    entry = db.get(TenureComparisonEntry, entry_id)
    if not entry or entry.tenure_id != tenure_id:
        raise ValueError(f"Comparison entry {entry_id} not found under tenure {tenure_id}")

    # Determine target recommendation state (toggle if force_state is None)
    new_state = (not entry.is_recommended) if force_state is None else force_state
    entry.is_recommended = new_state

    session_id = entry.session_id
    draft_id = None

    if new_state:
        # If newly selected, ensure linked session has an official RL reference
        if session_id:
            s = db.get(SessionModel, session_id)
            if s:
                if not s.quotation_ref or not s.quotation_ref.startswith("RL"):
                    ref_num = f"RL-{tenure.vehicle_no}-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"
                    s.quotation_ref = ref_num
                draft_id = s.draft_id
        else:
            # For manual quotes without a session, create a real UploadedFile stub, QuotationDraft, and SessionModel
            comp = None
            if entry.company_id:
                comp = db.get(InsuranceCompany, entry.company_id)
            if not comp and entry.company_name:
                comp = db.scalar(select(InsuranceCompany).where(InsuranceCompany.name == entry.company_name))

            comp_id = comp.id if comp else entry.company_id
            if comp_id and not entry.company_id:
                entry.company_id = comp_id

            ref_num = f"RL-{tenure.vehicle_no}-{datetime.now(timezone.utc).strftime('%y%m%d%H%M')}"

            # Locate or create an owner batch
            batch = db.scalar(
                select(Batch).where(Batch.owner_id == user_id).order_by(Batch.created_at.desc()).limit(1)
            )
            if not batch:
                batch = Batch(
                    id=new_id(),
                    owner_id=user_id,
                    name=f"Manual Quotes - {tenure.vehicle_no}",
                    status=RecordStatus.READY.value,
                )
                db.add(batch)
                db.flush()

            # Create real UploadedFile stub (satisfies foreign key constraint)
            uploaded_file_id = new_id()
            stub_file = UploadedFile(
                id=uploaded_file_id,
                batch_id=batch.id,
                owner_id=user_id,
                original_filename=f"Manual Quote - {entry.company_name}.pdf",
                content_type="application/pdf",
                storage_path=f"manual_quotes/{uploaded_file_id}.pdf",
                storage_provider="local_ephemeral",
                storage_status=StorageStatus.AVAILABLE.value,
                size_bytes=0,
                status=RecordStatus.READY.value,
                is_test=False,
                insurance_company_id=comp_id,
            )
            db.add(stub_file)
            db.flush()

            # Create QuotationDraft with valid uploaded_file_id
            new_draft = QuotationDraft(
                id=new_id(),
                uploaded_file_id=stub_file.id,
                owner_id=user_id,
                company_id=comp_id,
                status=RecordStatus.READY.value,
                fields={
                    "vehicle_no": tenure.vehicle_no,
                    "customer_name": tenure.customer_name,
                    "insurance_company": entry.company_name,
                    "sum_insured": float(entry.sum_insured),
                    "coverage_amount": float(entry.sum_insured),
                    "basic_premium": float(entry.motor_premium),
                    "road_tax": float(entry.road_tax),
                    "runner_fee": float(entry.runner_fee),
                    "total_payable": float(entry.total_payable),
                    "total_amount": float(entry.total_payable),
                    "towing_limit": entry.towing_limit,
                    "agreed_value": entry.agreed_value,
                    "waiver_of_betterment": entry.waiver_betterment,
                    "excess": float(entry.excess),
                    "coverage_start_date": tenure.coverage_start_date.isoformat(),
                    "coverage_end_date": tenure.coverage_end_date.isoformat(),
                    "ncd_percentage": float(tenure.ncd_percentage) if tenure.ncd_percentage is not None else 0.0,
                    "quotation_reference": ref_num,
                },
            )
            db.add(new_draft)
            db.flush()
            draft_id = new_draft.id

            # Create real SessionModel linked to tenure
            session_model = SessionModel(
                id=new_id(),
                owner_id=user_id,
                uploaded_file_id=stub_file.id,
                draft_id=new_draft.id,
                quotation_ref=ref_num,
                tenure_id=tenure.id,
                tracked_vehicle_id=tenure.tracked_vehicle_id,
                customer_id=tenure.customer_id,
                detected_company=entry.company_name,
                quotation_status="ready",
                status=AccountStatus.ACTIVE.value,
                coverage_start_date=tenure.coverage_start_date,
                coverage_end_date=tenure.coverage_end_date,
            )
            db.add(session_model)
            db.flush()

            # Associate entry with this session
            entry.session_id = session_model.id
            session_id = session_model.id

    # Query all currently recommended entries under this tenure
    all_entries = list(
        db.scalars(
            select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == tenure_id)
        ).all()
    )
    rec_entries = [e for e in all_entries if e.is_recommended]

    if rec_entries:
        primary = entry if new_state else rec_entries[0]
        tenure.status = "quoted"
        tenure.winning_company_id = primary.company_id
        tenure.won_premium = primary.total_payable
        if primary.session_id:
            s_primary = db.get(SessionModel, primary.session_id)
            if s_primary and s_primary.quotation_ref:
                tenure.winning_quotation_ref = s_primary.quotation_ref
    else:
        tenure.winning_company_id = None
        tenure.won_premium = None
        tenure.winning_quotation_ref = None

    db.commit()

    return {
        "status": "success",
        "tenure_id": tenure.id,
        "entry_id": entry.id,
        "is_recommended": entry.is_recommended,
        "selected_count": len(rec_entries),
        "winning_company": entry.company_name,
        "total_payable": float(entry.total_payable),
        "session_id": session_id,
        "draft_id": draft_id,
        "quotation_ref": tenure.winning_quotation_ref,
    }


def format_whatsapp_teaser(db: Session, tenure_id: str) -> str:
    """Format a clean, executive WhatsApp teaser message comparing all underwriters for client messaging."""
    data = get_marketing_comparison(db, tenure_id)
    tenure = data["tenure"]
    entries = data["entries"]

    plate = tenure["vehicle_no"]
    customer = tenure["customer_name"]
    model = tenure["vehicle_model"]
    period = tenure["coverage_period_formatted"]
    ncd = tenure.get("ncd_percentage")
    ncd_str = f"{ncd:.0f}%" if ncd is not None else "Not Detected"

    lines = [
        f"🚗 *Insurance Renewal Comparison for {plate}*",
        f"👤 Customer: {customer}",
        f"🚘 Vehicle: {model} ({tenure['engine_cc']})",
        f"📅 Period: {period} | NCD: {ncd_str}",
        f"🛣️ Road Tax & Runner Fee: RM {tenure['fixed_costs_total']:.2f}",
        "",
        "📋 *UNDERWRITER COMPARISON:*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, e in enumerate(entries, 1):
        rec_tag = " ★ (RECOMMENDED)" if e["is_recommended"] else ""
        val_tag = "Agreed Value" if e["agreed_value"] else "Market Value"
        betterment_tag = "Yes" if e["waiver_betterment"] else "No"

        lines.extend([
            f"*{idx}. {e['company_name']}{rec_tag}*",
            f"   • Sum Insured: RM {e['sum_insured']:,.2f} ({val_tag})",
            f"   • Motor Insurance: RM {e['motor_premium']:,.2f}",
            f"   • *TOTAL PAYABLE: RM {e['total_payable']:,.2f}*",
            f"   • Towing: {e['towing_limit']}",
            f"   • Waiver of Betterment: {betterment_tag} | Excess: RM {e['excess']:.2f}",
            "",
        ])

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    rec_winners = [e for e in entries if e.get("is_recommended")]
    if len(rec_winners) == 1:
        lines.append(f"🏆 *Recommended Choice:* {rec_winners[0]['company_name']} (Total: RM {rec_winners[0]['total_payable']:,.2f})\n")
    elif len(rec_winners) > 1:
        winner_items = ", ".join(f"{w['company_name']} (RM {w['total_payable']:,.2f})" for w in rec_winners)
        lines.append(f"🏆 *Shortlisted Options ({len(rec_winners)}):* {winner_items}\n")

    lines.append("💡 *Please let us know your preferred insurer so we can issue your official Risk-Locker quotation!*")

    return "\n".join(lines)

